"""Adapter for tick observation density (GBIF).

The two tick species relevant to Finnish hikers are
*Ixodes ricinus* (common tick, dominant in the south) and
*Ixodes persulcatus* (taiga tick, further north and east).

Punkkilive (the Pfizer-sponsored Finnish citizen-tick app) has no
public API. THL only publishes static yearly Lyme / TBE incidence
tables. The best machine-readable open source for georeferenced
tick records is GBIF, which aggregates museum collections,
iNaturalist, and research projects.

We pull all GBIF occurrences of either species in Finland from the
last decade (year >= 2014), bin them by maakunta, and emit one
feature per region with the count and dominant species. The popup
label is honest about what the number represents: observation
density, which is a proxy for - not a direct measure of - tick risk.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

from common import REGIONS, make_feature, region_for, run, write_layer

NAME = "tick-density"
SOURCE = "GBIF: Ixodes ricinus + Ixodes persulcatus occurrences"
SITE_URL = "https://www.gbif.org/"
API = "https://api.gbif.org/v1/occurrence/search"

PAGE = 300  # GBIF default cap
MIN_YEAR = 2014


def _fetch_all(scientific_name: str) -> list[dict]:
    out: list[dict] = []
    offset = 0
    while True:
        qs = urllib.parse.urlencode({
            "country": "FI",
            "scientificName": scientific_name,
            "hasCoordinate": "true",
            "year": f"{MIN_YEAR},2030",
            "limit": PAGE,
            "offset": offset,
        })
        req = urllib.request.Request(f"{API}?{qs}", headers={"User-Agent": "nature-aggregator/0.1"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
        results = body.get("results") or []
        out.extend(results)
        if body.get("endOfRecords") or len(results) < PAGE:
            return out
        offset += PAGE


def _level(count: int, threshold_low: int, threshold_high: int) -> str:
    if count == 0:
        return "None"
    if count < threshold_low:
        return "Low"
    if count < threshold_high:
        return "Moderate"
    return "High"


def fetch_features() -> list[dict]:
    print("  fetching Ixodes ricinus from GBIF")
    ricinus = _fetch_all("Ixodes ricinus")
    print(f"    {len(ricinus)} records")
    print("  fetching Ixodes persulcatus from GBIF")
    persulcatus = _fetch_all("Ixodes persulcatus")
    print(f"    {len(persulcatus)} records")

    # Bin by maakunta.
    counts: dict[str, dict[str, int]] = {name: {"ricinus": 0, "persulcatus": 0} for name, _, _ in REGIONS}
    # Per-(region, year) total tick records so the frontend time-window
    # slider can derive a windowed total per maakunta. Species-split is
    # intentionally not preserved here - the popup already shows the
    # all-time species mix and that's the more useful number.
    by_year: dict[str, dict[int, int]] = {name: {} for name, _, _ in REGIONS}
    for rec, species_key in ((ricinus, "ricinus"), (persulcatus, "persulcatus")):
        for r in rec:
            lat = r.get("decimalLatitude")
            lon = r.get("decimalLongitude")
            if lat is None or lon is None:
                continue
            region = region_for(lat, lon)
            if region in counts:
                counts[region][species_key] += 1
                year = r.get("year")
                if isinstance(year, int) and MIN_YEAR <= year <= 2030:
                    by_year[region][year] = by_year[region].get(year, 0) + 1

    # Calibrate thresholds against the actual distribution so the
    # labels mean something. Compare to the median + max of the
    # combined-per-region totals.
    totals = sorted(c["ricinus"] + c["persulcatus"] for c in counts.values())
    if totals and totals[-1] > 0:
        median = totals[len(totals) // 2] or 1
        threshold_low = max(1, median // 2)
        threshold_high = max(threshold_low + 1, totals[-1] // 2)
    else:
        threshold_low, threshold_high = 1, 10

    out: list[dict] = []
    for region_name, rlat, rlon in REGIONS:
        bucket = counts[region_name]
        total = bucket["ricinus"] + bucket["persulcatus"]
        level = _level(total, threshold_low, threshold_high)
        bits = [
            f"Tick observation density: {level}",
            f"Records since {MIN_YEAR}: {total}",
        ]
        if bucket["ricinus"]:
            bits.append(f"Ixodes ricinus (common tick): {bucket['ricinus']}")
        if bucket["persulcatus"]:
            bits.append(f"Ixodes persulcatus (taiga tick): {bucket['persulcatus']}")
        if total == 0:
            bits.append("(No GBIF records - absence of evidence, not evidence of absence)")
        description = " . ".join(bits)

        tags = [f"density-{level.lower()}"]
        if bucket["ricinus"] > 0:
            tags.append("ricinus")
        if bucket["persulcatus"] > 0:
            tags.append("persulcatus")

        feature = make_feature(
            feature_id=f"tick-{region_name.lower().replace(' ', '-')}",
            name=f"{region_name}: ticks {level.lower()}",
            lat=rlat,
            lon=rlon,
            category="tick-density",
            source=SOURCE,
            source_url=f"https://www.gbif.org/occurrence/search?country=FI&taxon_key=Ixodes",
            features=tags,
            description=description[:400],
            region=region_name,
        )
        if feature:
            feature["properties"]["by_year"] = {str(y): n for y, n in sorted(by_year[region_name].items())}
            out.append(feature)
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
