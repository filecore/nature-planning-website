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
SITE_URL = "https://wwwi3.ymparisto.fi/i3/paivanarvot/ENG/Index.htm"
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


def _latest_readings(days: int = 3) -> dict[int, tuple[float, str]]:
    """Return {Paikka_Id: (value_cm, iso_timestamp)} keeping only the
    most recent reading per station."""
    since = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    rows = _paged("Vedenkorkeus", {"$filter": f"Aika gt datetime'{since}'"})
    print(f"  {len(rows)} readings in last {days} days")

    latest: dict[int, tuple[float, str]] = {}
    for r in rows:
        pid = r.get("Paikka_Id")
        ts = r.get("Aika")
        val = r.get("Arvo")
        if pid is None or ts is None or val is None:
            continue
        prev = latest.get(pid)
        if prev is None or ts > prev[1]:
            latest[pid] = (float(val), ts)
    print(f"  {len(latest)} stations with recent data")
    return latest


def fetch_features() -> list[dict]:
    stations = _stations()
    readings = _latest_readings(days=3)

    out: list[dict] = []
    for s in stations:
        pid = s.get("Paikka_Id")
        reading = readings.get(pid)
        if not reading:
            continue
        lat = _dms_to_deg(s.get("KoordLat"))
        lon = _dms_to_deg(s.get("KoordLong"))
        if lat is None or lon is None:
            continue

        value_cm, ts = reading
        when = ts.replace("T", " ").split(".")[0]
        body_kind = "Lake" if s.get("JarviNimi") else "River"
        bits = [
            f"Water level: {value_cm:.0f} cm",
            f"as of {when}",
            f"{body_kind}: {(s.get('JarviNimi') or s.get('PaaVesalNimi') or '').strip()}",
        ]
        description = " . ".join(b for b in bits if b.strip())[:300]

        nro = (s.get("Nro") or "").strip()
        name = (s.get("Nimi") or "").strip() or f"Station {nro}"
        feature = make_feature(
            feature_id=f"syke-w-{pid}",
            name=name,
            lat=lat,
            lon=lon,
            category="water-level",
            source=SOURCE,
            source_url=f"https://wwwi3.ymparisto.fi/i3/paivanarvot/FIN/Kunta/Paikka.aspx?Paikka_ID={pid}",
            features=[body_kind.lower()],
            description=description,
        )
        if feature:
            out.append(feature)
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
