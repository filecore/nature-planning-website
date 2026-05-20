"""Adapter for Finnish public swimming beaches (EU Bathing Water Directive).

Source: SYKE GeoServer at
``https://paikkatiedot.ymparisto.fi/geoserver/inspire_am2/wfs``, feature
type ``AM.BathingWaters``. Same hosting pattern as the national-parks
adapter, different namespace (``inspire_am2`` instead of
``inspire_ps``).

The dataset covers every officially monitored bathing site in Finland
under the EU Bathing Water Directive: roughly 437 beaches, both
freshwater (``uimavesityyppi=1``) and coastal (``uimavesityyppi=2``),
across LK (Large, >100 visitors) and SUK (Small) categories.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

from common import make_feature, run, write_layer

NAME = "beaches"
SOURCE = "SYKE EU Bathing Water Directive (uimavesidirektiivi)"
SITE_URL = "https://avoindata.suomi.fi/data/en_GB/dataset/uimavesidirektiivin-mukaiset-uimavedet"
WFS_URL = "https://paikkatiedot.ymparisto.fi/geoserver/inspire_am2/wfs"


def _wfs_query() -> dict:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": "inspire_am2:AM.BathingWaters",
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "count": "5000",
    }
    url = WFS_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "nature-aggregator/0.1"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _category(props: dict) -> str:
    """Coastal vs freshwater, big vs small. Two-letter codes in the source."""
    water_type = props.get("uimavesityyppi")
    size = (props.get("uimavesikategoria") or "").upper()
    base = "beach-coastal" if water_type == 2 else "beach-freshwater"
    return base + ("-small" if size == "SUK" else "")


def _description(props: dict) -> str:
    bits: list[str] = []
    water_type = props.get("uimavesityyppi")
    if water_type == 2:
        bits.append("Coastal bathing water")
    elif water_type == 1:
        bits.append("Freshwater bathing water")
    cat = (props.get("uimavesikategoria") or "").upper()
    if cat == "LK":
        bits.append("EU-regulated (large, >100 visitors)")
    elif cat == "SUK":
        bits.append("Small bathing site")
    huom = (props.get("huom") or "").strip()
    if huom and huom.lower() != "na":
        bits.append(huom)
    return ". ".join(bits)


def _coords(geom: dict, props: dict) -> tuple[float, float] | None:
    """Prefer WGS84 columns in properties; fall back to MultiPoint geometry."""
    try:
        lon = float(props.get("koorderlong"))
        lat = float(props.get("koorderlat"))
        if lat and lon:
            return lat, lon
    except (TypeError, ValueError):
        pass
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "Point" and coords:
        return float(coords[1]), float(coords[0])
    if gtype == "MultiPoint" and coords:
        return float(coords[0][1]), float(coords[0][0])
    return None


def fetch_features() -> list[dict]:
    override = os.environ.get("NATURE_BEACHES_GEOJSON")
    if override:
        req = urllib.request.Request(override, headers={"User-Agent": "nature-aggregator/0.1"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            geo = json.loads(resp.read())
    else:
        print(f"  fetching BathingWaters from {WFS_URL}")
        geo = _wfs_query()

    out: list[dict] = []
    for feat in geo.get("features", []):
        props = feat.get("properties") or {}
        if not props:
            continue
        coord = _coords(feat.get("geometry") or {}, props)
        if not coord:
            continue
        lat, lon = coord

        name = (props.get("uimavesinimi") or props.get("uimavesilyhytnimi") or "").strip() or "(unnamed)"
        feature_id = "beach-" + str(props.get("uimavesitunnus") or props.get("objectid") or name)

        f = make_feature(
            feature_id=feature_id,
            name=name,
            lat=lat,
            lon=lon,
            category=_category(props),
            source=SOURCE,
            source_url=SITE_URL,
            features=[],
            description=_description(props),
        )
        if f:
            out.append(f)
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
