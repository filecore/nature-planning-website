"""Adapter for outdoor climbing crags (OpenStreetMap via Overpass).

Pulls OSM nodes and ways tagged ``sport=climbing`` or
``climbing=crag|boulder|route|route_bottom`` within Finland, filters
out indoor climbing gyms (anything with ``leisure=sports_centre``,
``building=*`` or ``indoor=yes``), and emits a point feature per crag
with the public OSM browse URL as the source link.

OSM has 200+ named outdoor climbing locations in Finland - bouldering
fields like Forte/Pesankallio, sport crags like Olhava, and trad/route
walls. Coverage isn't 100% (no open dataset is) but it's the best
free source for this category.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request

from common import make_feature, run, write_layer

NAME = "crags"
SOURCE = "OpenStreetMap (Overpass API)"
SITE_URL = "https://www.openstreetmap.org/"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

QUERY = """
[out:json][timeout:180];
area["ISO3166-1"="FI"][admin_level=2]->.fi;
(
  node["sport"="climbing"]["leisure"!="sports_centre"](area.fi);
  way["sport"="climbing"]["leisure"!="sports_centre"](area.fi);
  node["climbing"~"crag|boulder|route"](area.fi);
  way["climbing"~"crag|boulder|route"](area.fi);
);
out center tags;
""".strip()


def _osm_browse_url(el: dict) -> str:
    t = el.get("type")
    i = el.get("id")
    if t and i:
        return f"https://www.openstreetmap.org/{t}/{i}"
    return SITE_URL


def _is_indoor(tags: dict) -> bool:
    if tags.get("indoor") == "yes":
        return True
    if tags.get("building"):
        return True
    if tags.get("leisure") == "sports_centre":
        return True
    return False


def _label_subtype(tags: dict) -> str:
    c = (tags.get("climbing") or "").lower()
    if c == "crag":
        return "Crag"
    if c == "boulder":
        return "Bouldering"
    if c in ("route", "route_bottom"):
        return "Route"
    if tags.get("climbing:sport") == "yes":
        return "Sport climbing"
    if tags.get("climbing:boulder") == "yes":
        return "Bouldering"
    if tags.get("climbing:traditional") == "yes":
        return "Trad climbing"
    if tags.get("climbing:ice") == "yes":
        return "Ice climbing"
    if tags.get("climbing:toprope") == "yes":
        return "Top-rope"
    return "Climbing"


def _features_from_tags(tags: dict) -> list[str]:
    out: list[str] = []
    if tags.get("climbing:sport") == "yes":
        out.append("sport")
    if tags.get("climbing:boulder") == "yes" or tags.get("climbing") == "boulder":
        out.append("bouldering")
    if tags.get("climbing:traditional") == "yes":
        out.append("trad")
    if tags.get("climbing:ice") == "yes":
        out.append("ice")
    if tags.get("climbing:toprope") == "yes":
        out.append("top-rope")
    if tags.get("climbing:multipitch") == "yes":
        out.append("multi-pitch")
    return out


def fetch_features() -> list[dict]:
    data = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={"User-Agent": "nature-aggregator/0.1 (jason@togneri.net)"},
        method="POST",
    )
    print(f"  POST {OVERPASS_URL}")
    with urllib.request.urlopen(req, timeout=240) as resp:
        body = json.loads(resp.read())

    out: list[dict] = []
    seen: set[str] = set()
    for el in body.get("elements", []):
        tags = el.get("tags") or {}
        if _is_indoor(tags):
            continue
        name = (tags.get("name") or "").strip()
        if not name:
            continue
        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            center = el.get("center") or {}
            lat = center.get("lat")
            lon = center.get("lon")
        if lat is None or lon is None:
            continue

        osm_id = f"{el.get('type','node')}-{el.get('id','')}"
        if osm_id in seen:
            continue
        seen.add(osm_id)

        subtype = _label_subtype(tags)
        grade_bits = []
        for k in ("climbing:grade:uiaa", "climbing:grade:french", "climbing:grade:fb"):
            if tags.get(k):
                scheme = k.split(":")[-1]
                grade_bits.append(f"{scheme} {tags[k]}")
        bits = [subtype]
        if grade_bits:
            bits.append("Grades: " + ", ".join(grade_bits))
        if tags.get("description"):
            bits.append(tags["description"])
        description = " . ".join(bits)[:300]

        feat = make_feature(
            feature_id=f"osm-{osm_id}",
            name=name,
            lat=float(lat),
            lon=float(lon),
            category="crag",
            source=SOURCE,
            source_url=_osm_browse_url(el),
            features=_features_from_tags(tags),
            description=description,
        )
        if feat:
            out.append(feat)
    print(f"  {len(out)} crags after filtering")
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
