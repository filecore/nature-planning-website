"""Adapter for live air quality monitoring stations (FMI).

Two FMI open-data WFS calls combined into one layer:

1. ``fmi::ef::stations&networkid=151`` returns the 148 Finnish air
   quality monitoring stations (name, fmisid, lat/lon).
2. ``urban::observations::airquality::hourly::simple`` returns hourly
   pollutant readings for all stations. We keep only the latest
   ``AQINDEX_PT1H_avg`` per station (FMI's combined 1-5 air quality
   index: 1=good, 5=very poor).

Each station feature exposes the AQI value and a human-readable
quality label so the popup can render a single intuitive headline.
Stations with no recent AQI reading are still included (so users know
the station exists) but flagged as "no recent data".
"""

from __future__ import annotations

import datetime as _dt
import sys
import urllib.request
import xml.etree.ElementTree as ET

from common import make_feature, run, write_layer

NAME = "air-quality"
SOURCE = "FMI: air quality observations (network 151)"
SITE_URL = "https://en.ilmatieteenlaitos.fi/air-quality"
WFS_URL = "https://opendata.fmi.fi/wfs"

GML_NS = "{http://www.opengis.net/gml/3.2}"
EF_NS = "{http://inspire.ec.europa.eu/schemas/ef/4.0}"
BSWFS_NS = "{http://xml.fmi.fi/schema/wfs/2.0}"

AQI_LABELS = {
    1: "Good",
    2: "Satisfactory",
    3: "Fair",
    4: "Poor",
    5: "Very poor",
}


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "nature-aggregator/0.1"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def _stations() -> list[dict]:
    url = f"{WFS_URL}?service=WFS&version=2.0.0&request=getFeature&storedquery_id=fmi::ef::stations&networkid=151"
    root = ET.fromstring(_fetch(url))
    out: list[dict] = []
    for fac in root.iter(f"{EF_NS}EnvironmentalMonitoringFacility"):
        fmisid = None
        for nm in fac.findall(f".//{GML_NS}identifier"):
            if "fmisid" in (nm.get("codeSpace") or ""):
                fmisid = (nm.text or "").strip()
                break
        name = None
        for nm in fac.findall(f".//{GML_NS}name"):
            if (nm.get("codeSpace") or "").endswith("locationcode/name"):
                name = (nm.text or "").strip()
                break
        pos = fac.find(f".//{GML_NS}pos")
        if pos is None or not pos.text or not fmisid:
            continue
        try:
            lat_s, lon_s = pos.text.strip().split()[:2]
            lat = float(lat_s)
            lon = float(lon_s)
        except (ValueError, IndexError):
            continue
        out.append({"fmisid": fmisid, "name": name or fmisid, "lat": lat, "lon": lon})
    return out


def _latest_aqi() -> dict[tuple[float, float], tuple[float, str]]:
    """Map rounded (lat, lon) -> (latest AQI, iso timestamp)."""
    end = _dt.datetime.now(_dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - _dt.timedelta(hours=4)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    url = (
        f"{WFS_URL}?service=WFS&version=2.0.0&request=getFeature"
        f"&storedquery_id=urban::observations::airquality::hourly::simple"
        f"&parameters=AQINDEX_PT1H_avg"
        f"&starttime={start.strftime(fmt)}&endtime={end.strftime(fmt)}"
    )
    root = ET.fromstring(_fetch(url))

    readings: dict[tuple[float, float], tuple[str, float]] = {}
    for el in root.iter(f"{BSWFS_NS}BsWfsElement"):
        pos = el.find(f".//{GML_NS}pos")
        time_el = el.find(f"{BSWFS_NS}Time")
        val_el = el.find(f"{BSWFS_NS}ParameterValue")
        if pos is None or time_el is None or val_el is None:
            continue
        try:
            lat_s, lon_s = pos.text.strip().split()[:2]
            key = (round(float(lat_s), 4), round(float(lon_s), 4))
            value = float(val_el.text)
        except (ValueError, AttributeError, IndexError):
            continue
        if value != value:  # NaN guard
            continue
        ts = (time_el.text or "").strip()
        # Keep the most recent reading per location.
        prev = readings.get(key)
        if prev is None or ts > prev[0]:
            readings[key] = (ts, value)

    return {k: (v[1], v[0]) for k, v in readings.items()}


def fetch_features() -> list[dict]:
    stations = _stations()
    print(f"  {len(stations)} stations")
    aqi = _latest_aqi()
    print(f"  {len(aqi)} stations with recent AQI")

    out: list[dict] = []
    matched = 0
    for s in stations:
        key = (round(s["lat"], 4), round(s["lon"], 4))
        reading = aqi.get(key)
        bits = []
        feat_tags = ["air-quality"]
        if reading:
            matched += 1
            value, ts = reading
            label = AQI_LABELS.get(int(round(value)), f"AQI {value:.1f}")
            bits.append(f"AQI {value:.1f}: {label}")
            bits.append(f"as of {ts.replace('Z','').replace('T',' ')} UTC")
            feat_tags.append(f"aqi-{int(round(value))}")
        else:
            bits.append("No recent AQI reading")
            feat_tags.append("aqi-none")
        description = " . ".join(bits)[:300]
        feature = make_feature(
            feature_id=f"fmi-{s['fmisid']}",
            name=s["name"],
            lat=s["lat"],
            lon=s["lon"],
            category="air-quality",
            source=SOURCE,
            source_url=f"https://en.ilmatieteenlaitos.fi/observation-stations?p_p_id=fmiairqualitydata_WAR_fmiairqualitydataportlet&observationStationId={s['fmisid']}",
            features=feat_tags,
            description=description,
        )
        if feature:
            out.append(feature)
    print(f"  {matched} stations matched to AQI readings")
    return out


def main():
    return write_layer(NAME, SOURCE, SITE_URL, fetch_features())


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
