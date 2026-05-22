"""Adapter for bumblebee (Bombus) observations in Finland (GBIF).

Multiple bumblebee monitoring projects feed observations into FinBIF
and from there to GBIF: the SYKE / Luomus pollinator-monitoring scheme,
opportunistic FinBIF observations, and academic studies. We pull the
genus *Bombus* across all of them, restricted to Finland and the last
five years, and aggregate to ~10x10 km grid cells the same way the
butterflies adapter does. The popup shows species richness, total
individuals, and the three most-seen species.

Coordinate uncertainty in GBIF Bombus records is typically already 10
km (cell-coarsened by FinBIF), which matches our bin resolution.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

from common import make_feature, run, write_layer

NAME = "bumblebees"
SOURCE = "GBIF: Bombus observations in Finland (FinBIF aggregate)"
SITE_URL = "https://www.gbif.org/occurrence/search?country=FI&taxon_key=1340278"
API = "https://api.gbif.org/v1/occurrence/search"
TAXON_KEY = 1340278  # genus Bombus

PAGE = 300
MIN_YEAR = 2020

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
            "taxonKey": TAXON_KEY,
            "hasCoordinate": "true",
            "year": f"{MIN_YEAR},2030",
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
    print(f"  fetching Bombus from GBIF since {MIN_YEAR}")
    records = _fetch_all()
    print(f"    {len(records)} records")

    cells: dict[tuple[float, float], Counter[str]] = defaultdict(Counter)
    for r in records:
        lat = r.get("decimalLatitude")
        lon = r.get("decimalLongitude")
        if lat is None or lon is None:
            continue
        species = r.get("species") or r.get("acceptedScientificName") or r.get("scientificName")
        if not species or species.lower().startswith("bombus latr"):
            # Genus-only records add no species information.
            continue
        cells[_bin(float(lat), float(lon))][species] += int(r.get("individualCount") or 1)

    out: list[dict] = []
    for (lat, lon), counter in cells.items():
        n_species = len(counter)
        total = sum(counter.values())
        top = ", ".join(s for s, _ in counter.most_common(3))
        description = (
            f"{n_species} species, {total} individuals recorded since {MIN_YEAR}. "
            f"Most-seen: {top}."
        )
        feature = make_feature(
            feature_id=f"bumblebees-{lat:.2f}-{lon:.2f}",
            name=f"Bumblebees: {n_species} species",
            lat=lat,
            lon=lon,
            category="bumblebees",
            source=SOURCE,
            source_url=SITE_URL,
            features=[f"richness-{'high' if n_species >= 8 else 'mid' if n_species >= 3 else 'low'}"],
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
