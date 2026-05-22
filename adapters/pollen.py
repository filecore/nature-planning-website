"""Adapter for the daily pollen forecast (Open-Meteo).

Norkko (the Finnish pollen authority at the University of Turku) does
not expose a public API; their site renders forecast images from
internal WordPress data. The cleanest open source for georeferenced
pollen counts is Open-Meteo's free Air Quality API, which serves the
European CAMS pollen forecast hour-by-hour, no key required:

  https://air-quality-api.open-meteo.com/v1/air-quality

We sample today's forecast at each of Finland's 19 maakunta
centroids (already defined in ``common.REGIONS``) and emit one
feature per region. The popup shows today's peak per species so
the user can see which pollens are active where they're going.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
import urllib.parse
import urllib.request

from common import REGIONS, make_feature, run, write_layer

NAME = "pollen"
SOURCE = "Open-Meteo Air Quality (European CAMS pollen forecast)"
SITE_URL = "https://open-meteo.com/en/docs/air-quality-api"
API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

SPECIES = ["alder_pollen", "birch_pollen", "grass_pollen", "mugwort_pollen", "olive_pollen", "ragweed_pollen"]
SPECIES_LABELS = {
    "alder_pollen":   "Alder",
    "birch_pollen":   "Birch",
    "grass_pollen":   "Grass",
    "mugwort_pollen": "Mugwort",
    "olive_pollen":   "Olive",
    "ragweed_pollen": "Ragweed",
}

# Common (and admittedly rough) thresholds in grains/m^3 for the
# headline level. Species-specific cutoffs vary; these are a
# defensible mid-line that matches Norkko's public colour codes
# closely enough for a "is today bad for pollen?" glance.
def _level(value: float) -> str:
    if value <= 0:
        return "None"
    if value < 10:
        return "Low"
    if value < 50:
        return "Moderate"
    if value < 100:
        return "High"
    return "Very high"


def _fetch_one(lat: float, lon: float) -> dict:
    qs = urllib.parse.urlencode({
        "latitude": f"{lat:.3f}",
        "longitude": f"{lon:.3f}",
        "hourly": ",".join(SPECIES),
        "timezone": "auto",
        "forecast_days": 1,
    })
    url = f"{API_URL}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": "nature-aggregator/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _today_peaks(body: dict) -> dict[str, float]:
    hourly = body.get("hourly") or {}
    times = hourly.get("time") or []
    today = _dt.date.today().isoformat()
    keep_idx = [i for i, t in enumerate(times) if t.startswith(today)]
    out: dict[str, float] = {}
    for sp in SPECIES:
        series = hourly.get(sp) or []
        if not series:
            continue
        vals = [series[i] for i in keep_idx if i < len(series) and series[i] is not None]
        if vals:
            out[sp] = max(vals)
    return out


def fetch_features() -> list[dict]:
    out: list[dict] = []
    for region_name, rlat, rlon in REGIONS:
        try:
            body = _fetch_one(rlat, rlon)
        except Exception as e:
            print(f"  {region_name}: fetch failed - {e}")
            continue
        peaks = _today_peaks(body)
        if not peaks:
            continue

        # Headline = the species with the highest peak.
        top_sp, top_val = max(peaks.items(), key=lambda kv: kv[1])
        top_label = SPECIES_LABELS.get(top_sp, top_sp)
        top_level = _level(top_val)

        # Build a sorted summary of every species we have data for.
        ordered = sorted(peaks.items(), key=lambda kv: -kv[1])
        species_lines = [
            f"{SPECIES_LABELS.get(sp, sp)} {val:.1f} ({_level(val)})"
            for sp, val in ordered
        ]
        description = f"Peak today (grains/m^3): " + ", ".join(species_lines)

        tags = [f"level-{top_level.lower().replace(' ', '-')}"]
        if top_val > 0:
            tags.append(f"top-{top_sp.replace('_pollen','')}")

        feature = make_feature(
            feature_id=f"pollen-{region_name.lower().replace(' ', '-')}",
            name=f"{region_name}: {top_label} {top_level.lower()}",
            lat=rlat,
            lon=rlon,
            category="pollen",
            source=SOURCE,
            source_url=SITE_URL,
            features=tags,
            description=description[:400],
            region=region_name,
        )
        if feature:
            out.append(feature)
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
