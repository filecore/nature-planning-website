"""Adapter for bird-watching hotspots (OpenStreetMap via Overpass).

eBird and BirdLife both require API keys and have restrictive
license terms. OpenStreetMap's ``leisure=bird_hide`` tag (and the
related observation-tower tags) is the cleanest open source for
"places hikers go to watch birds" - covers public lintutornit, kojuja
and observation platforms across Finland.

Query: any node or way tagged ``leisure=bird_hide``, plus generic
observation towers explicitly marked as for birds, plus tourism
information boards labelled ``birding``. Abandoned hides are skipped.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request

from common import make_feature, run, write_layer

NAME = "bird-hotspots"
SOURCE = "OpenStreetMap (bird hides + observation towers)"
SITE_URL = "https://www.openstreetmap.org/"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

QUERY = """
[out:json][timeout:180];
area["ISO3166-1"="FI"][admin_level=2]->.fi;
(
  node["leisure"="bird_hide"](area.fi);
  way["leisure"="bird_hide"](area.fi);
  node["tower:type"="observation"]["bird"="yes"](area.fi);
  node["tourism"="information"]["information"="birding"](area.fi);
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
        if tags.get("abandoned") == "yes" or tags.get("disused") == "yes":
            continue
        name = (tags.get("name") or tags.get("name:en") or "").strip()
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

        bits = ["Bird hide / observation tower"]
        if tags.get("description"):
            bits.append(tags["description"].strip())
        if tags.get("access"):
            bits.append(f"Access: {tags['access']}")
        if tags.get("opening_hours"):
            bits.append(f"Open: {tags['opening_hours']}")
        description = " . ".join(bits)[:300]

        tags_list = ["bird-hide"]
        if tags.get("man_made") == "tower":
            tags_list.append("tower")
        if (tags.get("wheelchair") or "").lower() == "yes":
            tags_list.append("accessible")

        feature = make_feature(
            feature_id=f"osm-{osm_id}",
            name=name,
            lat=float(lat),
            lon=float(lon),
            category="bird-hotspot",
            source=SOURCE,
            source_url=_osm_browse_url(el),
            features=tags_list,
            description=description,
        )
        if feature:
            out.append(feature)
    print(f"  {len(out)} bird hotspots")
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
