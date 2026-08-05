"""Adapter for tree species composition by region (Luke NFI 13/14).

Luke's National Forest Inventory publishes total standing volume (growing
stock) broken down into four species groups - pine, spruce, birch, and
other broadleaved - via the PxWeb statistics API, aggregated per maakunta
(region). This is coarser than the MVMI raster (16m grid, per-species
m3/ha) that Luke also publishes, but the raster's volume layers are not
WMS-queryable and are only distributed as GeoTIFF, which would need a
raster library (rasterio/GDAL) outside this project's stdlib-only
convention. The PxWeb table stays inside that constraint and maps 1:1
onto the 19 maakuntas already defined in common.py.

Table: 1.16 "Puuston tilavuus metsa- ja kitumaalla puulajeittain"
(Growing stock volume on forest land and poorly productive forest land
by tree species), inventory NFI 13/14 (2020-2024).
"""

from __future__ import annotations

import json
import sys
import urllib.request

from common import REGIONS, make_feature, run, write_layer

NAME = "tree-species"
SOURCE = "Luke: National Forest Inventory (NFI 13/14, 2020-2024), table 1.16"
SITE_URL = "https://www.luke.fi/en/statistics/forest-resources/results-of-the-national-forest-inventory"
API = (
    "https://statdb.luke.fi/PXWeb/api/v1/en/LUKE/met/zzz_lak/"
    "06%20Metsavarat/1.16_Puuston_tilavuus_metsa_ja_kitumaalla_pu.px"
)

# maakunta region codes (excludes the "1"/"1.1"/"1.2" whole-country and
# Southern/Northern Finland aggregates) mapped to the canonical Finnish
# region names used everywhere else in this project (common.REGIONS).
REGION_CODE_TO_NAME = {
    "1.1.1": "Uusimaa",
    "1.1.2": "Varsinais-Suomi",
    "1.1.3": "Satakunta",
    "1.1.4": "Kanta-Häme",
    "1.1.5": "Pirkanmaa",
    "1.1.6": "Päijät-Häme",
    "1.1.7": "Kymenlaakso",
    "1.1.8": "Etelä-Karjala",
    "1.1.9": "Etelä-Savo",
    "1.1.10": "Pohjois-Savo",
    "1.1.11": "Pohjois-Karjala",
    "1.1.12": "Keski-Suomi",
    "1.1.13": "Etelä-Pohjanmaa",
    "1.1.14": "Pohjanmaa",
    "1.1.15": "Keski-Pohjanmaa",
    "1.2.17": "Pohjois-Pohjanmaa",
    "1.2.18": "Kainuu",
    "1.2.19": "Lappi",
    "1.1.21": "Ahvenanmaa",
}

SPECIES_CODE_TO_SLUG = {
    "Mänty": "pine",
    "Kuusi": "spruce",
    "Koivu": "birch",
    "Muut lehtipuut": "other-broadleaved",
}
SPECIES_SLUG_TO_LABEL = {
    "pine": "Pine",
    "spruce": "Spruce",
    "birch": "Birch",
    "other-broadleaved": "Other broadleaved",
}
SPECIES_ORDER = ("pine", "spruce", "birch", "other-broadleaved")

INVENTORY_CODE = "14"  # NFI 13/14 (2020-2024), the latest published


def _fetch_json_stat() -> dict:
    query = {
        "query": [
            {"code": "inventointi", "selection": {"filter": "item", "values": [INVENTORY_CODE]}},
            {"code": "maakunta", "selection": {"filter": "item", "values": list(REGION_CODE_TO_NAME)}},
            {"code": "puulaji", "selection": {"filter": "item", "values": list(SPECIES_CODE_TO_SLUG)}},
        ],
        "response": {"format": "json-stat2"},
    }
    body = json.dumps(query).encode("utf-8")
    req = urllib.request.Request(
        API,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "nature-aggregator/0.1"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _region_centroid(name: str) -> tuple[float, float] | None:
    for rname, rlat, rlon in REGIONS:
        if rname == name:
            return (rlat, rlon)
    return None


def fetch_features() -> list[dict]:
    print("  fetching Luke NFI table 1.16 (tree species volume by region)")
    data = _fetch_json_stat()

    region_index = data["dimension"]["maakunta"]["category"]["index"]
    species_index = data["dimension"]["puulaji"]["category"]["index"]
    n_species = len(species_index)
    values = data["value"]

    out: list[dict] = []
    for region_code, region_name in REGION_CODE_TO_NAME.items():
        region_pos = region_index[region_code]
        centroid = _region_centroid(region_name)
        if centroid is None:
            continue
        lat, lon = centroid

        volumes: dict[str, float] = {}
        for species_code, slug in SPECIES_CODE_TO_SLUG.items():
            species_pos = species_index[species_code]
            flat_index = region_pos * n_species + species_pos
            volumes[slug] = values[flat_index]

        total = sum(volumes.values())
        if total <= 0:
            continue
        shares = {slug: round(v / total * 100) for slug, v in volumes.items()}
        dominant_slug = max(volumes, key=volumes.get)

        bits = [f"{SPECIES_SLUG_TO_LABEL[slug]} {shares[slug]}%" for slug in SPECIES_ORDER]
        description = (
            " · ".join(bits)
            + f" of {round(total, 1)} million m³ growing stock (NFI 13/14, 2020-2024)"
        )

        feature = make_feature(
            feature_id=f"tree-species-{region_name.lower().replace(' ', '-')}",
            name=f"{region_name}: {SPECIES_SLUG_TO_LABEL[dominant_slug].lower()}-dominant",
            lat=lat,
            lon=lon,
            category="tree-species",
            source=SOURCE,
            source_url=SITE_URL,
            features=[f"dominant-{dominant_slug}"],
            description=description,
            region=region_name,
        )
        if feature:
            feature["properties"]["species_million_m3"] = {
                slug: round(v, 1) for slug, v in volumes.items()
            }
            feature["properties"]["species_pct"] = shares
            feature["properties"]["total_million_m3"] = round(total, 1)
            feature["properties"]["dominant_species"] = dominant_slug
            out.append(feature)
    if len(out) != len(REGION_CODE_TO_NAME):
        raise RuntimeError(
            f"expected {len(REGION_CODE_TO_NAME)} regions, got {len(out)} - "
            "a region was silently dropped (missing centroid or zero volume)"
        )
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
