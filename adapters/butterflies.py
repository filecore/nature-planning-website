"""Adapter for the Finnish national butterfly monitoring scheme (NAFI).

The NAFI scheme is a route-based citizen-science transect count run by
the Finnish Lepidopterological Society and Luomus. The dataset is
published openly on GBIF as
``181eab51-9399-4baa-a0df-8de01a3acf19`` (DOI 10.15468/imsrtd).

Half a million records since 1999 is far too many to ship as static
GeoJSON, and per-observation points would clutter the map. We aggregate
the most recent three years' records into ~10x10 km grid cells (0.1
deg lat x 0.2 deg lon, close enough to the Finnish ETRS-TM35FIN grid
for visualisation) and emit one feature per cell with species richness
and top species in the popup.

Raw records are cached on disk for 30 days via ``_gbif.py`` because
the cold-cache paginated fetch is slow (GBIF deep-pagination cliff).
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict

from _gbif import occurrence_search
from common import make_feature, run, write_layer

NAME = "butterflies"
SOURCE = "GBIF: NAFI (Finnish butterfly monitoring scheme)"
SITE_URL = "https://www.gbif.org/dataset/181eab51-9399-4baa-a0df-8de01a3acf19"
DATASET_KEY = "181eab51-9399-4baa-a0df-8de01a3acf19"

MIN_YEAR = 2023
BIN_LAT = 0.1
BIN_LON = 0.2


def _bin(lat: float, lon: float) -> tuple[float, float]:
    return (round(lat / BIN_LAT) * BIN_LAT, round(lon / BIN_LON) * BIN_LON)


def fetch_features() -> list[dict]:
    records = occurrence_search("butterflies_nafi", {
        "country": "FI",
        "datasetKey": DATASET_KEY,
        "hasCoordinate": "true",
    }, year_range=(MIN_YEAR, 2026))

    cells: dict[tuple[float, float], Counter[str]] = defaultdict(Counter)
    for r in records:
        lat = r.get("decimalLatitude")
        lon = r.get("decimalLongitude")
        if lat is None or lon is None:
            continue
        species = r.get("species") or r.get("acceptedScientificName") or r.get("scientificName")
        if not species:
            continue
        cells[_bin(float(lat), float(lon))][species] += int(r.get("individualCount") or 1)

    out: list[dict] = []
    for (lat, lon), counter in cells.items():
        n_species = len(counter)
        total = sum(counter.values())
        top = ", ".join(s for s, _ in counter.most_common(3))
        description = (
            f"{n_species} species, {total} individuals counted since {MIN_YEAR}. "
            f"Most-seen: {top}."
        )
        feature = make_feature(
            feature_id=f"butterflies-{lat:.2f}-{lon:.2f}",
            name=f"Butterflies: {n_species} species",
            lat=lat,
            lon=lon,
            category="butterflies",
            source=SOURCE,
            source_url=SITE_URL,
            features=[f"richness-{'high' if n_species >= 15 else 'mid' if n_species >= 5 else 'low'}"],
            description=description,
        )
        if feature:
            feature["properties"]["species_count"] = n_species
            feature["properties"]["individual_count"] = total
            out.append(feature)
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
