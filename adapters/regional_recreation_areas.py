"""Adapter for regional-plan recreation areas (maakuntakaava, kaavamerkinta V).

Finland's regional councils (maakuntaliitot) each publish a harmonised
regional land-use plan under the shared "HAME data model", served as WFS
from a per-region GeoServer workspace at
``geoserver.lounaistieto.fi/geoserver/hame_<region>/ows``. The
"virkistysalue" (recreation area) zoning code - roughly Finland's closest
national-scale answer to "ulkoilualue" as a land-use designation, rather
than a nature-conservation one - is one attribute value (kaavaMerkL LIKE
'V%') on a generic "area reservations" (Aluevaraukset) layer that also
carries every other zoning category (housing, industry, roads, ...).

This is why the Natura 2000 layer (natura-2000.geojson) alone does not
capture everywhere people go hiking: a large multi-use recreation area
can be zoned "V" in its region's plan without being a nature reserve or a
Natura site at all.

IMPORTANT - this coverage is genuinely incomplete, not a bug:

* Two regions publish no HAME-model data here at all: Pohjois-Pohjanmaa,
  Ahvenanmaa.
* Three more publish only a small or unverified fragment rather than a
  full regional plan - most notably Uusimaa, whose dataset here is only
  one localised phase-plan (Ostersundom, near Helsinki) and does NOT
  include most of the region (e.g. Onkimaanjarvi near Karkkila, the case
  that prompted this adapter, is not covered). Kainuu and Etela-Pohjanmaa
  use the same unqualified layer-naming pattern as Uusimaa and are
  unverified, not confirmed complete.
* The other twelve regions use a "yhdistelma"/"yhdelma" (composite) named
  layer, which spot-checking (Kanta-Hame: 109 real, named recreation
  areas from a single region-wide "Maakuntakaava 2040") suggests is
  genuinely a full current regional plan - but this has only been
  directly verified for a sample, not all twelve.

Every region's dataset otherwise shares the same attribute schema
(kaavaMerkL, kohdeTunnus, kohteenNimi, kuvaus, kaavanNimi, voimaanPvm),
except Pohjanmaa, which uses the identical schema but with all-lowercase
field names - handled by _prop() trying both cases.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request

from common import make_polygon_feature, run, write_layer

NAME = "regional-recreation-areas"
SOURCE = "Regional councils' harmonised land-use plans (HAME data model) via Lounaistieto"
SITE_URL = "https://www.lounaistieto.fi/maakuntakaavat/"
GEOSERVER_BASE = "https://geoserver.lounaistieto.fi/geoserver"

# (workspace, typeName, canonical maakunta name). Two of Finland's 19
# regions (Pohjois-Pohjanmaa, Ahvenanmaa) are absent from this service
# entirely and are not listed here. Where a region's workspace exposes
# several candidate "Aluevaraukset" layers, the one used below was picked
# by comparing feature counts across the candidates (see the adapter's
# module docstring / development notes) - not a formal quality signal
# from the source itself.
REGIONS = [
    ("hame_etela_karjala", "etela_karjala_yhdelma_aluevaraukset", "Etelä-Karjala"),
    ("hame_etela_pohjanmaa", "Aluevaraukset", "Etelä-Pohjanmaa"),
    ("hame_etela_savo", "etela_savo_maakuntakaavayhdistelma_aluevaraukset", "Etelä-Savo"),
    ("hame_kainuu", "Aluevaraukset", "Kainuu"),
    ("hame_kanta_hame", "kanta_hame_yhdelma_aluevaraukset", "Kanta-Häme"),
    ("hame_keski_pohjanmaa", "keski_pohjanmaa_yhdelma_aluevaraukset", "Keski-Pohjanmaa"),
    ("hame_keski_suomi", "keski_suomi_yhdelma_aluevaraukset", "Keski-Suomi"),
    ("hame_kymenlaakso", "kymenlaakso_aluevaraukset_kaavamaaraykset", "Kymenlaakso"),
    ("hame_lappi", "lappi_yhdelma_aluevaraukset", "Lappi"),
    ("hame_paijat_hame", "Aluevaraukset2023", "Päijät-Häme"),
    ("hame_pirkanmaa", "Aluevaraukset", "Pirkanmaa"),
    ("hame_pohjanmaa", "Aluevaraukset2050", "Pohjanmaa"),
    ("hame_pohjois_karjala", "pohjois_karjala_yhdelma_aluevaraukset2025", "Pohjois-Karjala"),
    ("hame_pohjois_savo", "pohjois_savo_yhdelma_aluevaraukset_virallinen", "Pohjois-Savo"),
    ("hame_satakunta", "satakunta_yhdelma_aluevaraukset_2021", "Satakunta"),
    ("hame_uusimaa", "Aluevaraukset", "Uusimaa"),
    ("hame_varsinais_suomi", "Aluevaraukset", "Varsinais-Suomi"),
]

# Recreation-area zoning codes are "V" (Virkistysalue) but regions append
# suffixes/compounds (VR, VU, VU/VR, "V 12.345", ...) rather than always
# using the bare code - matched with LIKE 'V%' rather than an exact filter.
CQL_FILTER = "kaavaMerkL LIKE 'V%'"


def _prop(props: dict, name: str):
    """Field lookup tolerant of Pohjanmaa's all-lowercase schema variant."""
    return props.get(name, props.get(name.lower()))


def _wfs_query(workspace: str, type_name: str) -> dict:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": f"{workspace}:{type_name}",
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "CQL_FILTER": CQL_FILTER,
        "count": "2000",
    }
    url = f"{GEOSERVER_BASE}/{workspace}/ows?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "nature-aggregator/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _description(props: dict) -> str:
    bits = []
    kuvaus = (_prop(props, "kuvaus") or "").strip()
    if kuvaus:
        bits.append(kuvaus)
    plan_name = (_prop(props, "kaavanNimi") or "").strip()
    if plan_name:
        bits.append(f"Plan: {plan_name}")
    raw = _prop(props, "voimaanPvm") or ""
    if raw and not raw.startswith("9999"):
        match = re.match(r"(\d{4})", raw)
        if match:
            bits.append(f"In force: {match.group(1)}")
    return " · ".join(bits)


def fetch_features() -> list[dict]:
    out: list[dict] = []
    for workspace, type_name, region_name in REGIONS:
        print(f"  fetching {region_name} recreation-area zoning via WFS ({workspace})")
        try:
            geo = _wfs_query(workspace, type_name)
        except Exception as e:
            print(f"    {region_name} FAILED, skipping ({e})")
            continue
        features = geo.get("features", [])
        region_out = 0
        for feat in features:
            props = feat.get("properties") or {}
            name = (_prop(props, "kohteenNimi") or "").strip() or "(unnamed)"
            kohde_id = _prop(props, "kohdeTunnus") or props.get("OBJECTID") or props.get("objectid")
            # kohdeTunnus is not reliably unique per feature in every region's
            # dataset (Pohjois-Savo reuses one kohdeTunnus across 14 distinct
            # named sites; Pirkanmaa reuses one across a site's disjoint
            # polygon parts) - OBJECTID is the row-level id GeoServer/ArcGIS
            # always assigns, so append it to guarantee a unique feature_id.
            objectid = props.get("OBJECTID") or props.get("objectid")
            feature_id = "maakuntakaava-" + workspace + "-" + str(kohde_id) + "-" + str(objectid)

            f = make_polygon_feature(
                feature_id=feature_id,
                name=name,
                geometry=feat["geometry"],
                category="regional-recreation-area",
                source=SOURCE,
                source_url=SITE_URL,
                features=[],
                description=_description(props),
                region=region_name,
                coord_precision=4,
                min_step=0.001,
            )
            if f:
                out.append(f)
                region_out += 1
        print(f"    {region_out} recreation areas")

    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
