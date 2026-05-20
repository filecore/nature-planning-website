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


def main():
    """Fetch once, write three layer files."""
    all_features = fetch_features()
    buckets: dict[str, list[dict]] = {"breweries": [], "wineries": [], "distilleries": []}
    for f in all_features:
        cat = (f.get("properties") or {}).get("category", "")
        layer = LAYER_FOR_CATEGORY.get(cat)
        if layer:
            buckets[layer].append(f)

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
