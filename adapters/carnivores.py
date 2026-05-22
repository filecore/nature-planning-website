"""Adapter for large-carnivore observations: wolves, bears, lynx.

Luke's authoritative Tassu sightings registry (riistahavainnot.fi) has
no public API, so we use the openly-licensed GBIF aggregate of the
same species. Most records come from iNaturalist and FinBIF, with
coordinates coarsened to roughly 25 km in line with FinBIF's
sensitive-species policy. That coarsening is appropriate for these
species - it both protects animals from disturbance and reflects how
far large carnivores actually roam.

Emits one GeoJSON per species so the frontend can toggle them
independently: ``wolves``, ``bears``, ``lynx``. Raw records are
cached on disk for 30 days via ``_gbif.py``.
"""

from __future__ import annotations

import pathlib
import sys

from _gbif import occurrence_search
from common import LAYERS_DIR, make_feature, run, write_layer

SOURCE = "GBIF: large-carnivore observations in Finland"
SITE_URL = "https://www.gbif.org/"

MIN_YEAR = 2020

# scientific, vernacular, output-layer-id
SPECIES = [
    ("Canis lupus",  "Wolf",          "wolves"),
    ("Ursus arctos", "Brown bear",    "bears"),
    ("Lynx lynx",    "Eurasian lynx", "lynx"),
]


def _features_for(scientific: str, vernacular: str) -> list[dict]:
    cache_name = "carnivore_" + scientific.lower().replace(" ", "_")
    records = occurrence_search(cache_name, {
        "country": "FI",
        "scientificName": scientific,
        "hasCoordinate": "true",
    }, year_range=(MIN_YEAR, 2026))

    out: list[dict] = []
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
    written: list[pathlib.Path] = []
    for scientific, vernacular, layer_id in SPECIES:
        print(f"  building {layer_id} ({scientific})")
        features = _features_for(scientific, vernacular)
        written.append(write_layer(layer_id, SOURCE, SITE_URL, features))

    # Drop the legacy combined file from earlier iterations so the
    # frontend never picks up a stale dataset.
    legacy = LAYERS_DIR / "carnivores.geojson"
    if legacy.exists():
        legacy.unlink()
        print(f"  removed legacy {legacy.name}")

    return written


if __name__ == "__main__":
    sys.exit(run(main, name="carnivores"))
