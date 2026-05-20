"""Adapter for Uiras live water-temperature sensors.

Source: Forum Virium Helsinki IoT, a LoRaWAN sensor network in the
Helsinki / Espoo / Vantaa region. Each sensor publishes its readings as
a standalone GeoJSON file at
``https://iot.fvh.fi/opendata/uiras/<device_id>.geojson``. The parent
directory is an Nginx auto-index we scrape to enumerate device IDs.

Each per-sensor file carries the latest reading in
``properties.measurement.temp_water`` plus a backlog in
``properties.data.raw``. We use only the latest reading. Sensors whose
latest reading is older than ``MAX_AGE_DAYS`` are dropped so the layer
stays a "live" view instead of a memorial to retired sensors.

This is the data behind the "Sensors" toggle on jaaskel.com/rannat.html.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request

from common import make_feature, run, write_layer

NAME = "water-sensors"
SOURCE = "Uiras (Forum Virium Helsinki IoT)"
SITE_URL = "https://iot.fvh.fi/opendata/uiras/"
LISTING_URL = SITE_URL
MAX_AGE_DAYS = 30
USER_AGENT = "nature-aggregator/0.1 (+https://nature.togneri.net)"

DEVICE_HREF_RE = re.compile(r'href="([0-9A-F]{16}\.geojson)"', re.IGNORECASE)


def _http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def _list_devices() -> list[str]:
    html = _http_get(LISTING_URL)
    return [m for m in DEVICE_HREF_RE.findall(html)]


def _parse_iso(s: str | None) -> _dt.datetime | None:
    if not s:
        return None
    # Normalise so fromisoformat accepts trailing Z and microseconds.
    s = s.strip().replace("Z", "+00:00")
    try:
        return _dt.datetime.fromisoformat(s)
    except ValueError:
        return None


def fetch_features() -> list[dict]:
    override = os.environ.get("NATURE_UIRAS_LISTING")
    if override:
        global LISTING_URL  # noqa: PLW0603
        LISTING_URL = override

    devices = _list_devices()
    print(f"  found {len(devices)} sensor files")
    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=MAX_AGE_DAYS)

    out: list[dict] = []
    skipped_stale = 0
    skipped_other = 0

    for i, device_file in enumerate(devices, 1):
        try:
            body = _http_get(urllib.parse.urljoin(SITE_URL, device_file))
            feat = json.loads(body)
        except Exception as e:
            print(f"    {device_file}: {e}", file=sys.stderr)
            skipped_other += 1
            continue

        geom = feat.get("geometry") or {}
        if geom.get("type") != "Point":
            skipped_other += 1
            continue
        try:
            lon, lat = float(geom["coordinates"][0]), float(geom["coordinates"][1])
        except (KeyError, TypeError, ValueError, IndexError):
            skipped_other += 1
            continue

        props = feat.get("properties") or {}
        measurement = props.get("measurement") or {}
        temp = measurement.get("temp_water")
        when = _parse_iso(measurement.get("time"))
        if temp is None or when is None:
            skipped_other += 1
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=_dt.timezone.utc)
        if when < cutoff:
            skipped_stale += 1
            continue

        name = (props.get("name") or "").strip()
        location = (props.get("location") or "").strip()
        display = location or name or "Uiras sensor"
        descriptor_parts = [
            f"Water: {temp} °C",
            f"Read: {when.astimezone().strftime('%Y-%m-%d %H:%M')}",
        ]
        description = " · ".join(descriptor_parts)

        f = make_feature(
            feature_id=f"uiras-{feat.get('id') or device_file.split('.')[0]}",
            name=display,
            lat=lat,
            lon=lon,
            category="water-sensor",
            source=SOURCE,
            source_url=props.get("site_url") or SITE_URL,
            features=[],
            description=description,
        )
        if f:
            out.append(f)
        if i % 20 == 0:
            print(f"    {i}/{len(devices)} processed")

    print(f"  skipped: {skipped_stale} stale (>{MAX_AGE_DAYS} days), {skipped_other} malformed")
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
