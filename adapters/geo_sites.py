"""Adapter for nationally valuable geological sites (SYKE).

SYKE publishes four "nationally valuable" geological-formation
inventories as a single WFS workspace
(``syke_geologisetmuodostumat``). Each is a polygon layer; we emit a
point per polygon (bbox centroid) since the user-facing intent is "go
visit this spot".

Layers (counts approximate as of 2026):

* Arvokkaat_kallioalueet              - bedrock / cliff areas       (~1286)
* Arvokkaat_kivikot                   - boulder / scree fields      (~472)
* Arvokkaat_moreenimuodostumat        - moraine formations          (~607)
* Arvokkaat_tuuli_ja_rantakerrostumat - eolian + shore deposits     (~417)

``arvoluokka`` (value class) ranges 1 (highest) - 7. ``selitearvoluokka``
holds the human-readable label, which we surface in the popup.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

from common import make_feature, polygon_bbox_centroid, run, write_layer

NAME = "geo-sites"
SOURCE = "SYKE: nationally valuable geological formations"
SITE_URL = "https://www.syke.fi/avointieto"
WFS_URL = "https://paikkatiedot.ymparisto.fi/geoserver/syke_geologisetmuodostumat/wfs"

# typeName -> (subcategory key, English label, marker subtype shown in popup)
LAYERS = [
    ("Arvokkaat_kallioalueet",              "bedrock",  "Bedrock area"),
    ("Arvokkaat_kivikot",                   "kivikko",  "Boulder field"),
    ("Arvokkaat_moreenimuodostumat",        "moraine",  "Moraine formation"),
    ("Arvokkaat_tuuli_ja_rantakerrostumat", "eolian",   "Wind / shore deposit"),
]


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


def _feature_from(row: dict, subkey: str, sublabel: str) -> dict | None:
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
    feature_id = f"{subkey}-{tunnus}"

    value_label = (props.get("selitearvoluokka") or "").strip()
    bits = [sublabel]
    if value_label:
        bits.append(value_label)
    if props.get("lisatieto"):
        bits.append(str(props["lisatieto"]).strip())
    description = " . ".join(b for b in bits if b)[:300]

    return make_feature(
        feature_id=feature_id,
        name=name,
        lat=lat,
        lon=lon,
        category="geo-site",
        source=SOURCE,
        source_url=SITE_URL,
        features=[subkey],
        description=description,
    )


def fetch_features() -> list[dict]:
    out: list[dict] = []
    for type_name, subkey, sublabel in LAYERS:
        print(f"  fetching {type_name}")
        body = _wfs_get(type_name)
        n0 = len(out)
        for row in body.get("features", []):
            feat = _feature_from(row, subkey, sublabel)
            if feat:
                out.append(feat)
        print(f"    +{len(out) - n0}")
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
