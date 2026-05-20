"""Adapter for nationally significant Finnish archaeological sites (VARK).

Source: Museovirasto open data on GeoServer at
``https://geoserver.museovirasto.fi/geoserver/rajapinta_suojellut/wfs``.
The full ancient-monument register (``muinaisjaannos_piste``) carries
~41k points which is too many to ship as a single browser payload, so
we use the curated VARK subset (``vark_pisteet``, ~1010 points) of
nationally significant sites: kivikautinen asuinpaikka type stuff a
hiker would actually detour to see.

The legacy WFS at ``kartta.nba.fi`` was retired when Museovirasto
migrated to GeoServer in December 2023; the avoindata.suomi.fi CKAN
entry for that dataset still points at the dead URL.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request

from common import make_feature, run, write_layer

NAME = "archaeology"
SOURCE = "Museovirasto VARK (rajapinta_suojellut)"
SITE_URL = "https://www.kyppi.fi/"
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
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _category_for(tyyppi: str, ajoitus: str) -> str:
    t = (tyyppi or "").lower()
    if "hautap" in t or "hautar" in t:
        return "archaeology-burial"
    if "asuinp" in t:
        return "archaeology-settlement"
    if "kalliom" in t or "kallio m" in t or "kalliomaal" in t:
        return "archaeology-rock-art"
    if "linnav" in t or "fort" in t:
        return "archaeology-fort"
    if "kirkko" in t or "luostari" in t:
        return "archaeology-religious"
    if "valmistuspai" in t or "työpai" in t:
        return "archaeology-workshop"
    return "archaeology"


def _description(props: dict) -> str:
    """Two icon rows: 'Established: <period>' and 'Type: <typ>'."""
    period = (props.get("Ajoitus") or "").strip()
    period2 = (props.get("Ajoitus2") or "").strip()
    typ = (props.get("Tyyppi") or "").strip().rstrip(",")
    subtyp = (props.get("Alatyyppi") or "").strip().rstrip(",")

    bits: list[str] = []
    if period:
        bits.append("Established: " + period + (f" ({period2})" if period2 else ""))
    if typ:
        bits.append("Type: " + typ + (f" ({subtyp})" if subtyp and subtyp != "ei määritelty" else ""))
    return " · ".join(bits)


def _normalise_props(raw: dict) -> dict:
    """Strip the right-padding GeoServer leaves on character columns."""
    out = {}
    for k, v in raw.items():
        out[k] = v.strip() if isinstance(v, str) else v
    return out


def fetch_features() -> list[dict]:
    url_override = os.environ.get("NATURE_ARCHAEOLOGY_WFS")
    if url_override:
        # Test hook for a forked endpoint.
        req = urllib.request.Request(url_override, headers={"User-Agent": "nature-aggregator/0.1"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            geo = json.loads(resp.read())
    else:
        print(f"  fetching VARK feature collection from {WFS_URL}")
        geo = _wfs_query("rajapinta_suojellut:vark_pisteet")

    out: list[dict] = []
    for feat in geo.get("features", []):
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        try:
            lon = float(geom["coordinates"][0])
            lat = float(geom["coordinates"][1])
        except (KeyError, TypeError, ValueError, IndexError):
            continue

        props = _normalise_props(feat.get("properties") or {})
        name = props.get("VARK_nimi") or props.get("Mj_kohde") or "(unnamed)"
        link = props.get("Linkki") or SITE_URL
        region = props.get("Maakunta") or None  # already a Finnish maakunta name
        if region and region.lower().startswith("varsinais"):
            region = "Varsinais-Suomi"

        f = make_feature(
            feature_id="vark-" + str(props.get("VARK_ID") or props.get("Mj_tunnus") or name),
            name=name,
            lat=lat,
            lon=lon,
            category=_category_for(props.get("Tyyppi", ""), props.get("Ajoitus", "")),
            source=SOURCE,
            source_url=link,
            features=[],
            description=_description(props)[:300],
            region=region,
        )
        if f:
            out.append(f)
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
