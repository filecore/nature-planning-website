"""Adapter for "Suomen luonnon pyhäpaikat" (Finnish natural sacred sites).

This is a manual-export adapter. The upstream is a Google Maps *List*
(distinct from My Maps), and Google does not expose List pin data over
any public endpoint -- there is no KML export and the page renders
pins client-side after a private RPC. The realistic ways to populate
this layer are, in order of effort:

1. Browser extension. Install something like "Maps List Export" or
   "Map Exporter for Google Maps" in Chrome, open the list, export to
   CSV or KML, save the result at ``data/manual/pyhat_paikat.csv``
   (or ``.kml``).
2. Hand-curate. Edit ``data/manual/pyhat_paikat.csv`` with the columns
   ``name,lat,lon,description`` (description optional). Pasting in
   coordinates one place at a time is tedious but reliable.

This adapter accepts EITHER ``pyhat_paikat.kml`` OR
``pyhat_paikat.csv``; the CSV wins if both are present. If neither
file exists, the adapter soft-skips so ``refresh.sh`` stays green.
"""

from __future__ import annotations

import csv
import os
import pathlib
import re
import sys
from xml.etree import ElementTree as ET

from common import make_feature, run, write_layer

NAME = "sacred-sites"
SOURCE = "Suomen luonnon pyhapaikat (manual export)"
SITE_URL = "https://www.facebook.com/pyhatpaikat/"
MANUAL_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "manual"
KML_PATH = MANUAL_DIR / "pyhat_paikat.kml"
CSV_PATH = MANUAL_DIR / "pyhat_paikat.csv"

KML_NS = {"k": "http://www.opengis.net/kml/2.2"}


class MissingManualFile(Exception):
    """Raised when the user has not yet placed the expected KML export."""


def _strip_html(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


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

        coord_el = pm.find(".//k:Point/k:coordinates", KML_NS)
        if coord_el is None or not coord_el.text:
            continue
        try:
            parts = coord_el.text.strip().split(",")
            lon, lat = float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            continue

        feature_id = "sacred-" + re.sub(r"[^a-z0-9]+", "-", name.lower())[:60] + f"-{lat:.4f}-{lon:.4f}"
        f = make_feature(
            feature_id=feature_id,
            name=name,
            lat=lat,
            lon=lon,
            category="sacred-site",
            source=SOURCE,
            source_url=SITE_URL,
            features=[],
            description=desc[:400],
        )
        if f:
            out.append(f)
    return out


def _parse_csv(text: str) -> list[dict]:
    """Accept a CSV with columns name,lat,lon,description (order flexible)."""
    out: list[dict] = []
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        return out
    # Normalise headers to lowercase for tolerance.
    headers = {h.lower().strip(): h for h in reader.fieldnames if h}
    name_h = headers.get("name") or headers.get("nimi")
    lat_h = headers.get("lat") or headers.get("latitude") or headers.get("leveysaste")
    lon_h = headers.get("lon") or headers.get("lng") or headers.get("longitude") or headers.get("pituusaste")
    desc_h = headers.get("description") or headers.get("kuvaus") or headers.get("notes")
    if not (name_h and lat_h and lon_h):
        raise RuntimeError(
            "CSV must have at least name, lat, lon columns "
            "(description optional). Got headers: " + ", ".join(reader.fieldnames or [])
        )

    for row in reader:
        name = (row.get(name_h) or "").strip()
        if not name:
            continue
        try:
            lat = float((row.get(lat_h) or "").replace(",", "."))
            lon = float((row.get(lon_h) or "").replace(",", "."))
        except ValueError:
            continue
        desc = (row.get(desc_h) or "").strip() if desc_h else ""
        feature_id = "sacred-" + re.sub(r"[^a-z0-9]+", "-", name.lower())[:60] + f"-{lat:.4f}-{lon:.4f}"
        f = make_feature(
            feature_id=feature_id,
            name=name,
            lat=lat,
            lon=lon,
            category="sacred-site",
            source=SOURCE,
            source_url=SITE_URL,
            features=[],
            description=desc[:400],
        )
        if f:
            out.append(f)
    return out


def fetch_features() -> list[dict]:
    # CSV takes precedence over KML so hand-curated edits beat a stale export.
    if CSV_PATH.exists():
        return _parse_csv(CSV_PATH.read_text(encoding="utf-8-sig"))
    if KML_PATH.exists():
        return _parse_kml(KML_PATH.read_bytes())

    path_override = os.environ.get("NATURE_SACRED_KML")
    if path_override and pathlib.Path(path_override).exists():
        p = pathlib.Path(path_override)
        if p.suffix.lower() == ".csv":
            return _parse_csv(p.read_text(encoding="utf-8-sig"))
        return _parse_kml(p.read_bytes())

    raise MissingManualFile(
        f"No manual export at {KML_PATH} or {CSV_PATH}. "
        "See data/manual/README.md."
    )


def main():
    try:
        feats = fetch_features()
    except MissingManualFile as e:
        # Soft-skip: do not overwrite a previous layer file with empty
        # contents, but do not break refresh.sh either.
        print(f"  skipped: {e}")
        return None
    return write_layer(NAME, SOURCE, SITE_URL, feats)


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
