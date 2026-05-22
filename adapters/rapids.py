"""Adapter for Finnish river rapids (OpenStreetMap via Overpass).

Waterfalls (vesiputoukset) are already covered by ``suomenvesiputoukset.fi``,
but the much larger set of *kosket* (river rapids / -niva / -koski) was
missing. kosket.fi is a parked domain, so OSM's ``waterway=rapids`` tag
is the cleanest open source - 600+ entries across Finland, with most of
the named ones (Nukarinkoski, Ruutinkoski, etc.) already tagged.

Unnamed rapids are skipped: a marker with no name is just clutter.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

from common import make_feature, run, write_layer

NAME = "rapids"
SOURCE = "OpenStreetMap (waterway=rapids)"
SITE_URL = "https://www.openstreetmap.org/"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

QUERY = """
[out:json][timeout:180];
area["ISO3166-1"="FI"][admin_level=2]->.fi;
(
  node["waterway"="rapids"](area.fi);
  way["waterway"="rapids"](area.fi);
);
out center tags;
""".strip()


def _osm_browse_url(el: dict) -> str:
    t = el.get("type")
    i = el.get("id")
    if t and i:
        return f"https://www.openstreetmap.org/{t}/{i}"
    return SITE_URL


def fetch_features() -> list[dict]:
    data = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={"User-Agent": "nature-aggregator/0.1"},
        method="POST",
    )
    print(f"  POST {OVERPASS_URL}")
    with urllib.request.urlopen(req, timeout=240) as resp:
        body = json.loads(resp.read())

    out: list[dict] = []
    seen: set[str] = set()
    for el in body.get("elements", []):
        tags = el.get("tags") or {}
        name = (tags.get("name") or tags.get("name:fi") or tags.get("name:en") or "").strip()
        if not name:
            continue
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue

        osm_id = f"{el.get('type','node')}-{el.get('id','')}"
        if osm_id in seen:
            continue
        seen.add(osm_id)

        bits = ["Rapids"]
        if tags.get("name:sv") and tags.get("name:sv") != name:
            bits.append(f"sv: {tags['name:sv']}")
        if tags.get("description"):
            bits.append(tags["description"].strip())
        if (tags.get("whitewater") or tags.get("canoe")):
            bits.append("paddleable")
        description = " . ".join(bits)[:300]

        tags_list = ["rapids"]
        if (tags.get("whitewater") or tags.get("canoe")):
            tags_list.append("paddleable")

        feature = make_feature(
            feature_id=f"osm-{osm_id}",
            name=name,
            lat=float(lat),
            lon=float(lon),
            category="rapids",
            source=SOURCE,
            source_url=_osm_browse_url(el),
            features=tags_list,
            description=description,
        )
        if feature:
            out.append(feature)
    print(f"  {len(out)} named rapids")
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
