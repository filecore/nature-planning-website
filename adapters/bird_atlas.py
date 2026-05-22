"""Adapter for the 4th Finnish Bird Atlas (2022-2025).

The Bird Atlas is a country-wide breeding-bird census run by Luomus
and BirdLife Finland on the standard 10x10 km ETRS-TM35FIN grid.
The fieldwork dataset is published openly on GBIF as
``74b866a0-6bed-41f0-83be-f52bf16ad77a``.

The atlas grid has roughly 3800 cells covering Finland. We bin the
~350k observations into 10x10 km cells (0.1 deg lat x 0.2 deg lon)
and emit one feature per cell with the species count (richness) and
the three most-frequently-recorded species.

We do not attempt to reconstruct the breeding-confirmation index
(Possible / Probable / Confirmed) from the raw GBIF dump - those
codes live in the FinBIF Notebook export, not the GBIF projection.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

from common import make_feature, run, write_layer

NAME = "bird-atlas"
SOURCE = "GBIF: 4th Finnish Bird Atlas (2022-2025)"
SITE_URL = "https://lintuatlas.fi/"
API = "https://api.gbif.org/v1/occurrence/search"
DATASET_KEY = "74b866a0-6bed-41f0-83be-f52bf16ad77a"

PAGE = 300

BIN_LAT = 0.1
BIN_LON = 0.2


def _bin(lat: float, lon: float) -> tuple[float, float]:
    return (round(lat / BIN_LAT) * BIN_LAT, round(lon / BIN_LON) * BIN_LON)


def _fetch_all() -> list[dict]:
    out: list[dict] = []
    offset = 0
    while True:
        qs = urllib.parse.urlencode({
            "country": "FI",
            "datasetKey": DATASET_KEY,
            "hasCoordinate": "true",
            "limit": PAGE,
            "offset": offset,
        })
        req = urllib.request.Request(f"{API}?{qs}", headers={"User-Agent": "nature-aggregator/0.1"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
        results = body.get("results") or []
        out.extend(results)
        if body.get("endOfRecords") or len(results) < PAGE:
            return out
        offset += PAGE


def fetch_features() -> list[dict]:
    print("  fetching 4th Bird Atlas observations from GBIF")
    records = _fetch_all()
    print(f"    {len(records)} records")

    cells: dict[tuple[float, float], Counter[str]] = defaultdict(Counter)
    for r in records:
        lat = r.get("decimalLatitude")
        lon = r.get("decimalLongitude")
        if lat is None or lon is None:
            continue
        species = r.get("species") or r.get("acceptedScientificName") or r.get("scientificName")
        if not species:
            continue
        cells[_bin(float(lat), float(lon))][species] += 1

    out: list[dict] = []
    for (lat, lon), counter in cells.items():
        n_species = len(counter)
        total = sum(counter.values())
        top = ", ".join(s for s, _ in counter.most_common(3))
        description = (
            f"{n_species} bird species recorded ({total} observations) in this "
            f"10 km cell during the 2022-2025 atlas. Most-seen: {top}."
        )
        feature = make_feature(
            feature_id=f"bird-atlas-{lat:.2f}-{lon:.2f}",
            name=f"Bird Atlas: {n_species} species",
            lat=lat,
            lon=lon,
            category="bird-atlas",
            source=SOURCE,
            source_url=SITE_URL,
            features=[f"richness-{'high' if n_species >= 60 else 'mid' if n_species >= 30 else 'low'}"],
            description=description,
        )
        if feature:
            feature["properties"]["species_count"] = n_species
            feature["properties"]["observation_count"] = total
            out.append(feature)
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
