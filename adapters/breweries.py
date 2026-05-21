"""Adapter for the curated Finnish small-breweries / wineries / distilleries
Google My Maps. Writes THREE separate layers from a single KML download:
breweries (incl. sahti), wineries, and distilleries.

Source: ``https://www.google.com/maps/d/u/0/edit?mid=1NtD_h1CjndFVmV77m1chR3Mjhko``
(map title "Suomen pienpanimot"). Google My Maps serves the underlying
layer as KML via ``/maps/d/kml?mid=<mid>&forcekml=1``. The same map
includes wineries and small distilleries flagged by colour / icon.

The KML carries ~260 placemarks with point geometry and free-text
descriptions (address, website, opening hours). We pull name +
coordinates and put the description in the popup; categorisation is by
``<styleUrl>`` / ``<name>`` token where we can detect it.
"""

from __future__ import annotations

import os
import re
import sys
import urllib.request
from xml.etree import ElementTree as ET

from common import make_feature, run, write_layer

SOURCE = "Suomen pienpanimot (Google My Maps, olutkellari.blogspot.fi)"
SITE_URL = "https://www.google.com/maps/d/u/0/viewer?mid=1NtD_h1CjndFVmV77m1chR3Mjhko"
KML_URL = "https://www.google.com/maps/d/kml?mid=1NtD_h1CjndFVmV77m1chR3Mjhko&forcekml=1"

# Splits one KML download into three output layers. Sahti breweries fold
# into the main breweries layer; they are a regional style of beer, not a
# separate establishment type.
LAYER_FOR_CATEGORY = {
    "brewery": "breweries",
    "sahti-brewery": "breweries",
    "winery": "wineries",
    "distillery": "distilleries",
}

KML_NS = {"k": "http://www.opengis.net/kml/2.2"}


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "nature-aggregator/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _classify(name: str, description: str, style_url: str) -> tuple[str, list[str]]:
    blob = (name + " " + description).lower()
    if "tislaamo" in blob or "distillery" in blob:
        return "distillery", []
    if "viinitila" in blob or "winery" in blob:
        return "winery", []
    if "sahti" in blob:
        return "sahti-brewery", []
    if "punainen" in style_url.lower():  # red marker = sahti per map legend
        return "sahti-brewery", []
    return "brewery", []


def _strip_html(s: str) -> str:
    # KML descriptions are CDATA blobs of HTML. Keep them readable in popups.
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


def _parse_kml(payload: bytes) -> list[dict]:
    root = ET.fromstring(payload)
    out: list[dict] = []
    for pm in root.iter("{http://www.opengis.net/kml/2.2}Placemark"):
        name_el = pm.find("k:name", KML_NS)
        if name_el is None or not name_el.text:
            continue
        name = name_el.text.strip()
        desc_el = pm.find("k:description", KML_NS)
        desc = _strip_html(desc_el.text or "") if desc_el is not None else ""
        style_el = pm.find("k:styleUrl", KML_NS)
        style = (style_el.text or "") if style_el is not None else ""

        coord_el = pm.find(".//k:Point/k:coordinates", KML_NS)
        if coord_el is None or not coord_el.text:
            continue
        try:
            parts = coord_el.text.strip().split(",")
            lon, lat = float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            continue

        cat, flags = _classify(name, desc, style)
        feature_id = "brew-" + re.sub(r"[^a-z0-9]+", "-", name.lower())[:60] + f"-{lat:.4f}-{lon:.4f}"

        f = make_feature(
            feature_id=feature_id,
            name=name,
            lat=lat,
            lon=lon,
            category=cat,
            source=SOURCE,
            source_url=SITE_URL,
            features=flags,
            description=desc[:400],
        )
        if f:
            out.append(f)
    return out


def fetch_features() -> list[dict]:
    url = os.environ.get("NATURE_BREWERIES_KML", KML_URL)
    payload = _http_get(url)
    return _parse_kml(payload)


def _load_winery_supplement():
    """Merge in any rows from data/manual/wineries_supplement.csv. The
    upstream Google My Maps KML only covers ~15 wineries; the supplement
    is a hand-curated extension. Rows are deduplicated against the KML
    output by coord proximity (200 m)."""
    import csv as _csv, io as _io, math as _math, pathlib as _pl, re as _re
    supplement = _pl.Path(__file__).resolve().parent.parent / "data" / "manual" / "wineries_supplement.csv"
    if not supplement.exists():
        return []
    text = supplement.read_text(encoding="utf-8-sig")
    out = []
    gmaps_re = _re.compile(r"/maps/(?:place/[^/]+/)?@(-?\d+\.\d+),(-?\d+\.\d+)")
    for row in _csv.DictReader(_io.StringIO(text)):
        name = (row.get("Name") or "").strip()
        if not name:
            continue
        url = (row.get("Google Maps URL") or "").strip()
        m = gmaps_re.search(url)
        if not m:
            continue
        try:
            lat, lon = float(m.group(1)), float(m.group(2))
        except ValueError:
            continue
        out.append({
            "name": name,
            "lat": lat, "lon": lon,
            "description": (row.get("Details") or "").strip(),
        })
    return out


def _dedupe_supplement(kml_feats, supplement):
    """Drop supplement rows whose coord lies within 200 m of an existing
    KML feature."""
    import math as _math
    def hav(a, b, c, d):
        R = 6371000
        p1, p2 = _math.radians(a), _math.radians(c)
        return 2*R*_math.asin(_math.sqrt(_math.sin(_math.radians(c-a)/2)**2 + _math.cos(p1)*_math.cos(p2)*_math.sin(_math.radians(d-b)/2)**2))
    out = []
    for s in supplement:
        too_close = False
        for f in kml_feats:
            try:
                fl, fln = f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0]
            except (KeyError, TypeError, IndexError):
                continue
            if hav(s["lat"], s["lon"], fl, fln) < 200:
                too_close = True
                break
        if not too_close:
            out.append(s)
    return out


def main():
    """Fetch once, write three layer files."""
    all_features = fetch_features()
    buckets: dict[str, list[dict]] = {"breweries": [], "wineries": [], "distilleries": []}
    for f in all_features:
        cat = (f.get("properties") or {}).get("category", "")
        layer = LAYER_FOR_CATEGORY.get(cat)
        if layer:
            buckets[layer].append(f)

    # Merge supplemental wineries (hand-curated CSV) into the wineries
    # bucket, deduplicated by coord proximity.
    supplement = _load_winery_supplement()
    if supplement:
        new = _dedupe_supplement(buckets["wineries"], supplement)
        for s in new:
            import re as _re
            slug = _re.sub(r"[^a-z0-9]+", "-", s["name"].lower())[:60]
            feat = make_feature(
                feature_id=f"winery-extra-{slug}",
                name=s["name"],
                lat=s["lat"], lon=s["lon"],
                category="winery",
                source="Wineries supplement (data/manual/wineries_supplement.csv)",
                source_url="https://www.viinitilat.net/",
                features=[],
                description=s["description"],
            )
            if feat:
                buckets["wineries"].append(feat)
        print(f"  wineries supplement: {len(new)}/{len(supplement)} merged after dedup", file=sys.stderr)

    last_path = None
    for layer_name, feats in buckets.items():
        if not feats:
            print(f"  warn: layer '{layer_name}' would be empty, skipping", file=sys.stderr)
            continue
        last_path = write_layer(layer_name, SOURCE, SITE_URL, feats)
    return last_path


if __name__ == "__main__":
    # Despite the file name "breweries.py", this adapter is the source of
    # three layer files: breweries, wineries, distilleries. The run banner
    # uses the umbrella name to make refresh.sh logs accurate.
    sys.exit(run(main, name="alcohol"))
