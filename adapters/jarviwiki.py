"""One-time scraper for Järviwiki / Järvi-meriwiki lake data.

Source: ``https://www.jarviwiki.fi/w/api.php`` (MediaWiki + Semantic
MediaWiki). Each lake is a wiki page in ``Luokka:Järvi`` (Category:Lake)
with structured semantic properties: KoordPohj/KoordIta (decimal-degree
WGS84), Pinta-ala (area km²), Korkeustaso (elevation), Maakunta (region),
Kunta (municipality), Päävesistö (main watercourse), Ecological_status,
and Excerpt_fi (a wikitext description with internal links).

Järviwiki has ~55,875 lake pages. Even gzipped that is far too heavy to
push to the browser as a single GeoJSON, and the long tail is mostly
nameless small ponds. We paginate the whole catalogue once and filter
by area (default >= 0.5 km², overridable via NATURE_JARVIWIKI_MIN_KM2)
before writing the layer file.

The wiki is stable; this is a one-time scrape that the user re-runs
when they want fresh data. The output is committed to the repo as a
local cache so a fresh clone gets the layer without re-scraping.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

from common import make_feature, run, write_layer

NAME = "lakes"
SOURCE = "Järviwiki (Järvi-meriwiki)"
SITE_URL = "https://www.jarviwiki.fi/wiki/Etusivu"
API_URL = "https://www.jarviwiki.fi/w/api.php"

ASK_QUERY = (
    "[[Luokka:Järvi]]"
    "|?KoordPohj|?KoordIta|?Pinta-ala|?Korkeustaso"
    "|?Maakunta|?Kunta|?Päävesistö|?Ecological_status|?Excerpt_fi"
)
PAGE_LIMIT = 500
REQUEST_DELAY = 0.35
MIN_AREA_KM2_DEFAULT = 0.5
USER_AGENT = "nature-aggregator/0.1 (+https://nature.togneri.net)"


def _http_get(params: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    url = f"{API_URL}?{qs}"
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _scrape_all() -> list[dict]:
    """Paginate the Luokka:Järvi category via SMW ask.

    Saves a checkpoint after every page so a partial run is recoverable.
    Resumes from the checkpoint if NATURE_JARVIWIKI_RESUME=1 is set.
    """
    import pathlib as _pl
    ckpt = _pl.Path("/tmp/jarviwiki.checkpoint.jsonl")
    resume = os.environ.get("NATURE_JARVIWIKI_RESUME") == "1"
    out: list[dict] = []
    offset = 0
    if resume and ckpt.exists():
        with ckpt.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        offset = len(out)
        print(f"    resuming from checkpoint at offset {offset} ({len(out)} pages)")

    fh = ckpt.open("a", buffering=1)  # line-buffered append
    try:
        while True:
            body = _http_get({
                "action": "ask",
                "query": f"{ASK_QUERY}|limit={PAGE_LIMIT}|offset={offset}",
                "format": "json",
            })
            results = (body.get("query") or {}).get("results") or {}
            if not results:
                break
            for title, page in results.items():
                page["__title__"] = title
                out.append(page)
                fh.write(json.dumps(page, ensure_ascii=False) + "\n")
            next_offset = body.get("query-continue-offset")
            if not next_offset:
                break
            offset = int(next_offset)
            if offset % 2000 == 0:
                print(f"    scraped {offset} / ~55875")
            time.sleep(REQUEST_DELAY)
    finally:
        fh.close()
    return out


def _strip_wikilinks(s: str) -> str:
    s = re.sub(r"\[\[SMW::off\]\]", "", s)
    s = re.sub(r"\[\[:?[^|\]]+\|([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^|\]]+)\]\]", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def _first(val) -> object:
    if isinstance(val, list) and val:
        return val[0]
    return None


def _qty(val) -> float | None:
    item = _first(val)
    if isinstance(item, dict):
        try:
            return float(item.get("value"))
        except (TypeError, ValueError):
            return None
    if isinstance(item, (int, float)):
        return float(item)
    return None


def _wpg_label(val) -> str | None:
    item = _first(val)
    if isinstance(item, dict):
        text = item.get("fulltext") or ""
        return text.replace("_", " ").strip() or None
    return None


def _to_feature(page: dict, fallback_id: int) -> dict | None:
    props = page.get("printouts") or {}
    raw_title = page.get("__title__") or page.get("fulltext") or ""
    # Drop the basin-code suffix from the display name, e.g.
    # "Aakenusjärvi (65.546.1.006)" -> "Aakenusjärvi".
    name = re.sub(r"\s*\([\d.]+\)\s*$", "", raw_title).strip()
    if not name:
        name = raw_title

    lat = _first(props.get("KoordPohj"))
    lon = _first(props.get("KoordIta"))
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return None

    area_km2 = _qty(props.get("Pinta-ala"))
    elev_m = _qty(props.get("Korkeustaso"))
    region = _wpg_label(props.get("Maakunta")) or ""
    if region.endswith(" maakunta"):
        region = region[: -len(" maakunta")]
    municipality = _wpg_label(props.get("Kunta")) or ""
    if municipality.endswith(" (kunta)"):
        municipality = municipality[: -len(" (kunta)")]
    main_watercourse = _wpg_label(props.get("Päävesistö")) or ""
    status = _first(props.get("Ecological status")) or ""
    excerpt = _strip_wikilinks(_first(props.get("Excerpt fi")) or "")

    desc_bits = []
    if area_km2 is not None:
        desc_bits.append(f"Area: {area_km2:.2f} km²")
    if elev_m is not None:
        desc_bits.append(f"Elevation: {elev_m:.0f} m")
    if municipality:
        desc_bits.append(municipality)
    if main_watercourse:
        desc_bits.append(f"Watercourse: {main_watercourse}")
    if status:
        desc_bits.append(f"Ecological status: {status}")
    description = " · ".join(desc_bits)
    if excerpt and excerpt not in description:
        description = (description + "\n" + excerpt).strip()

    return make_feature(
        feature_id=f"jw-{fallback_id}-" + re.sub(r"[^a-z0-9]+", "-", name.lower())[:50],
        name=name,
        lat=lat,
        lon=lon,
        category="lake",
        source=SOURCE,
        source_url=page.get("fullurl") or SITE_URL,
        features=[],
        description=description[:600],
        region=region,
    )


def fetch_features() -> list[dict]:
    min_area = float(os.environ.get("NATURE_JARVIWIKI_MIN_KM2", str(MIN_AREA_KM2_DEFAULT)))
    print(f"  scraping all lakes from {API_URL}")
    raw = _scrape_all()
    print(f"  fetched {len(raw)} lake pages")

    out: list[dict] = []
    skipped_small = 0
    skipped_other = 0
    for i, page in enumerate(raw):
        area = _qty((page.get("printouts") or {}).get("Pinta-ala"))
        if area is None or area < min_area:
            skipped_small += 1
            continue
        feat = _to_feature(page, i)
        if not feat:
            skipped_other += 1
            continue
        out.append(feat)
    print(
        f"  kept {len(out)} lakes (>= {min_area} km²); "
        f"skipped {skipped_small} small, {skipped_other} malformed"
    )
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
