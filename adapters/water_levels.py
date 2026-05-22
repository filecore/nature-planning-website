"""Adapter for river / lake water level stations (SYKE Hydrologiarajapinta).

SYKE exposes hydrological monitoring data via an OData 3 API. We pull:

* All Paikka entities filtered to Suure_Id=1 (water level, "W")
  - ~1750 stations across Finnish rivers and lakes.
* All Vedenkorkeus records from the last few days, and keep the
  most recent value per Paikka_Id.

Coordinates come as DDMMSS strings in ``KoordLat`` / ``KoordLong``
(e.g. "622536" = 62 deg 25 min 36 sec) which we convert to decimal
degrees.

Stations with no recent reading are skipped: the popup needs a
headline number to be useful, and the hiker doesn't gain anything
from a marker that just says "no data".
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
import urllib.parse
import urllib.request

from common import make_feature, run, write_layer

NAME = "water-levels"
SOURCE = "SYKE: hydrological monitoring stations (Vedenkorkeus)"
SITE_URL = "https://www.vesi.fi/en/water-situation/"
API_ROOT = "https://rajapinnat.ymparisto.fi/api/Hydrologiarajapinta/1.1/odata"

PAGE = 500  # SYKE server caps responses at 500 rows


def _fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": "nature-aggregator/0.1",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read())


def _paged(path: str, query: dict) -> list[dict]:
    out: list[dict] = []
    skip = 0
    while True:
        qs = dict(query, **{"$top": PAGE, "$skip": skip})
        url = f"{API_ROOT}/{path}?" + urllib.parse.urlencode(qs, safe="$:'")
        body = _fetch(url)
        chunk = body.get("value") or []
        out.extend(chunk)
        if len(chunk) < PAGE:
            return out
        skip += PAGE


def _dms_to_deg(s: str) -> float | None:
    # "622536" -> 62 + 25/60 + 36/3600. Also handle "62 25 36" forms.
    if not s:
        return None
    s = s.strip().replace(" ", "")
    if not s.isdigit() or len(s) < 4:
        return None
    # Right-most two digits = seconds, next two = minutes, rest = degrees.
    deg = int(s[:-4])
    minutes = int(s[-4:-2])
    seconds = int(s[-2:])
    return deg + minutes / 60.0 + seconds / 3600.0


def _stations() -> list[dict]:
    rows = _paged("Paikka", {"$filter": "Suure_Id eq 1"})
    print(f"  {len(rows)} water-level stations")
    return rows


def _readings_window(days: int) -> list[dict]:
    since = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    rows = _paged("Vedenkorkeus", {"$filter": f"Aika gt datetime'{since}'"})
    print(f"  {len(rows)} Vedenkorkeus rows in last {days} days")
    return rows


def _summarise(rows: list[dict]) -> dict[int, dict]:
    """Group rows by Paikka_Id; return per-station latest value plus
    min/median/max across the window."""
    buckets: dict[int, list[tuple[str, float]]] = {}
    for r in rows:
        pid = r.get("Paikka_Id")
        ts = r.get("Aika")
        val = r.get("Arvo")
        if pid is None or ts is None or val is None:
            continue
        buckets.setdefault(pid, []).append((ts, float(val)))

    summary: dict[int, dict] = {}
    for pid, items in buckets.items():
        items.sort(key=lambda x: x[0])  # by Aika asc
        values = [v for _, v in items]
        latest_ts, latest_val = items[-1]
        values_sorted = sorted(values)
        median = values_sorted[len(values_sorted) // 2]
        summary[pid] = {
            "latest_cm": latest_val,
            "latest_ts": latest_ts,
            "min_cm": min(values),
            "max_cm": max(values),
            "median_cm": median,
            "samples": len(values),
        }
    print(f"  {len(summary)} stations with data summarised")
    return summary


def fetch_features() -> list[dict]:
    stations = _stations()
    rows = _readings_window(days=30)
    summary = _summarise(rows)

    out: list[dict] = []
    for s in stations:
        pid = s.get("Paikka_Id")
        stats = summary.get(pid)
        if not stats:
            continue
        lat = _dms_to_deg(s.get("KoordLat"))
        lon = _dms_to_deg(s.get("KoordLong"))
        if lat is None or lon is None:
            continue

        latest_m = stats["latest_cm"] / 100.0
        median_m = stats["median_cm"] / 100.0
        min_m = stats["min_cm"] / 100.0
        max_m = stats["max_cm"] / 100.0
        diff_cm = stats["latest_cm"] - stats["median_cm"]
        sign = "+" if diff_cm >= 0 else ""
        when = stats["latest_ts"].replace("T", " ").split(".")[0]
        body_kind = "Lake" if s.get("JarviNimi") else "River"

        bits = [
            f"Water level: {latest_m:.2f} m ({sign}{diff_cm:.0f} cm vs 30d median)",
            f"30-day median: {median_m:.2f} m",
            f"30-day range: {min_m:.2f} - {max_m:.2f} m ({stats['samples']} readings)",
            f"as of {when}",
            f"{body_kind}: {(s.get('JarviNimi') or s.get('PaaVesalNimi') or '').strip()}",
        ]
        description = " . ".join(b for b in bits if b.strip())[:400]

        nro = (s.get("Nro") or "").strip()
        name = (s.get("Nimi") or "").strip() or f"Station {nro}"

        # Tag whether the current reading is above / below / near the
        # 30-day median so the UI could colour-code later if wanted.
        if abs(diff_cm) < 5:
            level_tag = "level-normal"
        elif diff_cm > 0:
            level_tag = "level-above"
        else:
            level_tag = "level-below"

        feature = make_feature(
            feature_id=f"syke-w-{pid}",
            name=name,
            lat=lat,
            lon=lon,
            category="water-level",
            source=SOURCE,
            source_url=SITE_URL,  # vesi.fi has no per-station deep link; landing page only.
            features=[body_kind.lower(), level_tag],
            description=description,
        )
        if feature:
            out.append(feature)
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
