"""Adapter for Finnish river rapids (OpenStreetMap via Overpass).

Waterfalls (vesiputoukset) are already covered by ``suomenvesiputoukset.fi``,
but the much larger set of *kosket* (river rapids / -niva / -koski) was
missing. kosket.fi is a parked domain, so OSM's ``waterway=rapids`` tag
is the cleanest open source - 600+ entries across Finland, with most of
the named ones already tagged.

Unnamed rapids are skipped: a marker with no name is just clutter.
Notable rapids not yet tagged in OSM live in
``data/manual/rapids.csv`` (same Google Maps URL format as caves.csv)
and are merged in on top.
"""

from __future__ import annotations

import csv
import io
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request

from common import make_feature, run, write_layer

NAME = "rapids"
SOURCE = "OpenStreetMap (waterway=rapids) + manual supplements"
SITE_URL = "https://www.openstreetmap.org/"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
MANUAL_CSV = pathlib.Path(__file__).resolve().parent.parent / "data" / "manual" / "rapids.csv"
_AT_COORD_RE = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)")

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


def _coord_from_url(url: str) -> tuple[float, float] | None:
    m = _AT_COORD_RE.search(url or "")
    if not m:
        return None
    try:
        return float(m.group(1)), float(m.group(2))
    except ValueError:
        return None


def manual_features() -> list[dict]:
    if not MANUAL_CSV.exists():
        return []
    text = MANUAL_CSV.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    out: list[dict] = []
    for row in reader:
        name = (row.get("Name") or "").strip()
        if not name:
            continue
        coord = _coord_from_url((row.get("Google Maps URL") or "").strip())
        if not coord:
            continue
        lat, lon = coord
        details = (row.get("Details") or "").strip()
        region = (row.get("Region") or "").strip() or None
        link = (row.get("Link") or "").strip() or SITE_URL
        bits = ["Rapids"]
        if details:
            bits.append(details)
        feat_id = "rapids-manual-" + re.sub(r"[^a-z0-9]+", "-", name.lower())[:60] + f"-{lat:.4f}-{lon:.4f}"
        f = make_feature(
            feature_id=feat_id,
            name=name,
            lat=lat,
            lon=lon,
            category="rapids",
            source=SOURCE,
            source_url=link,
            features=["rapids", "manual"],
            description=" . ".join(bits)[:300],
            region=region,
        )
        if f:
            out.append(f)
    print(f"  {len(out)} manual rapids merged")
    return out


def main():
    features = fetch_features()
    osm_names = {(f["properties"]["name"] or "").lower() for f in features}
    for m in manual_features():
        if (m["properties"]["name"] or "").lower() in osm_names:
            continue  # OSM already covers it
        features.append(m)
    return write_layer(NAME, SOURCE, SITE_URL, features)


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
