"""Adapter for current Finnish algae observations (VESLA / Levävahti).

Source: SYKE VESLA OData v3 service at
``https://rajapinnat.ymparisto.fi/api/vesla/2.0/odata/``. Citizen and
authority observations of cyanobacterial blooms are recorded as
``YmpHavainto`` rows with ``YmpSuure_Id = 10`` (ALGA, Levärunsaus, 0-3
scale). Each observation links to a sampling occasion (``Naytteenotto``)
which links to a location (``Paikka``) carrying ``KoordErLat`` /
``KoordErLong`` in WGS84.

We pull the last ``LOOKBACK_DAYS`` of non-zero observations, batch-look
up the locations, and emit one point feature per observation. The 0-3
scale becomes human labels (little / moderate / abundant) and feeds
both the category code and the popup description. Observations where
``Arvo == 0`` (no algae) are filtered out so the layer shows only
current blooms.

This is the data behind the "Algae" toggle on jaaskel.com/rannat.html,
which fuses VESLA with Algaline ferry data; we pull VESLA only.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import urllib.parse
import urllib.request

from common import make_feature, run, write_layer

NAME = "algae"
SOURCE = "SYKE VESLA citizen algae observations"
SITE_URL = "https://www.jarviwiki.fi/wiki/Levavahti"
ODATA_BASE = "https://rajapinnat.ymparisto.fi/api/vesla/2.0/odata"
LOOKBACK_DAYS = 60
PAIKKA_BATCH = 30  # how many Paikka_Ids per Paikka lookup request
USER_AGENT = "nature-aggregator/0.1 (+https://nature.togneri.net)"

LEVEL_LABELS = {
    1: ("little",     "vähän levää"),
    2: ("moderate",   "kohtalaisesti levää"),
    3: ("abundant",   "runsaasti levää"),
}


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _fetch_observations(since_iso: str) -> list[dict]:
    """Walk paginated YmpHavainto results with $expand=Naytteenotto."""
    filt = (
        f"YmpSuure_Id eq 10 and Arvo gt 0 "
        f"and Naytteenotto/Aika ge datetime'{since_iso}'"
    )
    params = {
        "$filter": filt,
        "$expand": "Naytteenotto",
        "$top": "1000",
    }
    url = ODATA_BASE + "/YmpHavainto?" + urllib.parse.urlencode(params)

    out: list[dict] = []
    page = 0
    while url:
        page += 1
        body = _http_get_json(url)
        rows = body.get("value") or []
        out.extend(rows)
        next_link = body.get("odata.nextLink") or body.get("@odata.nextLink")
        if not next_link:
            break
        if next_link.startswith("http"):
            url = next_link
        else:
            url = ODATA_BASE + "/" + next_link.lstrip("/")
        if page > 20:
            print(f"  warn: stopping after 20 pages ({len(out)} rows so far)", file=sys.stderr)
            break
    return out


def _fetch_paikat(ids: set[int]) -> dict[int, dict]:
    """Fetch every Paikka with a coordinate, batched by id."""
    result: dict[int, dict] = {}
    ids_list = sorted(ids)
    for i in range(0, len(ids_list), PAIKKA_BATCH):
        batch = ids_list[i : i + PAIKKA_BATCH]
        clause = " or ".join(f"Paikka_Id eq {pid}" for pid in batch)
        url = ODATA_BASE + "/Paikka?" + urllib.parse.urlencode({
            "$filter": clause,
            "$top": str(len(batch)),
        })
        body = _http_get_json(url)
        for row in body.get("value") or []:
            pid = row.get("Paikka_Id")
            if pid is not None:
                result[pid] = row
    return result


def _coord(paikka: dict) -> tuple[float, float] | None:
    for lat_key, lon_key in (("KoordErLat", "KoordErLong"), ("KoordLat", "KoordLong")):
        lat_raw = paikka.get(lat_key)
        lon_raw = paikka.get(lon_key)
        if lat_raw is None or lon_raw is None:
            continue
        try:
            lat = float(str(lat_raw).replace(",", "."))
            lon = float(str(lon_raw).replace(",", "."))
        except (TypeError, ValueError):
            continue
        if lat == 0 or lon == 0:
            continue
        # KoordLat/Long are degrees+decimal-minutes (e.g. "60 01,722").
        # KoordErLat/Long are clean decimal degrees. Tell them apart by
        # whether the raw string contains a space.
        if lat_key == "KoordLat" and " " in str(lat_raw):
            deg = int(str(lat_raw).split()[0])
            mins = float(str(lat_raw).split()[1].replace(",", "."))
            lat = deg + mins / 60
            deg = int(str(lon_raw).split()[0])
            mins = float(str(lon_raw).split()[1].replace(",", "."))
            lon = deg + mins / 60
        return lat, lon
    return None


def fetch_features() -> list[dict]:
    since = (_dt.date.today() - _dt.timedelta(days=LOOKBACK_DAYS)).isoformat() + "T00:00:00"
    if os.environ.get("NATURE_ALGAE_SINCE"):
        since = os.environ["NATURE_ALGAE_SINCE"]

    print(f"  fetching algae observations since {since}")
    observations = _fetch_observations(since)
    print(f"    {len(observations)} VESLA algae observations in window")

    paikat_ids = {
        (row.get("Naytteenotto") or {}).get("Paikka_Id")
        for row in observations
    }
    paikat_ids.discard(None)
    print(f"    looking up {len(paikat_ids)} distinct sampling locations")
    paikat = _fetch_paikat(paikat_ids)
    print(f"    {len(paikat)} location records resolved")

    out: list[dict] = []
    by_key: dict[tuple, dict] = {}
    for row in observations:
        sample = row.get("Naytteenotto") or {}
        pid = sample.get("Paikka_Id")
        paikka = paikat.get(pid) if pid is not None else None
        if not paikka:
            continue
        coord = _coord(paikka)
        if not coord:
            continue
        lat, lon = coord

        try:
            level = int(float(row.get("Arvo") or 0))
        except (TypeError, ValueError):
            continue
        if level < 1:
            continue
        label_short, label_fi = LEVEL_LABELS.get(level, ("present", "levää"))

        aika = sample.get("Aika") or ""
        date_part = aika.split("T")[0] if "T" in aika else aika
        name = (paikka.get("Nimi") or "(unnamed)").strip()
        comment = (sample.get("Lisatieto") or "").strip()

        # Deduplicate: keep the most recent observation per (location, level).
        key = (pid, level)
        prev = by_key.get(key)
        if prev and prev["aika"] >= aika:
            continue

        bits = [f"Algae level: {level}/3 ({label_fi})", f"Observed: {date_part}"]
        description = " · ".join(bits)
        if comment:
            description = description + "\n" + comment[:200]

        feat = make_feature(
            feature_id=f"algae-{pid}-{date_part}-{level}",
            name=name,
            lat=lat,
            lon=lon,
            category=f"algae-{label_short}",
            source=SOURCE,
            source_url=SITE_URL,
            features=[],
            description=description,
        )
        if feat:
            by_key[key] = {"aika": aika, "feature": feat}

    return [v["feature"] for v in by_key.values()]


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
