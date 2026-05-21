"""Adapter for Finnish national parks and hiking areas.

Source: SYKE / Metsahallitus "Luonnonsuojelu- ja eramaa-alueet" open data,
catalogued at avoindata.suomi.fi. The underlying spatial service is a
GeoServer WFS at https://paikkatiedot.ymparisto.fi/geoserver/inspire_ps/wfs
which serves GeoJSON when asked. We pull two feature subsets and emit them
as **two separate layers** so the frontend can toggle them independently:

* ``national-parks.geojson``: typeNames=...ValtionOmistamaLuonnonsuojelualue
  with a CQL filter picking only kohdetyyppi codes for KPU
  ("Kansallispuisto") and KPM ("Kansallispuisto - other custodian").
  Matches the 41 NPs listed on luontoon.fi (plus 1 KPM-custodian park).
* ``hiking-areas.geojson``: typeNames=...EramaaAlue (the 12 wilderness
  areas, the other major Metsahallitus hiking destination type).

Each polygon comes through with attributes including nimi (name),
tyyppinimi (type label), lpalue (region), and paaturl (link to source).
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request

from common import make_polygon_feature, polygon_bbox_centroid, region_for, run, write_layer

NAME = "outdoors-fi"  # adapter identifier for logs; produces two layer files
LAYER_NP = "national-parks"
LAYER_HIKING = "hiking-areas"
SOURCE = "SYKE / Metsahallitus open data (luonnonsuojelu-ja-eramaa-alueet)"
SITE_URL = "https://avoindata.suomi.fi/data/en_GB/dataset/luonnonsuojelu-ja-eramaa-alueet"
WFS_BASE = "https://paikkatiedot.ymparisto.fi/geoserver/inspire_ps/wfs"

# Note: SYKE's 'lpalue' field is the Metsähallitus *service area* name, not
# a maakunta. 'Rannikko, LP' covers Uusimaa + Varsinais-Suomi + Kymenlaakso
# in one bucket, so mapping it to any single maakunta is wrong (Nuuksio
# and Sipoonkorpi previously got tagged 'Varsinais-Suomi' that way). We
# now rely on the polygon bbox centroid + region_for() exclusively.


def _wfs_query(type_names: str, cql_filter: str | None = None) -> dict:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": type_names,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "count": "1000",
    }
    if cql_filter:
        params["CQL_FILTER"] = cql_filter
    url = WFS_BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "nature-aggregator/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _category_for(tyyppi_lyhenne: str | None, tyyppi_nimi: str | None) -> str:
    code = (tyyppi_lyhenne or "").upper()
    if code == "EMA":
        return "wilderness-area"
    if code in ("KPU", "KPM"):
        return "national-park"
    if "kansallispuisto" in (tyyppi_nimi or "").lower():
        return "national-park"
    if "eramaa" in (tyyppi_nimi or "").lower() or "erämaa" in (tyyppi_nimi or "").lower():
        return "wilderness-area"
    return "protected-area"


def _region_for(props: dict, geometry: dict) -> str:
    centroid = polygon_bbox_centroid(geometry)
    if centroid:
        return region_for(*centroid)
    return ""


def _description(props: dict) -> str:
    """One row per fact: IUCN class, established year, plus any lisatieto.

    'voimaantulopvm' is the effective date of the most recent administrative
    law (every park currently reads 2023-06-01 from a 2023 reform), so we
    use 'paatpvm' for the original founding decision instead. The 9999-12-31
    sentinel SYKE uses for "unknown / pending" is filtered out.
    """
    bits = []
    if props.get("iucnluokkanimi"):
        bits.append(f"IUCN: {props['iucnluokkanimi']}")
    for date_field in ("paatpvm", "voimaantulopvm"):
        raw = props.get(date_field) or ""
        if not raw or raw.startswith("9999"):
            continue
        match = re.match(r"(\d{4})", raw)
        if match:
            bits.append(f"Established: {match.group(1)}")
            break
    extra = (props.get("lisatieto") or "").strip()
    if extra:
        bits.append(extra)
    return " · ".join(bits)


def _ingest(geo: dict) -> list[dict]:
    out: list[dict] = []
    for feat in geo.get("features", []):
        props = feat.get("properties") or {}
        if (props.get("olotila") or "").lower() and "voimassa" not in (props.get("olotila") or "").lower():
            continue  # skip non-active records
        name = (props.get("nimi") or "").strip() or "(unnamed)"
        cat = _category_for(props.get("tyyppilyhenne"), props.get("tyyppinimi"))
        feature_id = "mh-" + str(props.get("kohdeid") or props.get("lsaluetunnus") or re.sub(r"[^a-z0-9]+", "-", name.lower())[:60])

        # Best-effort source URL: prefer the law-reference link, fall back to the
        # outdoors.fi search page so users still get somewhere useful.
        link = props.get("paaturl")
        if not link:
            slug = re.sub(r"[^a-z0-9]+", "", name.lower())
            link = f"https://www.outdoors.fi/?q={urllib.parse.quote(name)}"

        f = make_polygon_feature(
            feature_id=feature_id,
            name=name,
            geometry=feat["geometry"],
            category=cat,
            source=SOURCE,
            source_url=link,
            features=[],  # service amenities are not in this dataset
            description=_description(props),
            region=_region_for(props, feat["geometry"]),
        )
        if f:
            out.append(f)
    return out


def fetch_features() -> tuple[list[dict], list[dict]]:
    """Return (national_parks, hiking_areas) feature lists."""
    override = os.environ.get("NATURE_OUTDOORS_GEOJSON")
    if override:
        # Override path is single-file by design (for offline testing). Split
        # the ingested features on category so the same override still gives
        # us the two layers downstream.
        req = urllib.request.Request(override, headers={"User-Agent": "nature-aggregator/0.1"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            geo = json.loads(resp.read())
        feats = _ingest(geo)
        np = [f for f in feats if f["properties"]["category"] == "national-park"]
        hk = [f for f in feats if f["properties"]["category"] == "wilderness-area"]
        return np, hk

    print("  fetching national parks via WFS (CQL filter for KPU/KPM)")
    np = _wfs_query(
        "inspire_ps:PS.ProtectedSitesValtionOmistamaLuonnonsuojelualue",
        cql_filter="tyyppilyhenne IN ('KPU','KPM')",
    )
    np_feats = _ingest(np)
    print(f"    {len(np_feats)} national parks")

    print("  fetching wilderness areas via WFS")
    em = _wfs_query("inspire_ps:PS.ProtectedSitesEramaaAlue")
    em_feats = _ingest(em)
    print(f"    {len(em_feats)} wilderness areas")

    return np_feats, em_feats


def main():
    np_feats, hk_feats = fetch_features()
    paths = []
    paths.append(write_layer(LAYER_NP, SOURCE, SITE_URL, np_feats))
    paths.append(write_layer(LAYER_HIKING, SOURCE, SITE_URL, hk_feats))
    return paths


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
