"""Adapter for the curated Finnish caves layer.

Source: ``data/manual/caves.csv`` (committed to the repo). Each row is
a cave with a Google Maps URL carrying its WGS84 coordinate. The
adapter only parses ``@lat,lon`` out of the URL -- it does not
geocode -- so the layer is fully deterministic from the CSV.

CSV columns: Region, Name, Link, Details, Google Maps URL.

The Caves layer overlaps intentionally with other layers (e.g. Uusimaa
classics) per the user's exception: the Uusimaa list is a curated
overlay and may contain features that also belong to thematic filters
such as Caves.
"""

from __future__ import annotations

import csv
import io
import pathlib
import re
import sys

from common import make_feature, run, write_layer

NAME = "caves"
SOURCE = "Curated Finnish caves (hand-edited list)"
SITE_URL = "https://nature.togneri.net/"
CSV_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "manual" / "caves.csv"

GMAPS_AT_RE = re.compile(r"/maps/(?:place/[^/]+/)?@(-?\d+\.\d+),(-?\d+\.\d+)")


def _coord_from_url(url: str) -> tuple[float, float] | None:
    if not url:
        return None
    m = GMAPS_AT_RE.search(url)
    if not m:
        return None
    try:
        return float(m.group(1)), float(m.group(2))
    except ValueError:
        return None


def fetch_features() -> list[dict]:
    if not CSV_PATH.exists():
        raise RuntimeError(
            f"Source CSV missing at {CSV_PATH}. Edit it and re-run; the "
            "adapter does not geocode, so every row must have a Google "
            "Maps URL with an @lat,lon component."
        )

    text = CSV_PATH.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    out: list[dict] = []
    skipped: list[str] = []
    for row in reader:
        name = (row.get("Name") or "").strip()
        if not name:
            continue
        coord = _coord_from_url((row.get("Google Maps URL") or "").strip())
        if not coord:
            skipped.append(name)
            continue
        lat, lon = coord

        region = (row.get("Region") or "").strip() or None
        details = (row.get("Details") or "").strip()
        link = (row.get("Link") or "").strip() or SITE_URL

        feature_id = "cave-" + re.sub(r"[^a-z0-9]+", "-", name.lower())[:60] + f"-{lat:.4f}-{lon:.4f}"
        f = make_feature(
            feature_id=feature_id,
            name=name,
            lat=lat,
            lon=lon,
            category="cave",
            source=SOURCE,
            source_url=link,
            features=[],
            description=details,
            region=region,
        )
        if f:
            out.append(f)

    if skipped:
        print(f"  note: skipped {len(skipped)} row(s) lacking a Google Maps URL: {', '.join(skipped[:5])}", file=sys.stderr)
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
