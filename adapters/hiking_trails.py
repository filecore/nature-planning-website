"""Adapter for Finnish hiking trails (OpenStreetMap route=hiking relations).

OSM tags named, way-marked hiking routes as ``route=hiking`` relations -
everything from short local loops to multi-hundred-km regional routes like
Hameen Ilvesreitti (250 km, connects Liesjarvi and Torronsuo national
parks). This is the same Overpass API this project already uses for
crags.py and bird_hotspots.py.

Two-phase fetch, because a single "give me everything with geometry" query
for ~700+ relations nationwide is both slow and prone to the shared
Overpass instance's rate limiting / timeouts (observed directly while
building this adapter):

1. One lightweight tags-only query lists every route=hiking relation in
   Finland (fast, no geometry).
2. Geometry is then fetched in small batches of RELATIONS_PER_BATCH ids at
   a time, each batch retried with backoff on a 429/502/503/504, with a
   short pause between successful batches to stay polite to the shared
   server.

A route relation's members are not stitched into one continuous line -
each ``way`` member becomes one segment of a MultiLineString instead.
Adjacent segments still connect visually wherever they share an endpoint;
attempting to detect member order/direction and merge them into a single
LineString would add real complexity for a purely cosmetic difference on
a country-zoom map.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from common import make_line_feature, run, write_layer

NAME = "hiking-trails"
SOURCE = "OpenStreetMap contributors (route=hiking relations) via Overpass"
SITE_URL = "https://www.openstreetmap.org/"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

RELATIONS_PER_BATCH = 15
MAX_RETRIES = 6
RETRY_BACKOFF_BASE_S = 10
RETRY_BACKOFF_CAP_S = 120
PAUSE_BETWEEN_BATCHES_S = 8

NETWORK_LABELS = {
    "iwn": "International walking network",
    "nwn": "National walking network",
    "rwn": "Regional walking network",
    "lwn": "Local walking network",
    "lcn": "Local network",
}


def _overpass(query: str) -> dict:
    """POST to Overpass with retry+backoff.

    The shared public instance rate-limits (429) and times out (504) under
    load - observed directly while developing this adapter, hitting both
    within a single test run. Exponential backoff (10s, 20s, 40s, 80s,
    120s, 120s) with a generous retry count is the practical fix; a 429's
    ``Retry-After`` header is honoured when present instead of guessing.
    """
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(
            OVERPASS_URL,
            data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
            headers={"User-Agent": "nature-aggregator/0.1"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last_err = e
            retry_after = None
            if isinstance(e, urllib.error.HTTPError):
                retry_after = e.headers.get("Retry-After") if e.headers else None
            if retry_after and retry_after.isdigit():
                delay = int(retry_after)
            else:
                delay = min(RETRY_BACKOFF_BASE_S * (2 ** (attempt - 1)), RETRY_BACKOFF_CAP_S)
            print(f"    attempt {attempt}/{MAX_RETRIES} failed ({e}); retrying in {delay}s")
            time.sleep(delay)
    raise RuntimeError(f"Overpass query failed after {MAX_RETRIES} attempts: {last_err}")


def _list_relations() -> list[dict]:
    query = """
    [out:json][timeout:90];
    area["ISO3166-1"="FI"][admin_level=2]->.fi;
    relation["route"="hiking"](area.fi);
    out tags;
    """
    data = _overpass(query)
    return data.get("elements", [])


def _fetch_geometry_batch(relation_ids: list[int]) -> dict[int, list[dict]]:
    """Return {relation_id: [member, ...]} for one batch of ids."""
    ids = ",".join(str(i) for i in relation_ids)
    query = f"""
    [out:json][timeout:120];
    relation(id:{ids});
    out geom;
    """
    data = _overpass(query)
    return {el["id"]: el.get("members", []) for el in data.get("elements", []) if el.get("type") == "relation"}


def _to_multiline(members: list[dict]) -> dict | None:
    lines = []
    for m in members:
        if m.get("type") != "way":
            continue
        geom = m.get("geometry")
        if not geom or len(geom) < 2:
            continue
        lines.append([[pt["lon"], pt["lat"]] for pt in geom])
    if not lines:
        return None
    return {"type": "MultiLineString", "coordinates": lines}


def _description(tags: dict) -> str:
    bits = []
    network = tags.get("network")
    if network:
        bits.append(f"Network: {NETWORK_LABELS.get(network, network)}")
    distance = tags.get("distance")
    if distance:
        bits.append(f"Distance: {distance}")
    operator = tags.get("operator")
    if operator:
        bits.append(f"Operator: {operator}")
    desc = (tags.get("description") or tags.get("description:fi") or "").strip()
    if desc:
        bits.append(desc)
    return " · ".join(bits)


def fetch_features() -> list[dict]:
    print("  listing route=hiking relations via Overpass (tags only)")
    relations = _list_relations()
    print(f"    {len(relations)} relations found")

    out: list[dict] = []
    ids = [r["id"] for r in relations]
    tags_by_id = {r["id"]: (r.get("tags") or {}) for r in relations}
    n_batches = (len(ids) + RELATIONS_PER_BATCH - 1) // RELATIONS_PER_BATCH
    failed_batches = 0

    for start in range(0, len(ids), RELATIONS_PER_BATCH):
        batch = ids[start:start + RELATIONS_PER_BATCH]
        batch_num = start // RELATIONS_PER_BATCH + 1
        print(f"  fetching geometry batch {batch_num}/{n_batches} ({len(batch)} relations)")
        try:
            members_by_id = _fetch_geometry_batch(batch)
        except RuntimeError as e:
            # One batch exhausting retries (the shared Overpass instance
            # rate-limits/times out under sustained load) shouldn't sink
            # the whole layer - skip it and keep going, the same
            # partial-failure tolerance refresh.sh already applies across
            # adapters. A handful of missing trails out of ~700 is a far
            # better outcome than zero.
            print(f"    batch {batch_num} failed permanently, skipping ({e})")
            failed_batches += 1
            time.sleep(PAUSE_BETWEEN_BATCHES_S)
            continue
        for rel_id in batch:
            members = members_by_id.get(rel_id)
            if not members:
                continue
            geometry = _to_multiline(members)
            if not geometry:
                continue
            tags = tags_by_id.get(rel_id, {})
            name = (tags.get("name") or tags.get("name:fi") or "").strip() or "(unnamed trail)"
            link = tags.get("website") or f"https://www.openstreetmap.org/relation/{rel_id}"

            feature = make_line_feature(
                feature_id=f"osm-hiking-{rel_id}",
                name=name,
                geometry=geometry,
                category="hiking-trail",
                source=SOURCE,
                source_url=link,
                features=[],
                description=_description(tags),
            )
            if feature:
                out.append(feature)
        time.sleep(PAUSE_BETWEEN_BATCHES_S)

    if failed_batches:
        print(f"    {failed_batches}/{n_batches} batches failed permanently and were skipped")

    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
