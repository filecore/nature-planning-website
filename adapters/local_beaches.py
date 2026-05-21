"""Adapter for the user's curated swimming-beach list (Firefox GPX
export). Read from ``data/manual/local_beaches.csv``; the row's Google
Maps URL carries the coordinate."""

from __future__ import annotations

import csv
import io
import pathlib
import re
import sys

from common import make_feature, run, write_layer

NAME = "local-beaches"
SOURCE = "Curated local beaches (personal Google Maps list)"
SITE_URL = "https://nature.togneri.net/"
CSV_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "manual" / "local_beaches.csv"
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
    for row in csv.DictReader(io.StringIO(CSV_PATH.read_text(encoding="utf-8-sig"))):
        name = (row.get("Name") or "").strip()
        if not name:
            continue
        coord = _coord((row.get("Google Maps URL") or "").strip())
        if not coord:
            continue
        lat, lon = coord
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower())[:60]
        f = make_feature(
            feature_id=f"local-beach-{slug}-{lat:.4f}-{lon:.4f}",
            name=name,
            lat=lat,
            lon=lon,
            category="local-beach",
            source=SOURCE,
            source_url=(row.get("Link") or "").strip() or SITE_URL,
            features=[],
            description=(row.get("Details") or "").strip(),
        )
        if f:
            out.append(f)
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
