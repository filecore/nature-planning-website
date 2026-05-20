"""Adapter for the curated 'Hiking and walking in Uusimaa' Google Sheet.

Source CSV (Hiking places tab) lives at
``data/manual/uusimaa_hiking_places.csv`` and ships with the repo so a
fresh clone can rebuild the layer.

CSV columns:
  Region, Location, Link, Details, Google Maps URL

The Region column is cascading: a value on one row applies to the
following rows until a new Region appears. The Location is "Suburb:
Place" (e.g. "Vuosaari: Ramsinniemi") often -- we try a few search
variants against Nominatim with ``countrycodes=fi``.

Goal: bring every row onto the map as a curated 'Uusimaa classics'
layer with the upstream Link/Details preserved in the popup. Failed
geocodes are reported but do not fail the adapter; partial coverage is
useful.
"""

from __future__ import annotations

import csv
import json
import os
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

from common import make_feature, run, write_layer

NAME = "uusimaa-classics"
SOURCE = "Hiking and walking in Uusimaa (curated public Google Sheet)"
SITE_URL = "https://docs.google.com/spreadsheets/d/1NJUI7e74jLBlsHGTpr9SLZyVQp3HHsLY0e02nVMU_8I/edit"
CSV_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "manual" / "uusimaa_hiking_places.csv"

NOMINATIM_DELAY = 1.1  # one request per ~1.1s as per Nominatim usage policy
USER_AGENT = "nature-aggregator/0.1 (jason@togneri.net)"

GMAPS_AT_RE = re.compile(r'/maps/(?:place/[^/]+/)?@(-?\d+\.\d+),(-?\d+\.\d+)')
GMAPS_Q_RE = re.compile(r'[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)')


def _coords_from_gmaps(url: str) -> tuple[float, float] | None:
    """Pull lat/lon out of a Google Maps URL if it has @-coordinates."""
    if not url:
        return None
    for pat in (GMAPS_AT_RE, GMAPS_Q_RE):
        m = pat.search(url)
        if m:
            try:
                return float(m.group(1)), float(m.group(2))
            except ValueError:
                pass
    return None


def _nominatim(query: str) -> tuple[float, float] | None:
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "q": query, "format": "json", "countrycodes": "fi", "limit": 1,
    })
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            results = json.loads(r.read())
    except Exception as e:
        print(f'  geocode error {query!r}: {e}', file=sys.stderr)
        return None
    if not results:
        return None
    try:
        return float(results[0]['lat']), float(results[0]['lon'])
    except (KeyError, ValueError):
        return None


def _candidate_queries(location: str, region: str) -> list[str]:
    """Build progressively broader search queries for one row."""
    loc = location.strip()
    candidates: list[str] = []
    if ":" in loc:
        suburb, place = [p.strip() for p in loc.split(":", 1)]
        candidates.append(f"{place}, {suburb}, {region}, Finland")
        candidates.append(f"{place}, {region}, Finland")
        candidates.append(f"{suburb}, {region}, Finland")
    else:
        candidates.append(f"{loc}, {region}, Finland")
        candidates.append(f"{loc}, Uusimaa, Finland")
    candidates.append(f"{loc}, Finland")
    # Dedup while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _row_iter():
    """Forward-fill the cascading Region column. Skip header notes."""
    text = CSV_PATH.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    current_region = ""
    for row in reader:
        if row.get("Region", "").strip():
            current_region = row["Region"].strip()
        location = (row.get("Location") or "").strip()
        if not location:
            continue
        yield {
            "region": current_region,
            "location": location,
            "link": (row.get("Link") or "").strip(),
            "details": (row.get("Details") or "").strip(),
            "gmaps": (row.get("Google Maps URL") or "").strip(),
        }


def fetch_features() -> list[dict]:
    if not CSV_PATH.exists():
        raise RuntimeError(
            f"Source CSV missing at {CSV_PATH}. Drop the Google Sheet "
            "export there and re-run."
        )

    rows = list(_row_iter())
    print(f"  {len(rows)} candidate rows in CSV")

    out: list[dict] = []
    unresolved: list[str] = []
    used_gmaps = 0

    for i, row in enumerate(rows, 1):
        coord = _coords_from_gmaps(row["gmaps"])
        if coord:
            used_gmaps += 1
        else:
            coord = None
            for q in _candidate_queries(row["location"], row["region"]):
                coord = _nominatim(q)
                time.sleep(NOMINATIM_DELAY)
                if coord:
                    break

        if not coord:
            unresolved.append(f'{row["region"]}: {row["location"]}')
            continue

        lat, lon = coord
        details = row["details"]
        if details in ("-", ""):
            details = ""
        description_bits = []
        if row["region"]:
            description_bits.append(row["region"])
        if details:
            description_bits.append(details)
        description = " · ".join(description_bits)

        slug = re.sub(r"[^a-z0-9]+", "-", row["location"].lower()).strip("-")[:60]
        feature_id = f"uusimaa-{slug}-{i}"

        link = row["link"] or row["gmaps"] or SITE_URL

        f = make_feature(
            feature_id=feature_id,
            name=row["location"],
            lat=lat,
            lon=lon,
            category="uusimaa-classic",
            source=SOURCE,
            source_url=link,
            features=[],
            description=description[:400],
        )
        if f:
            out.append(f)
        if i % 10 == 0:
            print(f"    {i}/{len(rows)} processed ({len(out)} resolved)")

    print(f"  resolved: {len(out)} / {len(rows)}  (gmaps: {used_gmaps}, nominatim: {len(out) - used_gmaps})")
    if unresolved:
        print(f"  unresolved ({len(unresolved)}):")
        for u in unresolved[:8]:
            print(f"    - {u}")
        if len(unresolved) > 8:
            print(f"    ... and {len(unresolved) - 8} more")
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
