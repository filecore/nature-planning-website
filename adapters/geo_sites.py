"""Adapter for nationally valuable geological sites (SYKE).

SYKE publishes four "nationally valuable" geological-formation
inventories as a single WFS workspace
(``syke_geologisetmuodostumat``). Each is a polygon layer; we emit a
point per polygon (bbox centroid) and write one GeoJSON per type so
the frontend can toggle them independently.

Layers (counts approximate as of 2026):

* Arvokkaat_kallioalueet              -> geo-bedrock      (~1286)
* Arvokkaat_kivikot                   -> geo-boulders     (~472)
* Arvokkaat_moreenimuodostumat        -> geo-moraines     (~607)
* Arvokkaat_tuuli_ja_rantakerrostumat -> geo-eolian       (~417)

``arvoluokka`` (value class) is 1 (unique) - 4 (valuable) and is
exposed on every feature as a ``class-N`` tag so the frontend filter
can hide lower-tier sites on demand.
"""

from __future__ import annotations

import json
import pathlib
import sys
import urllib.parse
import urllib.request

from common import LAYERS_DIR, make_feature, polygon_bbox_centroid, run, write_layer

SOURCE = "SYKE: nationally valuable geological formations"
SITE_URL = "https://www.syke.fi/avointieto"
WFS_URL = "https://paikkatiedot.ymparisto.fi/geoserver/syke_geologisetmuodostumat/wfs"

# typeName -> (layer file id, English subtype label)
LAYERS = [
    ("Arvokkaat_kallioalueet",              "geo-bedrock",  "Bedrock area"),
    ("Arvokkaat_kivikot",                   "geo-boulders", "Boulder field"),
    ("Arvokkaat_moreenimuodostumat",        "geo-moraines", "Moraine formation"),
    ("Arvokkaat_tuuli_ja_rantakerrostumat", "geo-eolian",   "Wind / shore deposit"),
]

# Numeric arvoluokka -> human label (only kallioalueet populate
# ``selitearvoluokka``, but the numeric scale matches across all four
# types, so we synthesise a label for the other three).
CLASS_LABELS = {
    1: "Unique",
    2: "Extremely valuable",
    3: "Very valuable",
    4: "Valuable",
}


def _wfs_get(type_name: str) -> dict:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": f"syke_geologisetmuodostumat:{type_name}",
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "count": "5000",
    }
    url = WFS_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "nature-aggregator/0.1"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _feature_from(row: dict, layer_id: str, sublabel: str) -> dict | None:
    geom = row.get("geometry") or {}
    if geom.get("type") not in ("Polygon", "MultiPolygon"):
        return None
    centroid = polygon_bbox_centroid(geom)
    if not centroid:
        return None
    lat, lon = centroid

    props = row.get("properties") or {}
    name = (props.get("nimi") or "").strip() or "(unnamed)"
    tunnus = props.get("lskallioaluetunnus") or props.get("objectid") or ""
    feature_id = f"{layer_id}-{tunnus}"

    arvoluokka = props.get("arvoluokka")
    try:
        class_num = int(arvoluokka) if arvoluokka is not None else None
    except (TypeError, ValueError):
        class_num = None

    class_label = (props.get("selitearvoluokka") or "").strip()
    if not class_label and class_num is not None:
        class_label = CLASS_LABELS.get(class_num, "")

    bits = [sublabel]
    if class_label:
        bits.append(class_label)
    if props.get("lisatieto"):
        bits.append(str(props["lisatieto"]).strip())
    description = " . ".join(b for b in bits if b)[:300]

    tags: list[str] = []
    if class_num is not None:
        tags.append(f"class-{class_num}")

    return make_feature(
        feature_id=feature_id,
        name=name,
        lat=lat,
        lon=lon,
        category="geo-site",
        source=SOURCE,
        source_url=SITE_URL,
        features=tags,
        description=description,
    )


def main():
    written: list[pathlib.Path] = []
    for type_name, layer_id, sublabel in LAYERS:
        print(f"  fetching {type_name}")
        body = _wfs_get(type_name)
        features: list[dict] = []
        for row in body.get("features", []):
            feat = _feature_from(row, layer_id, sublabel)
            if feat:
                features.append(feat)
        print(f"    {len(features)} -> {layer_id}.geojson")
        written.append(write_layer(layer_id, SOURCE, SITE_URL, features))

    # Drop the legacy combined file from earlier iterations so the
    # frontend never sees a stale 2782-point layer.
    legacy = LAYERS_DIR / "geo-sites.geojson"
    if legacy.exists():
        legacy.unlink()
        print(f"  removed legacy {legacy.name}")

    return written


if __name__ == "__main__":
    sys.exit(run(main, name="geo-sites"))
