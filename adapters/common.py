"""Shared helpers for nature.togneri.net data adapters.

Each adapter produces a normalised GeoJSON FeatureCollection that the
frontend can consume without per-source special-casing. The schema is:

  {
    "type": "FeatureCollection",
    "generated_at": "2026-05-20T12:00:00Z",
    "source": "outdoors.fi",
    "source_url": "https://www.outdoors.fi/",
    "features": [
      {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
          "id": "stable-id",
          "name": "Nuuksio",
          "category": "national-park",
          "region": "Uusimaa",
          "description": "Optional short description",
          "features": ["has-sauna", "has-fire-pit"],
          "source": "outdoors.fi",
          "source_url": "https://www.nationalparks.fi/nuuksionp"
        }
      }
    ]
  }

Adapters call ``write_layer(name, source, source_url, features)`` which
validates feature counts and writes to src/data/layers/<name>.geojson.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import sys
from typing import Iterable

LAYERS_DIR = pathlib.Path(__file__).resolve().parent.parent / "src" / "data" / "layers"

# Finland bounding box for sanity-checking coordinates.
FIN_MIN_LAT, FIN_MAX_LAT = 59.5, 70.2
FIN_MIN_LON, FIN_MAX_LON = 19.0, 31.7

# Rough centroids of the 19 Finnish maakuntas. Used to assign a region to a
# point by nearest-neighbour. Coarse but enough for filter purposes.
# Names are the canonical Finnish forms with diacritics — all adapters MUST
# produce these strings (route any upstream value through canonical_region())
# so the frontend region filter does not see duplicates.
REGIONS = [
    ("Uusimaa",                60.30, 24.90),
    ("Varsinais-Suomi",        60.45, 22.30),
    ("Satakunta",              61.55, 22.10),
    ("Kanta-Häme",             60.85, 24.45),
    ("Pirkanmaa",              61.65, 23.85),
    ("Päijät-Häme",            61.10, 25.65),
    ("Kymenlaakso",            60.70, 26.70),
    ("Etelä-Karjala",          61.05, 28.20),
    ("Etelä-Savo",             61.85, 27.35),
    ("Pohjois-Savo",           63.10, 27.50),
    ("Pohjois-Karjala",        62.85, 30.00),
    ("Keski-Suomi",            62.50, 25.65),
    ("Etelä-Pohjanmaa",        62.85, 22.85),
    ("Pohjanmaa",              63.20, 22.20),
    ("Keski-Pohjanmaa",        63.85, 23.55),
    ("Pohjois-Pohjanmaa",      65.00, 25.40),
    ("Kainuu",                 64.20, 28.65),
    ("Lappi",                  67.50, 26.50),
    ("Ahvenanmaa",             60.20, 20.00),
]

_CANON_NAMES = {name for name, _, _ in REGIONS}
_REGION_ALIASES = {
    # Diacritic-stripped variants written by older adapters before
    # canonical_region() existed.
    "Kanta-Hame": "Kanta-Häme",
    "Paijat-Hame": "Päijät-Häme",
    "Etela-Karjala": "Etelä-Karjala",
    "Etela-Savo": "Etelä-Savo",
    "Etela-Pohjanmaa": "Etelä-Pohjanmaa",
    # Sub-region of Lappi, not a maakunta in its own right; collapse it.
    "Saamelaisten kotiseutualue": "Lappi",
}


def in_finland(lat: float, lon: float) -> bool:
    return FIN_MIN_LAT <= lat <= FIN_MAX_LAT and FIN_MIN_LON <= lon <= FIN_MAX_LON


def region_for(lat: float, lon: float) -> str:
    """Approximate Finnish maakunta by nearest centroid."""
    best_name, best_d = "", float("inf")
    for name, rlat, rlon in REGIONS:
        d = (rlat - lat) ** 2 + (rlon - lon) ** 2
        if d < best_d:
            best_d = d
            best_name = name
    return best_name


def canonical_region(value: str | None) -> str | None:
    """Normalise any region string to one of the 19 canonical maakuntas.

    Handles diacritic-stripped variants, known aliases (Sami homeland),
    and compound cross-border strings like "Kainuu, Pohjois-Karjala"
    (returns the first canonical match). Returns None for empty input
    or if no match can be found.
    """
    if not value:
        return None
    for part in (p.strip() for p in value.split(",") if p.strip()):
        if part in _CANON_NAMES:
            return part
        if part in _REGION_ALIASES:
            return _REGION_ALIASES[part]
    return None


def make_feature(
    feature_id: str,
    name: str,
    lat: float,
    lon: float,
    *,
    category: str,
    source: str,
    source_url: str,
    features: Iterable[str] = (),
    description: str = "",
    region: str | None = None,
) -> dict | None:
    if not in_finland(lat, lon):
        return None
    if region is None:
        region = region_for(lat, lon)
    else:
        region = canonical_region(region) or region_for(lat, lon)
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
        "properties": {
            "id": feature_id,
            "name": name.strip(),
            "category": category,
            "region": region,
            "description": (description or "").strip(),
            "features": sorted(set(f for f in features if f)),
            "source": source,
            "source_url": source_url,
        },
    }


def polygon_bbox_centroid(geometry: dict) -> tuple[float, float] | None:
    """Return (lat, lon) of the bounding-box centre of a Polygon/MultiPolygon."""
    coords = geometry.get("coordinates")
    if not coords:
        return None
    lons: list[float] = []
    lats: list[float] = []

    def collect(seq):
        if not seq:
            return
        if isinstance(seq[0], (int, float)):
            try:
                lons.append(float(seq[0]))
                lats.append(float(seq[1]))
            except (IndexError, ValueError, TypeError):
                pass
            return
        for s in seq:
            collect(s)

    collect(coords)
    if not lons:
        return None
    return (
        (min(lats) + max(lats)) / 2.0,
        (min(lons) + max(lons)) / 2.0,
    )


def _simplify_ring(ring: list, precision: int, *, close: bool = True) -> list:
    """Round coords to ``precision`` decimals and drop consecutive duplicates.

    Crude but good enough to take national-park polygons from megabytes to
    tens of kilobytes without visible loss at country-level zoom. At
    precision=4 (decimals of degrees), ~11 metres at the equator.

    ``close`` re-closes a polygon ring if dedup dropped its closing point.
    Pass ``close=False`` for open lines (trails, rivers) - forcing those
    closed would draw a spurious segment back to the start.
    """
    out: list[list[float]] = []
    prev: tuple[float, float] | None = None
    for pt in ring:
        try:
            lon = round(float(pt[0]), precision)
            lat = round(float(pt[1]), precision)
        except (TypeError, ValueError, IndexError):
            continue
        if prev == (lon, lat):
            continue
        out.append([lon, lat])
        prev = (lon, lat)
    if close and len(out) >= 3 and out[0] != out[-1]:
        out.append(out[0][:])
    return out


def _decimate_ring(ring: list, min_step: float) -> list:
    """Drop points that are within ``min_step`` degrees of the previous kept point.

    Cheap alternative to Douglas-Peucker. ``min_step`` of 0.001 is about
    110 metres at Finland's latitude, fine for country-zoom rendering.
    """
    if len(ring) <= 4:
        return ring
    kept = [ring[0]]
    last_lon, last_lat = ring[0][0], ring[0][1]
    for pt in ring[1:-1]:
        lon, lat = pt[0], pt[1]
        if abs(lon - last_lon) + abs(lat - last_lat) >= min_step:
            kept.append(pt)
            last_lon, last_lat = lon, lat
    kept.append(ring[-1])
    return kept


def _simplify_geometry(geometry: dict, precision: int = 4, min_step: float = 0.001) -> dict:
    """Apply ``_simplify_ring`` recursively across Polygon/MultiPolygon/
    LineString/MultiLineString. Lines are never re-closed into a loop."""
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    def reduce(ring, *, close):
        ring = _decimate_ring(ring, min_step)
        return _simplify_ring(ring, precision, close=close)

    if gtype == "Polygon":
        new_rings = [reduce(r, close=True) for r in coords]
        return {"type": "Polygon", "coordinates": [r for r in new_rings if len(r) >= 4]}
    if gtype == "MultiPolygon":
        new_polys = []
        for poly in coords:
            rings = [reduce(r, close=True) for r in poly]
            rings = [r for r in rings if len(r) >= 4]
            if rings:
                new_polys.append(rings)
        return {"type": "MultiPolygon", "coordinates": new_polys}
    if gtype == "LineString":
        new_line = reduce(coords, close=False)
        return {"type": "LineString", "coordinates": new_line if len(new_line) >= 2 else []}
    if gtype == "MultiLineString":
        new_lines = [reduce(line, close=False) for line in coords]
        return {"type": "MultiLineString", "coordinates": [l for l in new_lines if len(l) >= 2]}
    return geometry


def make_polygon_feature(
    feature_id: str,
    name: str,
    geometry: dict,
    *,
    category: str,
    source: str,
    source_url: str,
    features: Iterable[str] = (),
    description: str = "",
    region: str | None = None,
    coord_precision: int = 4,
    min_step: float = 0.001,
) -> dict | None:
    """Emit a Polygon/MultiPolygon feature with the same property schema as Points.

    ``coord_precision`` controls decimal-rounding (default 4 -> ~11 m at
    Finland's latitude). ``min_step`` is the Manhattan-distance threshold
    for the cheap decimator (default 0.001 -> ~110 m). Bump both for
    layers with many small polygons that don't need fine detail at
    country-level zoom.
    """
    if geometry.get("type") not in ("Polygon", "MultiPolygon"):
        return None
    centroid = polygon_bbox_centroid(geometry)
    if not centroid:
        return None
    lat, lon = centroid
    if not in_finland(lat, lon):
        return None
    if region is None:
        region = region_for(lat, lon)
    geometry = _simplify_geometry(geometry, precision=coord_precision, min_step=min_step)
    if not geometry.get("coordinates"):
        return None
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "id": feature_id,
            "name": name.strip(),
            "category": category,
            "region": region,
            "description": (description or "").strip(),
            "features": sorted(set(f for f in features if f)),
            "source": source,
            "source_url": source_url,
            "centroid": [round(lon, 6), round(lat, 6)],
        },
    }


def make_line_feature(
    feature_id: str,
    name: str,
    geometry: dict,
    *,
    category: str,
    source: str,
    source_url: str,
    features: Iterable[str] = (),
    description: str = "",
    region: str | None = None,
    coord_precision: int = 4,
    min_step: float = 0.0005,
) -> dict | None:
    """Emit a LineString/MultiLineString feature with the same property
    schema as Points/Polygons (trails, rivers - anything linear).

    Same parameters as ``make_polygon_feature``; the lower default
    ``min_step`` keeps more shape detail since lines have far fewer points
    per feature than a reserve polygon's ring, so aggressive decimation
    isn't needed to keep file size down.
    """
    if geometry.get("type") not in ("LineString", "MultiLineString"):
        return None
    centroid = polygon_bbox_centroid(geometry)
    if not centroid:
        return None
    lat, lon = centroid
    if not in_finland(lat, lon):
        return None
    if region is None:
        region = region_for(lat, lon)
    geometry = _simplify_geometry(geometry, precision=coord_precision, min_step=min_step)
    if not geometry.get("coordinates"):
        return None
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "id": feature_id,
            "name": name.strip(),
            "category": category,
            "region": region,
            "description": (description or "").strip(),
            "features": sorted(set(f for f in features if f)),
            "source": source,
            "source_url": source_url,
            "centroid": [round(lon, 6), round(lat, 6)],
        },
    }


def write_layer(name: str, source: str, source_url: str, features: list[dict]) -> pathlib.Path:
    LAYERS_DIR.mkdir(parents=True, exist_ok=True)
    out = LAYERS_DIR / f"{name}.geojson"
    if not features:
        raise RuntimeError(
            f"adapter '{name}' produced zero features. "
            "Refusing to overwrite. Check the source endpoint."
        )
    payload = {
        "type": "FeatureCollection",
        "generated_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
        "source_url": source_url,
        "features": features,
    }
    # Compact JSON: indent=1 inflates polygon coordinate arrays massively.
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    print(f"  wrote {out.relative_to(LAYERS_DIR.parent.parent.parent)} ({len(features)} features)")
    return out


def run(adapter_fn, *, name: str) -> int:
    """Standard CLI entry point for an adapter module.

    ``adapter_fn`` may return a single path (single-layer adapter) or a list
    of paths (an adapter that produces multiple layers from one source).
    """
    print(f"[{name}] starting")
    try:
        result = adapter_fn()
        if isinstance(result, (list, tuple)):
            for path in result:
                print(f"[{name}] ok -> {path}")
        else:
            print(f"[{name}] ok -> {result}")
        return 0
    except Exception as e:
        print(f"[{name}] FAILED: {e}", file=sys.stderr)
        return 1
