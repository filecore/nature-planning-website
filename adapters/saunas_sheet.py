"""Adapter for the curated sauna Google Sheet.

The sheet has the shape:

    Sijainti, Alue, Saunat, , , , , , Linkit
    UKK kansallispuisto, Lappi, Anteri, Tahvo, Harkavaara, Karhuoja, ...

i.e. each row is an area in column A, with sauna names in columns C..H.
There are no coordinates per sauna. We resolve each row's Sijainti (area)
to a coordinate using a four-stage cascade and emit one feature per sauna,
jittered slightly around the parent area so markers do not overlap:

  1. Exact normalised match against the in-house place index (which now
     spans national-parks, hiking-areas, lean-tos, and wilderness-huts).
  2. Curated alias map (e.g. "UKK" -> "Urho Kekkosen", "Hetta-Pallas" ->
     "Pallas-Yllastunturin") for short / colloquial forms that won't
     normalise to the official park name.
  3. Substring match using a Finnish-stemmed form of both sides (strips
     trailing genitive -n and a final vowel), which catches
     "Lemmenjoki" <-> "Lemmenjoen kansallispuisto" and similar.
  4. Nominatim geocoding restricted to Finland, with a JSON cache on disk
     under data/manual/saunas_geocache.json. Bounded to 1 req/sec to
     respect the public service's usage policy.

Run order matters: the spatial layers this adapter joins against must
already exist on disk. ``refresh.sh`` invokes the relevant adapters
first (outdoors_fi, laavu_org).
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

from common import LAYERS_DIR, make_feature, polygon_bbox_centroid, run, write_layer

NAME = "saunas"
SOURCE = "Sauna list (Google Sheet)"
SHEET_ID = "1zQvYnqq35oMKoJ7HbqNE8P-4EmIQdPj3npZNUjRqfJ4"
SITE_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/"
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# Curated short-form -> known canonical fragment. Lower-case, normalised.
# Each value just has to substring-match against the in-house place index.
AREA_ALIASES: dict[str, str] = {
    "ukk": "urho kekkosen",
    "ukk kansallispuisto": "urho kekkosen",
    "iso syote": "syotteen",
    "hetta pallas": "pallas yllas",
    "mantyharju repovesi": "repoveden",
    "tammisaari": "tammisaaren",
    "korvatunturi": "korvatunturin",   # falls through to Nominatim if not in WFS
    "puljun eramaaalue": "puljun eramaa",
    "puljun eramaa alue": "puljun eramaa",
}

# Free-text area names that aren't valid Nominatim queries as-written
# (typos, hybrid names, or local nicknames). Mapped to a query string
# Nominatim can resolve. Applied as a *Nominatim*-stage rewrite, not a
# substitution against the local spatial index.
GEOCODE_OVERRIDES: dict[str, str] = {
    "saariselaka": "Saariselka, Finland",  # sheet typo for Saariselka
}

# Cache for Nominatim lookups so we hit the network at most once per name
# across runs. The file is small (a flat dict, name -> [lat, lon] or null)
# and lives in data/manual/ alongside other hand-curated overlays.
NOMINATIM_CACHE_PATH = LAYERS_DIR.parent / "manual" / "saunas_geocache.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_DELAY_S = 1.1  # public-service rate limit is 1 req/sec
NOMINATIM_UA = "nature-aggregator/0.1 (https://nature.togneri.net)"

# Spatial layers consulted for the area-name index. We deliberately only
# index large named regions (national parks + wilderness areas) here: the
# sheet's Sijainti column always names an "area" rather than a specific
# hut, so dragging the 4400 laavu / kota points into the index just
# creates false positives like "Koli" (a lean-to in Forssa) winning over
# "Kolin kansallispuisto".
PLACE_LAYERS = [
    "national-parks",
    "wilderness-areas",
]


def _http_get(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": "nature-aggregator/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except Exception as e:
        print(f"  warn: {url} -> {e}", file=sys.stderr)
        return None


def _strip_diacritics(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _normalise(s: str) -> str:
    """Lowercase, strip diacritics, drop park-suffix words."""
    s = _strip_diacritics(s.lower().strip())
    s = re.sub(r"\b(kansallispuiston?|national park|nationalpark|kp|n\.p\.?)\b", "", s)
    s = re.sub(r"\beramaa(?:n|alue|-alue|alueen)?\b", "eramaa", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def _stem_word(w: str) -> str:
    """Crude Finnish noun stemmer.

    Drops a trailing 'n' that follows a vowel (Finnish genitive ``-n``),
    then drops a trailing single vowel. Maps both ``helvetinjarven`` and
    ``helvetinjarvi`` to ``helvetinjarv`` so a substring match across the
    two forms succeeds. Short tokens (<= 4 chars) are kept as-is so
    common words don't collapse into noise.
    """
    if len(w) <= 4:
        return w
    if w.endswith("n") and len(w) >= 2 and w[-2] in "aeiouy":
        w = w[:-1]
    if len(w) >= 5 and w[-1] in "aeiouy":
        w = w[:-1]
    return w


def _stem(s: str) -> str:
    """Apply ``_stem_word`` to each token in a normalised string."""
    return " ".join(_stem_word(t) for t in s.split())


def _coord_for_feature(feat: dict) -> tuple[float, float] | None:
    """Best (lat, lon) for a GeoJSON feature: Point coords, then cached centroid, then bbox centre."""
    geom = feat.get("geometry") or {}
    props = feat.get("properties") or {}
    if geom.get("type") == "Point":
        try:
            lon = float(geom["coordinates"][0])
            lat = float(geom["coordinates"][1])
            return (lat, lon)
        except (KeyError, TypeError, ValueError, IndexError):
            return None
    if geom.get("type") in ("Polygon", "MultiPolygon"):
        cached = props.get("centroid")
        if isinstance(cached, list) and len(cached) >= 2:
            try:
                return (float(cached[1]), float(cached[0]))
            except (TypeError, ValueError):
                pass
        return polygon_bbox_centroid(geom)
    return None


def _load_place_index() -> dict[str, tuple[float, float]]:
    """Build {normalised name -> (lat, lon)} across all spatial layers.

    Earlier layers in ``PLACE_LAYERS`` win on collisions so a sheet row
    naming a national park resolves to the park centroid rather than to
    some unrelated lean-to that happens to share the name.
    """
    index: dict[str, tuple[float, float]] = {}
    for layer_name in PLACE_LAYERS:
        path = LAYERS_DIR / f"{layer_name}.geojson"
        if not path.exists():
            continue
        try:
            geo = json.loads(path.read_text())
        except Exception:
            continue
        for feat in geo.get("features", []):
            name = (feat.get("properties") or {}).get("name") or ""
            if not name:
                continue
            coord = _coord_for_feature(feat)
            if not coord:
                continue
            key = _normalise(name)
            if key and key not in index:
                index[key] = coord
    return index


def _lookup_local(area: str, index: dict[str, tuple[float, float]]) -> tuple[float, float] | None:
    """Try alias -> exact -> stemmed substring against the local index."""
    norm = _normalise(area)
    if not norm:
        return None
    # Alias path: nudge the lookup term toward a known canonical fragment.
    aliased = AREA_ALIASES.get(norm)
    if aliased:
        if aliased in index:
            return index[aliased]
        for key, val in index.items():
            if aliased in key or key in aliased:
                return val
    # Direct exact match on the normalised area name.
    if norm in index:
        return index[norm]
    # Substring match in normalised form (handles e.g. "helvetinjarvi"
    # against "helvetinjarven kansallispuisto").
    for key, val in index.items():
        if norm and (norm in key or key in norm) and len(norm) >= 5:
            return val
    # Stemmed substring as last local-only attempt.
    stem = _stem(norm)
    if stem and stem != norm:
        for key, val in index.items():
            kstem = _stem(key)
            if (stem in kstem or kstem in stem) and len(stem) >= 5:
                return val
    return None


def _load_geocache() -> dict[str, list | None]:
    if NOMINATIM_CACHE_PATH.exists():
        try:
            return json.loads(NOMINATIM_CACHE_PATH.read_text())
        except Exception:
            pass
    return {}


def _save_geocache(cache: dict[str, list | None]) -> None:
    NOMINATIM_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOMINATIM_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True))


_LAST_NOMINATIM_AT: float = 0.0


def _nominatim_lookup(query: str) -> tuple[float, float] | None:
    """One Nominatim hit for an area name, restricted to Finland."""
    global _LAST_NOMINATIM_AT
    elapsed = time.monotonic() - _LAST_NOMINATIM_AT
    if elapsed < NOMINATIM_DELAY_S:
        time.sleep(NOMINATIM_DELAY_S - elapsed)
    params = {
        "q": query,
        "format": "json",
        "limit": "1",
        "countrycodes": "fi",
        "accept-language": "fi",
    }
    url = NOMINATIM_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": NOMINATIM_UA, "Accept-Language": "fi"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"  warn: nominatim {query!r}: {e}", file=sys.stderr)
        return None
    finally:
        _LAST_NOMINATIM_AT = time.monotonic()
    if not data:
        return None
    try:
        return (float(data[0]["lat"]), float(data[0]["lon"]))
    except (KeyError, ValueError, TypeError):
        return None


def _resolve_area(
    area: str,
    index: dict[str, tuple[float, float]],
    cache: dict[str, list | None],
) -> tuple[float, float] | None:
    """Local -> cached Nominatim -> live Nominatim."""
    local = _lookup_local(area, index)
    if local is not None:
        return local

    key = _normalise(area)
    if key in cache:
        cached = cache[key]
        if isinstance(cached, list) and len(cached) == 2:
            return (float(cached[0]), float(cached[1]))
        return None  # explicit miss recorded earlier; skip the network

    for q in _geocode_variants(area):
        coord = _nominatim_lookup(q)
        if coord:
            cache[key] = [coord[0], coord[1]]
            return coord
    cache[key] = None
    return None


# Trailing Finnish words that turn a place name into "near X" / "X trail".
# Strip them before geocoding so "Oulun lahisto" hits "Oulu" and "Arpaisten
# reitti" hits "Arpainen". Order matters only for readability.
_GEOCODE_TRIM_WORDS = ("lahisto", "lahistolla", "lahistoll", "reitti", "reitin", "kierros", "polku")


def _geocode_variants(area: str) -> list[str]:
    """Yield several Nominatim query strings to try, from specific to broad."""
    norm = _normalise(area)
    variants: list[str] = []
    override = GEOCODE_OVERRIDES.get(norm)
    if override:
        variants.append(override)
    variants.extend([area, f"{area}, Finland"])
    tokens = norm.split()
    # Drop trailing context words ("lahisto" = vicinity, "reitti" = trail).
    while tokens and tokens[-1] in _GEOCODE_TRIM_WORDS:
        tokens.pop()
    trimmed = " ".join(tokens)
    if trimmed and trimmed != norm:
        variants.append(f"{trimmed}, Finland")
    # Final fallback: just the first token (often the place stem like
    # "Oulun"). Strip a trailing genitive -n so "Oulun" -> "Oulu".
    if tokens:
        head = tokens[0]
        if head.endswith("n") and len(head) > 3:
            head = head[:-1]
        if head and head != trimmed:
            variants.append(f"{head}, Finland")
    # De-dup while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


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

    index = _load_place_index()
    if not index:
        print(
            "  warn: no spatial layers found - run outdoors_fi.py and laavu_org.py first",
            file=sys.stderr,
        )

    cache = _load_geocache()
    cache_dirty = False

    out: list[dict] = []
    unmatched: list[str] = []
    stats = {"local": 0, "nominatim": 0, "miss": 0}

    for row in data_rows:
        if not row or not row[0].strip():
            continue
        area = row[0].strip()
        sauna_names = [c.strip() for c in row[2:8] if c and c.strip()]
        if not sauna_names:
            continue

        local = _lookup_local(area, index)
        if local is not None:
            coord = local
            stats["local"] += 1
        else:
            coord = _resolve_area(area, index, cache)
            cache_dirty = True
            if coord is not None:
                stats["nominatim"] += 1
            else:
                stats["miss"] += 1
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

    if cache_dirty:
        _save_geocache(cache)

    print(
        f"  resolved {stats['local']} locally, {stats['nominatim']} via Nominatim, "
        f"{stats['miss']} unresolved"
    )
    if unmatched:
        print(f"  unresolved area(s):", file=sys.stderr)
        for u in unmatched:
            print(f"    - {u}", file=sys.stderr)

    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
