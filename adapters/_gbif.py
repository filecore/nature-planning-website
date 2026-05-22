"""Cached GBIF Occurrence API fetcher.

GBIF's Occurrence Search API has a soft deep-pagination cliff around
offset 10k: under it every page is sub-second, above it every page
takes ~40 seconds. To stay under the cliff we chunk by (year, month)
so no single combined-query needs to deep-paginate, then concatenate
the chunks. The cumulative result is cached on disk for
``CACHE_TTL_DAYS`` to keep subsequent ``refresh.sh`` runs fast.

Cache files live at ``data/cache/gbif_<cache_name>.json`` and are
``.gitignore``'d. Force a refetch by deleting the cache file or
setting ``NATURE_FORCE_REFRESH=1`` in the environment.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.gbif.org/v1/occurrence/search"
PAGE = 300
CACHE_TTL_DAYS = 30
DEEP_PAGE_THRESHOLD = 10000
USER_AGENT = "nature-aggregator/0.1 (https://nature.togneri.net)"

CACHE_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "cache"


def _cache_path(cache_name: str) -> pathlib.Path:
    return CACHE_DIR / f"gbif_{cache_name}.json"


def _checkpoint_path(cache_name: str) -> pathlib.Path:
    return CACHE_DIR / f"gbif_{cache_name}.partial.json"


def _cache_is_fresh(path: pathlib.Path) -> bool:
    if not path.exists():
        return False
    if os.environ.get("NATURE_FORCE_REFRESH"):
        return False
    try:
        payload = json.loads(path.read_text())
        if not payload.get("complete"):
            return False
        fetched_at = _dt.datetime.fromisoformat(payload["fetched_at"].replace("Z", "+00:00"))
    except Exception:
        return False
    age = _dt.datetime.now(_dt.timezone.utc) - fetched_at
    return age.days < CACHE_TTL_DAYS


def _load_cache(path: pathlib.Path) -> list[dict]:
    payload = json.loads(path.read_text())
    return payload.get("records") or []


def _save_cache(path: pathlib.Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "complete": True,
        "records": records,
    }
    # Atomic-ish write: stage to a sibling tmp then rename, so a crash
    # mid-write does not leave a half-truncated cache file.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False))
    tmp.replace(path)


def _load_checkpoint(cache_name: str) -> tuple[set[tuple], list[dict]]:
    """Resume in-progress fetches across crashes.

    Returns (set of completed chunk keys, accumulated records). Each
    chunk key is a tuple like (year,) for a single-year fetch or
    (year, month) for a month-chunked one.
    """
    path = _checkpoint_path(cache_name)
    if not path.exists():
        return set(), []
    try:
        payload = json.loads(path.read_text())
        done = {tuple(k) for k in payload.get("completed") or []}
        return done, payload.get("records") or []
    except Exception:
        return set(), []


def _save_checkpoint(cache_name: str, completed: set[tuple], records: list[dict]) -> None:
    path = _checkpoint_path(cache_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "complete": False,
        "completed": [list(k) for k in completed],
        "records": records,
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False))
    tmp.replace(path)


def _drop_checkpoint(cache_name: str) -> None:
    path = _checkpoint_path(cache_name)
    if path.exists():
        path.unlink()


def _http_get(url: str) -> dict:
    """GET with one-shot 429 backoff. GBIF rate-limits aggressive crawlers."""
    delays = [0, 5, 15, 45]
    last_err: Exception | None = None
    for delay in delays:
        if delay:
            time.sleep(delay)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                continue
            raise
    raise last_err if last_err else RuntimeError("unreachable")


REQUEST_GAP_S = 0.25  # courtesy delay between requests to stay under GBIF's rate limit


def _count(params: dict[str, str], **extra: str) -> int:
    qs = urllib.parse.urlencode({**params, **extra, "limit": 0})
    body = _http_get(f"{API}?{qs}")
    return int(body.get("count") or 0)


def _paginate(params: dict[str, str]) -> tuple[list[dict], bool]:
    """Paginate one GBIF query. Returns (records, hit_deep_cliff)."""
    out: list[dict] = []
    offset = 0
    while True:
        qs = urllib.parse.urlencode({**params, "limit": PAGE, "offset": offset})
        body = _http_get(f"{API}?{qs}")
        results = body.get("results") or []
        out.extend(results)
        if body.get("endOfRecords") or len(results) < PAGE:
            return (out, False)
        offset += PAGE
        if offset >= DEEP_PAGE_THRESHOLD:
            # Deep pagination is slow on GBIF; the caller should chunk.
            return (out, True)
        time.sleep(REQUEST_GAP_S)


def occurrence_search(
    cache_name: str,
    params: dict[str, str],
    *,
    year_range: tuple[int, int] | None = None,
) -> list[dict]:
    """Paginate GBIF /occurrence/search and cache the result.

    ``params`` is the per-query filter (country=FI, datasetKey=..., etc.).
    Do not include ``limit``, ``offset``, ``year``, or ``month`` - those
    are handled here.

    Pass ``year_range=(start, end)`` to chunk by (year, month) so no
    single query needs to deep-paginate past offset 10k. Without
    ``year_range``, a single paginated query is issued and a deep-cliff
    warning is logged if it triggers.
    """
    cache = _cache_path(cache_name)
    if _cache_is_fresh(cache):
        records = _load_cache(cache)
        print(f"  using cached {cache_name} ({len(records)} records, ttl {CACHE_TTL_DAYS}d)")
        return records

    # Resume from checkpoint if a previous run crashed mid-fetch.
    done, out = _load_checkpoint(cache_name)
    if done:
        print(f"  resuming {cache_name} from checkpoint ({len(done)} chunks, {len(out)} records)")
    start = time.monotonic()

    if year_range is None:
        if ("single",) in done:
            print(f"  checkpoint already complete for {cache_name}; finalising")
        else:
            print(f"  fetching {cache_name} from GBIF (single query)")
            records, hit_cliff = _paginate(params)
            out.extend(records)
            if hit_cliff:
                print(
                    f"    WARN: hit GBIF deep-pagination cliff at offset {DEEP_PAGE_THRESHOLD}; "
                    "truncated. Pass year_range=... to chunk.",
                    file=sys.stderr,
                )
            done.add(("single",))
            _save_checkpoint(cache_name, done, out)
    else:
        year_start, year_end = year_range
        years = list(range(year_start, year_end + 1))
        print(
            f"  fetching {cache_name} from GBIF year-by-year "
            f"({year_start}-{year_end})"
        )
        last_log = start
        for year in years:
            if (year,) in done:
                print(f"    {year}: skip (checkpoint)")
                continue
            count = _count(params, year=str(year))
            if count == 0:
                done.add((year,))
                _save_checkpoint(cache_name, done, out)
                continue
            if count < DEEP_PAGE_THRESHOLD - PAGE:
                records, hit_cliff = _paginate({**params, "year": str(year)})
                out.extend(records)
                if hit_cliff:
                    print(f"    WARN: unexpected cliff on year {year}", file=sys.stderr)
                done.add((year,))
                _save_checkpoint(cache_name, done, out)
            else:
                # Year is too big for single pagination; chunk by month.
                # This loses records that are missing the month field
                # (typically 10-20%), which is the price of avoiding
                # GBIF's deep-pagination cliff.
                print(f"    {year}: {count} records, chunking by month")
                for month in range(1, 13):
                    if (year, month) in done:
                        continue
                    records, hit_cliff = _paginate({**params, "year": str(year), "month": str(month)})
                    out.extend(records)
                    if hit_cliff:
                        print(
                            f"    WARN: cliff hit on {year}-{month:02d} "
                            f"({len(records)} truncated)",
                            file=sys.stderr,
                        )
                    done.add((year, month))
                    _save_checkpoint(cache_name, done, out)
                done.add((year,))
                _save_checkpoint(cache_name, done, out)
            now = time.monotonic()
            if now - last_log > 10 or year == years[-1]:
                elapsed = int(now - start)
                print(f"    through {year}: {len(out)} records ({elapsed}s)")
                last_log = now

    _save_cache(cache, out)
    _drop_checkpoint(cache_name)
    elapsed = int(time.monotonic() - start)
    print(f"  cached {cache_name}: {len(out)} records in {elapsed}s")
    return out


if __name__ == "__main__":
    print("This module is imported by adapters; it is not a CLI.", file=sys.stderr)
    sys.exit(2)
