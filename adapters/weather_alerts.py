"""Adapter for FMI weather warnings (CAP Atom feed).

There's no public trail-closure API for Metsähallitus (luontoon.fi is
a closed Next.js app with no exposed endpoints). The most relevant
proxy for "what trails should I avoid today" is the Finnish
Meteorological Institute's Common Alerting Protocol (CAP) feed:
wind warnings, thunderstorm warnings, forest-fire warnings, ice and
cold warnings - the same alerts Metsähallitus pushes to its own
poikkeavaa pages.

Source: ``https://alerts.fmi.fi/cap/feed/atom_en-GB.xml``

Each Atom entry wraps a CAP ``<alert>`` document. We read the English
``<info>`` block from each, then emit one feature per ``<area>``
inside it (each warning typically spans multiple maakunnat or
kuntas). The marker is placed at the polygon centroid so the map
isn't drowned in big translucent polygons.

Skip alerts already expired; keep onset-in-the-future ones (those
are imminent and useful for planning).
"""

from __future__ import annotations

import datetime as _dt
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

from common import make_feature, run, write_layer

NAME = "weather-alerts"
SOURCE = "FMI weather warnings (CAP)"
SITE_URL = "https://en.ilmatieteenlaitos.fi/warnings"
FEED_URL = "https://alerts.fmi.fi/cap/feed/atom_en-GB.xml"

ATOM_NS = "{http://www.w3.org/2005/Atom}"
CAP_NS = "{urn:oasis:names:tc:emergency:cap:1.2}"

# Per-event marker hints so the UI can colour-code in the popup text.
EVENT_LABELS = {
    "wind":            "Wind",
    "thunderstorm":    "Thunderstorm",
    "rain":            "Heavy rain",
    "snow":            "Heavy snow",
    "forest_fire":     "Forest fire",
    "grass_fire":      "Grass fire",
    "ice":             "Ice",
    "cold":            "Cold",
    "heat":            "Heat",
    "flooding":        "Flooding",
    "fog":             "Fog",
    "uv":              "UV",
}


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "nature-aggregator/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _parse_polygon(text: str) -> list[tuple[float, float]] | None:
    """CAP polygon: whitespace-separated 'lat,lon' pairs. Returns list of (lat,lon)."""
    if not text:
        return None
    out: list[tuple[float, float]] = []
    for tok in text.split():
        if "," not in tok:
            continue
        try:
            lat, lon = tok.split(",")
            out.append((float(lat), float(lon)))
        except (ValueError, IndexError):
            continue
    return out if len(out) >= 3 else None


def _centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return ((min(lats) + max(lats)) / 2.0, (min(lons) + max(lons)) / 2.0)


def _iso_to_dt(s: str) -> _dt.datetime | None:
    if not s:
        return None
    # CAP timestamps include a tz offset like "2026-05-26T06:00:00+03:00".
    try:
        return _dt.datetime.fromisoformat(s)
    except ValueError:
        return None


def _short_time(dt: _dt.datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(_dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def fetch_features() -> list[dict]:
    root = ET.fromstring(_fetch(FEED_URL))
    now = _dt.datetime.now(_dt.timezone.utc)

    out: list[dict] = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        alert = entry.find(f".//{CAP_NS}alert")
        if alert is None:
            continue
        identifier = (alert.findtext(f"{CAP_NS}identifier") or "").strip()
        for info in alert.findall(f"{CAP_NS}info"):
            lang = (info.findtext(f"{CAP_NS}language") or "").strip()
            if not lang.startswith("en"):
                continue
            expires = _iso_to_dt(info.findtext(f"{CAP_NS}expires"))
            if expires and expires < now:
                continue

            event = (info.findtext(f"{CAP_NS}event") or "").strip()
            severity = (info.findtext(f"{CAP_NS}severity") or "").strip()
            headline = (info.findtext(f"{CAP_NS}headline") or "").strip()
            description = (info.findtext(f"{CAP_NS}description") or "").strip()
            web = (info.findtext(f"{CAP_NS}web") or "").strip() or SITE_URL
            code = (info.findtext(f"{CAP_NS}eventCode/{CAP_NS}value") or "").strip()
            onset = _iso_to_dt(info.findtext(f"{CAP_NS}onset"))

            event_label = EVENT_LABELS.get(code, event or code or "Alert")

            for area in info.findall(f"{CAP_NS}area"):
                area_desc = (area.findtext(f"{CAP_NS}areaDesc") or "").strip()
                pts = _parse_polygon(area.findtext(f"{CAP_NS}polygon") or "")
                if not pts:
                    continue
                lat, lon = _centroid(pts)
                bits = [
                    f"{event_label} ({severity})" if severity else event_label,
                    headline,
                ]
                if onset:
                    bits.append(f"From {_short_time(onset)}")
                if expires:
                    bits.append(f"Until {_short_time(expires)}")
                if description and description != headline:
                    bits.append(description)
                popup = " . ".join(b for b in bits if b)[:500]

                tags = ["weather-alert"]
                if code:
                    tags.append(f"event-{code}")
                if severity:
                    tags.append(f"severity-{severity.lower()}")

                feat_id = f"fmi-{_slug(identifier)}-{_slug(area_desc)}"
                feature = make_feature(
                    feature_id=feat_id,
                    name=f"{event_label}: {area_desc}",
                    lat=lat,
                    lon=lon,
                    category="weather-alert",
                    source=SOURCE,
                    source_url=web,
                    features=tags,
                    description=popup,
                )
                if feature:
                    out.append(feature)
    return out


def main():
    features = fetch_features()
    if not features:
        # Empty alerts feed is a valid state (calm weather); write a
        # minimal placeholder so the frontend doesn't 404 the layer.
        import json as _json
        import pathlib as _pl
        out = _pl.Path(__file__).resolve().parent.parent / "src" / "data" / "layers" / f"{NAME}.geojson"
        payload = {
            "type": "FeatureCollection",
            "generated_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": SOURCE,
            "source_url": SITE_URL,
            "features": [],
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        print(f"  wrote empty {NAME}.geojson (no active alerts)")
        return out
    return write_layer(NAME, SOURCE, SITE_URL, features)


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
