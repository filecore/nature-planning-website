"""Adapter for the user's personal bucket-list / want-to-go layer,
sourced from two Google Maps lists exported to GPX.

CSV: ``data/manual/bucket_list.csv`` with columns
``Region, Name, Source, Details, Google Maps URL``. The Source column
identifies which upstream list each row came from."""

from __future__ import annotations

import csv
import io
import pathlib
import re
import sys

from common import make_feature, run, write_layer

NAME = "bucket-list"
SOURCE = "Personal bucket list (curated Google Maps lists)"
SITE_URL = "https://nature.togneri.net/"
CSV_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "manual" / "bucket_list.csv"
GMAPS_RE = re.compile(r"/maps/(?:place/[^/]+/)?@(-?\d+\.\d+),(-?\d+\.\d+)")


def _coord(url: str):
    m = GMAPS_RE.search(url or "")
    if not m:
        return None
    return float(m.group(1)), float(m.group(2))


def fetch_features():
    if not CSV_PATH.exists():
        raise RuntimeError(f"CSV missing at {CSV_PATH}")
    out = []
    seen = set()
    for row in csv.DictReader(io.StringIO(CSV_PATH.read_text(encoding="utf-8-sig"))):
        name = (row.get("Name") or "").strip()
        if not name:
            continue
        coord = _coord((row.get("Google Maps URL") or "").strip())
        if not coord:
            continue
        lat, lon = coord
        key = (round(lat, 4), round(lon, 4), name.lower())
        if key in seen:
            continue
        seen.add(key)

        source = (row.get("Source") or "").strip()
        details = (row.get("Details") or "").strip()
        desc_bits = []
        if source:
            desc_bits.append(f"From: {source}")
        if details:
            desc_bits.append(details)
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower())[:60]
        f = make_feature(
            feature_id=f"bucket-{slug}-{lat:.4f}-{lon:.4f}",
            name=name,
            lat=lat,
            lon=lon,
            category="bucket-list",
            source=SOURCE,
            source_url=SITE_URL,
            features=[],
            description=" · ".join(desc_bits)[:400],
        )
        if f:
            out.append(f)
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
