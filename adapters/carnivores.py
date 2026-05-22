"""Adapter for large-carnivore observations: wolves, bears, lynx.

Luke's authoritative Tassu sightings registry (riistahavainnot.fi) has
no public API, so we use the openly-licensed GBIF aggregate of the
same species. Most records come from iNaturalist and FinBIF, with
coordinates coarsened to roughly 25 km in line with FinBIF's
sensitive-species policy. That coarsening is appropriate for these
species - it both protects animals from disturbance and reflects how
far large carnivores actually roam.

We ship one feature per record (a few hundred per year), labelled
with species, year, and coordinate-precision. Raw records are cached
on disk for 30 days via ``_gbif.py``.
"""

from __future__ import annotations

import sys

from _gbif import occurrence_search
from common import make_feature, run, write_layer

NAME = "carnivores"
SOURCE = "GBIF: large-carnivore observations in Finland"
SITE_URL = "https://www.gbif.org/"

MIN_YEAR = 2020

SPECIES = [
    ("Canis lupus", "Wolf"),
    ("Ursus arctos", "Brown bear"),
    ("Lynx lynx", "Eurasian lynx"),
]


def fetch_features() -> list[dict]:
    out: list[dict] = []
    for scientific, vernacular in SPECIES:
        cache_name = "carnivore_" + scientific.lower().replace(" ", "_")
        records = occurrence_search(cache_name, {
            "country": "FI",
            "scientificName": scientific,
            "hasCoordinate": "true",
        }, year_range=(MIN_YEAR, 2025))
        for r in records:
            lat = r.get("decimalLatitude")
            lon = r.get("decimalLongitude")
            if lat is None or lon is None:
                continue
            event_date = (r.get("eventDate") or "")[:10]
            uncertainty_m = r.get("coordinateUncertaintyInMeters")
            unc_label = ""
            if uncertainty_m is not None:
                try:
                    km = round(float(uncertainty_m) / 1000.0)
                    if km > 0:
                        unc_label = f", location accurate to ~{km} km"
                except (TypeError, ValueError):
                    pass
            description = (
                f"{vernacular} ({scientific}) observed on {event_date or 'unknown date'}"
                f"{unc_label}. Source: GBIF."
            )
            feature_id = f"carnivore-{scientific.lower().replace(' ', '-')}-{r.get('key') or r.get('gbifID')}"
            feature = make_feature(
                feature_id=feature_id,
                name=vernacular,
                lat=float(lat),
                lon=float(lon),
                category="carnivore",
                source=SOURCE,
                source_url=SITE_URL,
                features=[scientific.lower().split()[0]],
                description=description,
            )
            if feature:
                feature["properties"]["species"] = scientific
                feature["properties"]["vernacular"] = vernacular
                if event_date:
                    feature["properties"]["observed_on"] = event_date
                if uncertainty_m is not None:
                    feature["properties"]["coordinate_uncertainty_m"] = uncertainty_m
                out.append(feature)
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
