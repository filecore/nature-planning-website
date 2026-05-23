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

# FinBIF coarsens large-carnivore coordinates to roughly 25 km to
# protect sensitive species; the result is that wolf / bear / lynx
# records routinely land on the *same* grid point. Without any
# nudging, the layer rendered later in the front-end's LAYERS array
# fully occludes the layers below it - typically the bear hides the
# wolf entirely. This kills the "show me all carnivores at once" use
# case and there is no UI cue that something is hidden.
#
# Each species gets a fixed offset on an equilateral triangle ~1 km
# on a side, well inside the existing coarsening uncertainty so this
# does not misrepresent location. Wolf goes north, bear southeast,
# lynx southwest, so overlapping records show as three touching
# circles instead of one. At 60 deg N, 1 km ~ 0.009 deg lat and
# ~ 0.018 deg lon. Deterministic per species, so the same record
# always lands at the same coordinate across refreshes.
JITTER_LAT_DEG = 0.005   # ~ 0.55 km
JITTER_LON_DEG = 0.010   # ~ 0.55 km at 60 deg N
SPECIES_OFFSET = {
    "Canis lupus":  ( JITTER_LAT_DEG,         0.0),
    "Ursus arctos": (-JITTER_LAT_DEG * 0.5,   JITTER_LON_DEG),
    "Lynx lynx":    (-JITTER_LAT_DEG * 0.5,  -JITTER_LON_DEG),
}

# Only nudge records that are themselves already coarsened. Precise
# records (uncertainty under 1 km, or genuinely fine-grained citizen
# observations) keep their reported coordinate so we do not move a
# true sighting away from where it was actually recorded.
JITTER_MIN_UNCERTAINTY_M = 1000.0


def _jittered(scientific: str, lat: float, lon: float, uncertainty_m) -> tuple[float, float]:
    if uncertainty_m is None:
        return lat, lon
    try:
        if float(uncertainty_m) < JITTER_MIN_UNCERTAINTY_M:
            return lat, lon
    except (TypeError, ValueError):
        return lat, lon
    dlat, dlon = SPECIES_OFFSET.get(scientific, (0.0, 0.0))
    return lat + dlat, lon + dlon


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
        plot_lat, plot_lon = _jittered(scientific, float(lat), float(lon), uncertainty_m)
        feature = make_feature(
            feature_id=feature_id,
            name=vernacular,
            lat=plot_lat,
            lon=plot_lon,
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
