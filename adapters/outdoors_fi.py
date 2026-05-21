"""Adapter for Finnish national parks, wilderness areas, and nature reserves.

Source: SYKE / Metsahallitus "Luonnonsuojelu- ja eramaa-alueet" open data,
catalogued at avoindata.suomi.fi. The underlying spatial service is a
GeoServer WFS at https://paikkatiedot.ymparisto.fi/geoserver/inspire_ps/wfs
which serves GeoJSON when asked. We pull three feature subsets and emit
them as **three separate layers** so the frontend can toggle them
independently:

* ``national-parks.geojson``: typeNames=...ValtionOmistamaLuonnonsuojelualue
  with a CQL filter picking only kohdetyyppi codes for KPU
  ("Kansallispuisto") and KPM ("Kansallispuisto - other custodian").
  Matches the 41 NPs listed on luontoon.fi (plus 1 KPM-custodian park).
* ``wilderness-areas.geojson``: typeNames=...EramaaAlue (the 12 eramaa
  alueet -- Finland's statutory wilderness areas in Lappi).
* ``nature-reserves.geojson``: typeNames=...ValtionOmistamaLuonnonsuojelualue
  filtered to **everything that isn't a national park** -- ESA (other
  conservation areas), SSA (mire reserves), VMA (old-growth forest), LHA
  (herb-rich forest), LPU (strict nature reserves), HYL and MHA. ~1050
  polygons total; we drop anything below ``RESERVE_MIN_AREA_KM2`` and
  apply heavier coordinate simplification to keep the layer file small
  enough to ship over HTTP without compression.

Each polygon comes through with attributes including nimi (name),
tyyppinimi (type label), lpalue (region), and paaturl (link to source).

Note on retkikartta.fi: its data backend is Metsahallitus's internal
ArcGIS REST and the layers are not openly published. The SYKE WFS used
here is the closest open equivalent and covers the same conservation
polygons (parks, wilderness, reserves) but not the recreational overlays
(trails, huts, services) that retkikartta layers on top. Trails / huts
come from laavu.org instead.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request

from common import make_polygon_feature, polygon_bbox_centroid, region_for, run, write_layer

NAME = "outdoors-fi"  # adapter identifier for logs; produces three layer files
LAYER_NP = "national-parks"
LAYER_WILDERNESS = "wilderness-areas"
LAYER_RESERVES = "nature-reserves"
SOURCE = "SYKE / Metsahallitus open data (luonnonsuojelu-ja-eramaa-alueet)"
SITE_URL = "https://avoindata.suomi.fi/data/en_GB/dataset/luonnonsuojelu-ja-eramaa-alueet"
WFS_BASE = "https://paikkatiedot.ymparisto.fi/geoserver/inspire_ps/wfs"

# Drop reserve polygons smaller than this. There are ~1050 non-NP
# conservation polygons in total; ~500 are >= 1 km^2 and that subset
# already covers the substantively important reserves without dragging
# in dozens of tiny LHA / SSA fragments.
RESERVE_MIN_AREA_KM2 = 1.0

# Friendly labels for the SYKE type-code abbreviations on non-NP polygons.
RESERVE_TYPE_LABELS = {
    "ESA": "Other conservation area",
    "SSA": "Mire reserve",
    "VMA": "Old-growth forest reserve",
    "LHA": "Herb-rich forest reserve",
    "LPU": "Strict nature reserve",
    "HYL": "Other conservation area",
    "MHA": "MH-decision conservation area",
}

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
    if code in RESERVE_TYPE_LABELS:
        return "nature-reserve"
    if "kansallispuisto" in (tyyppi_nimi or "").lower():
        return "national-park"
    if "eramaa" in (tyyppi_nimi or "").lower() or "erämaa" in (tyyppi_nimi or "").lower():
        return "wilderness-area"
    return "nature-reserve"


def _region_for(props: dict, geometry: dict) -> str:
    centroid = polygon_bbox_centroid(geometry)
    if centroid:
        return region_for(*centroid)
    return ""


def _description(props: dict) -> str:
    """One row per fact: type (for reserves), IUCN class, established year,
    plus any lisatieto.

    'voimaantulopvm' is the effective date of the most recent administrative
    law (every park currently reads 2023-06-01 from a 2023 reform), so we
    use 'paatpvm' for the original founding decision instead. The 9999-12-31
    sentinel SYKE uses for "unknown / pending" is filtered out.
    """
    bits = []
    type_code = (props.get("tyyppilyhenne") or "").upper()
    type_label = RESERVE_TYPE_LABELS.get(type_code)
    if type_label:
        bits.append(f"Type: {type_label}")
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
    area_m2 = props.get("shape_area") or 0
    if area_m2 and area_m2 >= 1_000_000:
        bits.append(f"Area: {area_m2 / 1_000_000:.1f} km²")
    extra = (props.get("lisatieto") or "").strip()
    if extra:
        bits.append(extra)
    return " · ".join(bits)


def _ingest(geo: dict, *, simplify: tuple[int, float] = (4, 0.001), min_area_km2: float = 0.0) -> list[dict]:
    """Convert raw SYKE features into our common schema.

    ``simplify`` is (coord_precision, min_step) passed through to
    make_polygon_feature. Reserves use heavier simplification because
    there are 1000+ of them. ``min_area_km2`` drops polygons below the
    threshold (their bbox / SYKE-reported area, whichever is available).
    """
    out: list[dict] = []
    precision, min_step = simplify
    for feat in geo.get("features", []):
        props = feat.get("properties") or {}
        if (props.get("olotila") or "").lower() and "voimassa" not in (props.get("olotila") or "").lower():
            continue  # skip non-active records
        if min_area_km2 > 0:
            area_m2 = props.get("shape_area") or 0
            if area_m2 and area_m2 < min_area_km2 * 1_000_000:
                continue
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
            coord_precision=precision,
            min_step=min_step,
        )
        if f:
            out.append(f)
    return out


def fetch_features() -> tuple[list[dict], list[dict], list[dict]]:
    """Return (national_parks, wilderness_areas, nature_reserves)."""
    override = os.environ.get("NATURE_OUTDOORS_GEOJSON")
    if override:
        # Override path is single-file by design (for offline testing). Split
        # the ingested features on category so the same override still gives
        # us the layers downstream.
        req = urllib.request.Request(override, headers={"User-Agent": "nature-aggregator/0.1"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            geo = json.loads(resp.read())
        feats = _ingest(geo)
        np = [f for f in feats if f["properties"]["category"] == "national-park"]
        wd = [f for f in feats if f["properties"]["category"] == "wilderness-area"]
        rs = [f for f in feats if f["properties"]["category"] == "nature-reserve"]
        return np, wd, rs

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

    print(
        f"  fetching nature reserves via WFS (NOT KPU/KPM, >= {RESERVE_MIN_AREA_KM2} km²)"
    )
    rs = _wfs_query(
        "inspire_ps:PS.ProtectedSitesValtionOmistamaLuonnonsuojelualue",
        cql_filter="tyyppilyhenne NOT IN ('KPU','KPM')",
    )
    rs_feats = _ingest(rs, simplify=(3, 0.005), min_area_km2=RESERVE_MIN_AREA_KM2)
    print(f"    {len(rs_feats)} nature reserves after filtering")

    return np_feats, em_feats, rs_feats


def main():
    np_feats, wd_feats, rs_feats = fetch_features()
    paths = []
    paths.append(write_layer(LAYER_NP, SOURCE, SITE_URL, np_feats))
    paths.append(write_layer(LAYER_WILDERNESS, SOURCE, SITE_URL, wd_feats))
    paths.append(write_layer(LAYER_RESERVES, SOURCE, SITE_URL, rs_feats))
    return paths


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
