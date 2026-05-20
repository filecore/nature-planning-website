"""Adapter for Finnish waterfalls (suomenvesiputoukset.fi).

The site has no machine-readable feed, but every waterfall has a detail
page under ``/vesiputoukset/suomen-vesiputoukset-luettelossa/<slug>/``
with the WGS84 coordinates rendered in a table cell. We fetch the index
page, extract the slug list, then fetch each detail page and pull the
Leveysaste (lat) and Pituusaste (lon) values.

This means ~82 HTTP requests per refresh, so be polite: a small delay
between requests, a custom User-Agent identifying the aggregator, and
the standard adapter contract of failing loud on zero features rather
than overwriting a known-good layer.
"""

from __future__ import annotations

import os
import re
import sys
import time
import urllib.request

from common import make_feature, run, write_layer

NAME = "waterfalls"
SOURCE = "suomenvesiputoukset.fi"
SITE_URL = "https://www.suomenvesiputoukset.fi/"
LIST_URL = "https://www.suomenvesiputoukset.fi/vesiputoukset/suomen-vesiputoukset-luettelossa/"

USER_AGENT = (
    "nature-aggregator/0.1 (+https://nature.togneri.net; refresh ~ monthly)"
)
REQUEST_DELAY_SEC = 0.25  # be friendly to the upstream site

DETAIL_HREF_RE = re.compile(
    r'href="/vesiputoukset/suomen-vesiputoukset-luettelossa/([^/"#]+)/"'
)
LAT_RE = re.compile(r"Leveysaste.*?<td[^>]*>\s*([\d.,]+)\s*\(?N", re.DOTALL)
LON_RE = re.compile(r"Pituusaste.*?<td[^>]*>\s*([\d.,]+)\s*\(?E", re.DOTALL)
TITLE_RE = re.compile(r"<h1[^>]*>\s*([^<]+?)\s*</h1>")
META_DESC_RE = re.compile(r'<meta\s+name="description"\s+content="([^"]+)"')


def _http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _slugs_from_index() -> list[str]:
    html = _http_get(LIST_URL)
    seen: list[str] = []
    for slug in DETAIL_HREF_RE.findall(html):
        if slug and slug not in seen:
            seen.append(slug)
    return seen


def _parse_detail(slug: str) -> dict | None:
    url = f"{LIST_URL}{slug}/"
    html = _http_get(url)

    lat_m = LAT_RE.search(html)
    lon_m = LON_RE.search(html)
    if not lat_m or not lon_m:
        return None
    try:
        lat = float(lat_m.group(1).replace(",", "."))
        lon = float(lon_m.group(1).replace(",", "."))
    except ValueError:
        return None

    title_m = TITLE_RE.search(html)
    name = (title_m.group(1).strip() if title_m else slug.replace("-", " ").title())

    desc_m = META_DESC_RE.search(html)
    desc = desc_m.group(1).strip() if desc_m else ""

    return make_feature(
        feature_id=f"wf-{slug}",
        name=name,
        lat=lat,
        lon=lon,
        category="waterfall",
        source=SOURCE,
        source_url=url,
        features=[],
        description=desc[:300],
    )


def fetch_features() -> list[dict]:
    override = os.environ.get("NATURE_WATERFALLS_LIST")
    if override:
        # Test hook: a local file URL or alternate listing endpoint.
        urllib.request.urlopen(override).close()

    slugs = _slugs_from_index()
    print(f"  found {len(slugs)} waterfall detail pages")
    out: list[dict] = []
    skipped: list[str] = []
    for i, slug in enumerate(slugs, 1):
        try:
            feat = _parse_detail(slug)
        except Exception as e:
            print(f"    {slug}: {e}", file=sys.stderr)
            feat = None
        if feat:
            out.append(feat)
        else:
            skipped.append(slug)
        if i % 20 == 0:
            print(f"    {i}/{len(slugs)} processed")
        time.sleep(REQUEST_DELAY_SEC)

    if skipped:
        print(f"  note: {len(skipped)} pages skipped (no coords found)", file=sys.stderr)
        for s in skipped[:5]:
            print(f"    - {s}", file=sys.stderr)
        if len(skipped) > 5:
            print(f"    ... and {len(skipped) - 5} more", file=sys.stderr)
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
