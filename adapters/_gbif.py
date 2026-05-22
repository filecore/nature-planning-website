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


def _cache_is_fresh(path: pathlib.Path) -> bool:
    if not path.exists():
        return False
    if os.environ.get("NATURE_FORCE_REFRESH"):
        return False
    try:
        payload = json.loads(path.read_text())
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
        "records": records,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False))


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

    out: list[dict] = []
    start = time.monotonic()

    if year_range is None:
        print(f"  fetching {cache_name} from GBIF (single query)")
        records, hit_cliff = _paginate(params)
        out.extend(records)
        if hit_cliff:
            print(
                f"    WARN: hit GBIF deep-pagination cliff at offset {DEEP_PAGE_THRESHOLD}; "
                "truncated. Pass year_range=... to chunk.",
                file=sys.stderr,
            )
    else:
        year_start, year_end = year_range
        chunks = (year_end - year_start + 1) * 12
        print(
            f"  fetching {cache_name} from GBIF in {chunks} (year, month) chunks "
            f"({year_start}-{year_end})"
        )
        done = 0
        last_log = start
        for year in range(year_start, year_end + 1):
            for month in range(1, 13):
                chunk_params = {**params, "year": str(year), "month": str(month)}
                records, hit_cliff = _paginate(chunk_params)
                out.extend(records)
                done += 1
                now = time.monotonic()
                if hit_cliff:
                    print(
                        f"    WARN: cliff hit on {year}-{month:02d} ({len(records)} truncated)",
                        file=sys.stderr,
                    )
                if now - last_log > 15 or done == chunks:
                    elapsed = int(now - start)
                    print(f"    {done}/{chunks} chunks, {len(out)} records ({elapsed}s)")
                    last_log = now

    _save_cache(cache, out)
    elapsed = int(time.monotonic() - start)
    print(f"  cached {cache_name}: {len(out)} records in {elapsed}s")
    return out


if __name__ == "__main__":
    print("This module is imported by adapters; it is not a CLI.", file=sys.stderr)
    sys.exit(2)
