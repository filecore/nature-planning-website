"""Adapter for the hand-curated sauna geojson.

Reads ``data/manual/saunas-enriched.geojson`` and emits the saunas layer.
Replaces the earlier Google Sheet pipeline whose area-level placeholder
coordinates required a coord-jitter + Nominatim geocode dance per sauna.
The curated file holds verified lat/lon for each sauna directly, with
per-feature source URLs.

To refresh: edit ``data/manual/saunas-enriched.geojson`` by hand and
re-run ``refresh.sh`` (or this adapter alone).
"""

from __future__ import annotations

import json
import pathlib
import sys

from common import make_feature, run, write_layer

NAME = "saunas"
SOURCE = "Curated (Metsähallitus, laavu.org, uuvi.fi and per-feature sources)"
SITE_URL = ""
INPUT_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "manual" / "saunas-enriched.geojson"


def fetch_features() -> list[dict]:
    if not INPUT_PATH.exists():
        raise RuntimeError(f"Curated sauna file not found at {INPUT_PATH}")
    raw = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    in_features = raw.get("features") or []

    out: list[dict] = []
    skipped = 0
    for f in in_features:
        geom = f.get("geometry") or {}
        coords = geom.get("coordinates") or []
        if geom.get("type") != "Point" or len(coords) < 2:
            skipped += 1
            continue
        try:
            lon = float(coords[0])
            lat = float(coords[1])
        except (TypeError, ValueError):
            skipped += 1
            continue

        props = f.get("properties") or {}
        feature = make_feature(
            feature_id=props.get("id", ""),
            name=props.get("name", ""),
            lat=lat,
            lon=lon,
            category=props.get("category", "sauna"),
            source=props.get("source") or SOURCE,
            source_url=props.get("source_url", ""),
            features=props.get("features") or ["has-sauna"],
            description=props.get("description", ""),
            region=props.get("region"),
        )
        if not feature:
            skipped += 1
            continue

        confidence = props.get("confidence")
        if confidence:
            feature["properties"]["confidence"] = confidence

        out.append(feature)

    if skipped:
        print(f"  skipped {skipped} malformed feature(s)")
    print(f"  loaded {len(out)} curated sauna(s) from {INPUT_PATH.name}")
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
