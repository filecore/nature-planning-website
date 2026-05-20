"""Adapter for the curated sauna Google Sheet.

The sheet has the shape:

    Sijainti, Alue, Saunat, , , , , , Linkit
    UKK kansallispuisto, Lappi, Anteri, Tahvo, Harkavaara, Karhuoja, ...

i.e. each row is an area in column A, with sauna names in columns C..H.
There are no coordinates. We join each row's area name against the
national-parks layer (produced by outdoors_fi.py) to obtain a coordinate,
then emit one feature per sauna placed at (or slightly offset from) the
parent area's coordinate.

Run order matters: ``national-parks.geojson`` must already exist on disk
when this adapter runs. ``refresh.sh`` invokes outdoors_fi first.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import urllib.request

from common import LAYERS_DIR, make_feature, polygon_bbox_centroid, run, write_layer

NAME = "saunas"
SOURCE = "Sauna list (Google Sheet)"
SHEET_ID = "1zQvYnqq35oMKoJ7HbqNE8P-4EmIQdPj3npZNUjRqfJ4"
SITE_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/"
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"


def _http_get(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": "nature-aggregator/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except Exception as e:
        print(f"  warn: {url} -> {e}", file=sys.stderr)
        return None


def _normalise(s: str) -> str:
    """Lowercase, strip Finnish diacritics, drop park-suffix words."""
    import unicodedata
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\b(kansallispuiston?|national park|nationalpark|kp|n\.p\.?)\b", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s



def _load_park_index() -> dict[str, tuple[float, float]]:
    """name (normalised) -> (lat, lon) from national-parks.geojson.

    Accepts both Point and Polygon/MultiPolygon features; polygons use the
    bounding-box centre as the join coordinate.
    """
    path = LAYERS_DIR / "national-parks.geojson"
    if not path.exists():
        return {}
    geo = json.loads(path.read_text())
    index: dict[str, tuple[float, float]] = {}
    for feat in geo.get("features", []):
        geom = feat.get("geometry") or {}
        props = feat.get("properties") or {}

        coord: tuple[float, float] | None = None
        if geom.get("type") == "Point":
            try:
                lon = float(geom["coordinates"][0])
                lat = float(geom["coordinates"][1])
                coord = (lat, lon)
            except (KeyError, TypeError, ValueError, IndexError):
                pass
        elif geom.get("type") in ("Polygon", "MultiPolygon"):
            cached = props.get("centroid")
            if isinstance(cached, list) and len(cached) >= 2:
                try:
                    coord = (float(cached[1]), float(cached[0]))
                except (TypeError, ValueError):
                    coord = None
            if not coord:
                coord = polygon_bbox_centroid(geom)

        name = props.get("name") or ""
        if name and coord:
            index[_normalise(name)] = coord
    return index


def _find_data_rows(rows: list[list[str]]) -> tuple[int, list[list[str]]]:
    """Locate the header row 'Sijainti,Alue,Saunat,...' and return data rows."""
    for i, row in enumerate(rows):
        joined = ",".join(c.strip().lower() for c in row[:3])
        if joined.startswith("sijainti,alue"):
            return i, rows[i + 1 :]
    raise RuntimeError("Could not find 'Sijainti,Alue,Saunat' header row in sheet")


def _jitter(lat: float, lon: float, index: int) -> tuple[float, float]:
    """Spread multiple saunas in the same area so markers don't perfectly overlap."""
    if index == 0:
        return lat, lon
    # ~150m offset, deterministic by sauna index
    angle = (index * 137.5) % 360
    import math
    dx = 0.0015 * math.cos(math.radians(angle))
    dy = 0.0015 * math.sin(math.radians(angle))
    return lat + dy, lon + dx


def fetch_features() -> list[dict]:
    url = os.environ.get("NATURE_SAUNAS_CSV", EXPORT_URL)
    payload = _http_get(url)
    if not payload:
        raise RuntimeError(
            f"Could not fetch sauna sheet at {url}. "
            "The sheet must have 'Anyone with the link can view' enabled."
        )

    text = payload.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    _, data_rows = _find_data_rows(rows)

    parks = _load_park_index()
    if not parks:
        print(
            "  warn: national-parks.geojson not found - run outdoors_fi.py first",
            file=sys.stderr,
        )

    out: list[dict] = []
    unmatched: list[str] = []
    for row in data_rows:
        if not row or not row[0].strip():
            continue
        area = row[0].strip()
        sauna_names = [c.strip() for c in row[2:8] if c and c.strip()]
        if not sauna_names:
            continue

        coord = parks.get(_normalise(area))
        if coord is None:
            # Try partial matches.
            target = _normalise(area)
            for key, val in parks.items():
                if target and (target in key or key in target):
                    coord = val
                    break
        if coord is None:
            unmatched.append(area)
            continue

        for idx, sname in enumerate(sauna_names):
            lat, lon = _jitter(coord[0], coord[1], idx)
            feature_id = "sauna-" + re.sub(r"[^a-z0-9]+", "-", (area + "-" + sname).lower())[:80]
            f = make_feature(
                feature_id=feature_id,
                name=sname,
                lat=lat,
                lon=lon,
                category="sauna",
                source=SOURCE,
                source_url=SITE_URL,
                features=["has-sauna"],
                description=f"Sauna in {area}",
            )
            if f:
                out.append(f)

    if unmatched:
        print(f"  note: {len(unmatched)} area(s) had saunas but no coordinate match:", file=sys.stderr)
        for u in unmatched[:10]:
            print(f"    - {u}", file=sys.stderr)
        if len(unmatched) > 10:
            print(f"    ... and {len(unmatched) - 10} more", file=sys.stderr)

    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
