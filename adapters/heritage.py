"""Adapter for open-air museums and ruins.

Combines two Museovirasto WFS feature types (same GeoServer used by
archaeology.py, different layers):

* ``rky_piste``: Valtakunnallisesti merkittävät rakennetut
  kulttuuriympäristöt - nationally significant built-heritage points
  (~64 entries: church villages, ironworks, traditional sawmills,
  open-air museums, fortifications).
* ``maailmanperinto_piste``: World Heritage Sites in Finland (6
  entries: Suomenlinna, Old Rauma, Petäjävesi old church, Verla,
  Sammallahdenmäki burial cairns, Struve geodetic arc points).

We label each feature with the source category so the popup makes
clear which list it came from.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request

from common import make_feature, run, write_layer

NAME = "open-air-heritage"
SOURCE = "Museovirasto: built heritage + World Heritage points"
SITE_URL = "http://www.rky.fi/"
WFS_URL = "https://geoserver.museovirasto.fi/geoserver/rajapinta_suojellut/wfs"


def _wfs_query(type_name: str) -> dict:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": type_name,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "count": "5000",
    }
    url = WFS_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "nature-aggregator/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _strip(s):
    return (s or "").strip() if isinstance(s, str) else s


def _feature_from(row: dict, category: str, source_label: str) -> dict | None:
    geom = row.get("geometry") or {}
    if geom.get("type") != "Point":
        return None
    try:
        lon, lat = float(geom["coordinates"][0]), float(geom["coordinates"][1])
    except (KeyError, TypeError, ValueError, IndexError):
        return None

    props = {k: _strip(v) for k, v in (row.get("properties") or {}).items()}
    name = props.get("kohdenimi") or props.get("nimi") or props.get("kohde") or "(unnamed)"
    feature_id = f"{category}-{props.get('ID') or props.get('mjtunnus') or props.get('OBJECTID') or re.sub(r'[^a-z0-9]+','-',name.lower())[:40]}"

    bits = [source_label]
    if props.get("tyyppi"):
        bits.append(props["tyyppi"].rstrip(","))
    description = " · ".join(b for b in bits if b)

    link = props.get("url") or SITE_URL
    return make_feature(
        feature_id=feature_id,
        name=name,
        lat=lat,
        lon=lon,
        category=category,
        source=SOURCE,
        source_url=link,
        features=[],
        description=description[:300],
    )


def fetch_features() -> list[dict]:
    out: list[dict] = []
    print("  fetching rky_piste (built heritage)")
    body = _wfs_query("rajapinta_suojellut:rky_piste")
    for row in body.get("features", []):
        feat = _feature_from(row, "built-heritage", "Built heritage (RKY)")
        if feat:
            out.append(feat)
    print(f"    {len(out)} so far")

    print("  fetching maailmanperinto_piste (UNESCO World Heritage)")
    body = _wfs_query("rajapinta_suojellut:maailmanperinto_piste")
    n0 = len(out)
    for row in body.get("features", []):
        feat = _feature_from(row, "world-heritage", "UNESCO World Heritage")
        if feat:
            out.append(feat)
    print(f"    {len(out)-n0} new")
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
