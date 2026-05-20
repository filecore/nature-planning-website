"""Adapter for laavu.org laavus, kotas, and other shelters across Finland.

The site publishes a full GPX dump at
``https://laavu.org/lataa.php?paikkakunta=kaikki`` that contains every
waypoint shown on the map (~4500 entries). We fetch it, parse the
``<wpt>`` elements, and categorise each one by the two-letter Finnish
suffix appended to the name (e.g. "Oopakka LA" -> laavu).

The feed is refreshed monthly at most; cache aggressively when calling
this adapter from cron.
"""

from __future__ import annotations

import os
import re
import sys
import urllib.request
from xml.etree import ElementTree as ET

from common import make_feature, run, write_layer

NAME = "laavut"
SOURCE = "laavu.org"
SITE_URL = "http://laavu.org/"
GPX_URL = "https://laavu.org/lataa.php?paikkakunta=kaikki"

GPX_NS = {"g": "http://www.topografix.com/GPX/1/0"}

# Suffix -> (category, feature tags). Anything not matched defaults to laavu.
# Source: laavu.org legend. ``has-laavu`` is the umbrella tag the frontend
# uses for "any shelter / lean-to", ``enclosed-fire`` distinguishes kotas.
SUFFIX_MAP: dict[str, tuple[str, list[str]]] = {
    "LA": ("laavu", ["has-laavu", "has-fire-pit"]),
    "KO": ("kota", ["enclosed-fire", "has-fire-pit"]),
    "AT": ("autiotupa", ["wilderness-hut", "has-fire-pit"]),
    "VT": ("varaustupa", ["reservable-hut"]),
    "KA": ("kammi", ["has-laavu"]),
    "PA": ("paivatupa", ["day-hut"]),
    "RA": ("rakennelma", []),
    "TR": ("tulipaikka", ["has-fire-pit"]),
    "TU": ("tupa", ["wilderness-hut"]),
}


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "nature-aggregator/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


_SUFFIX_RE = re.compile(r"\b([A-Z]{2})\s*$")


def _classify(name: str, sym: str) -> tuple[str, list[str]]:
    m = _SUFFIX_RE.search(name.strip())
    if m and m.group(1) in SUFFIX_MAP:
        return SUFFIX_MAP[m.group(1)]
    # Fallback by sym.
    s = (sym or "").lower()
    if "campground" in s:
        return "kota", ["enclosed-fire", "has-fire-pit"]
    if "picnic" in s:
        return "laavu", ["has-laavu", "has-fire-pit"]
    return "laavu", ["has-laavu"]


def _strip_suffix(name: str) -> str:
    return _SUFFIX_RE.sub("", name).strip()


def _parse_gpx(payload: bytes) -> list[dict]:
    root = ET.fromstring(payload)
    out: list[dict] = []
    seen: set[str] = set()
    for wpt in root.iter("{http://www.topografix.com/GPX/1/0}wpt"):
        try:
            lat = float(wpt.attrib["lat"])
            lon = float(wpt.attrib["lon"])
        except (KeyError, ValueError):
            continue
        name_el = wpt.find("g:name", GPX_NS)
        raw_name = (name_el.text or "").strip() if name_el is not None else ""
        if not raw_name:
            continue
        sym_el = wpt.find("g:sym", GPX_NS)
        sym = (sym_el.text or "").strip() if sym_el is not None else ""
        cat, flags = _classify(raw_name, sym)
        display = _strip_suffix(raw_name)

        feature_id = "laavu-" + re.sub(r"[^a-z0-9]+", "-", (raw_name + f"-{lat:.4f}-{lon:.4f}").lower())[:80]
        if feature_id in seen:
            continue
        seen.add(feature_id)

        f = make_feature(
            feature_id=feature_id,
            name=display or raw_name,
            lat=lat,
            lon=lon,
            category=cat,
            source=SOURCE,
            source_url=SITE_URL,
            features=flags,
            description=sym,
        )
        if f:
            out.append(f)
    return out


def fetch_features() -> list[dict]:
    url = os.environ.get("NATURE_LAAVU_FEED", GPX_URL)
    payload = _http_get(url)
    if not payload:
        raise RuntimeError(f"Empty body from {url}")
    return _parse_gpx(payload)


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
