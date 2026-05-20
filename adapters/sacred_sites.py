"""Adapter for "Suomen luonnon pyhäpaikat" (Finnish natural sacred sites).

This is a manual-export adapter: the upstream is a private / unlisted
Google My Maps whose ``mid`` is not derivable from the public Facebook
post that links to it. Drop a KML export at
``data/manual/pyhat_paikat.kml`` (see ``data/manual/README.md`` for the
download steps) and this adapter will parse it.

If the manual file is absent, the adapter exits cleanly (zero features +
informative message) rather than failing the whole refresh -- the layer
just stays empty until the file appears.
"""

from __future__ import annotations

import os
import pathlib
import re
import sys
from xml.etree import ElementTree as ET

from common import make_feature, run, write_layer

NAME = "sacred-sites"
SOURCE = "Suomen luonnon pyhapaikat (manual export)"
SITE_URL = "https://www.facebook.com/pyhatpaikat/"
MANUAL_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "manual" / "pyhat_paikat.kml"

KML_NS = {"k": "http://www.opengis.net/kml/2.2"}


class MissingManualFile(Exception):
    """Raised when the user has not yet placed the expected KML export."""


def _strip_html(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def _parse_kml(payload: bytes) -> list[dict]:
    root = ET.fromstring(payload)
    out: list[dict] = []
    for pm in root.iter("{http://www.opengis.net/kml/2.2}Placemark"):
        name_el = pm.find("k:name", KML_NS)
        if name_el is None or not name_el.text:
            continue
        name = name_el.text.strip()
        desc_el = pm.find("k:description", KML_NS)
        desc = _strip_html(desc_el.text or "") if desc_el is not None else ""

        coord_el = pm.find(".//k:Point/k:coordinates", KML_NS)
        if coord_el is None or not coord_el.text:
            continue
        try:
            parts = coord_el.text.strip().split(",")
            lon, lat = float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            continue

        feature_id = "sacred-" + re.sub(r"[^a-z0-9]+", "-", name.lower())[:60] + f"-{lat:.4f}-{lon:.4f}"
        f = make_feature(
            feature_id=feature_id,
            name=name,
            lat=lat,
            lon=lon,
            category="sacred-site",
            source=SOURCE,
            source_url=SITE_URL,
            features=[],
            description=desc[:400],
        )
        if f:
            out.append(f)
    return out


def fetch_features() -> list[dict]:
    path_override = os.environ.get("NATURE_SACRED_KML")
    path = pathlib.Path(path_override) if path_override else MANUAL_PATH
    if not path.exists():
        raise MissingManualFile(
            f"No manual KML at {path}. See data/manual/README.md for export steps."
        )
    return _parse_kml(path.read_bytes())


def main():
    try:
        feats = fetch_features()
    except MissingManualFile as e:
        # Soft-skip: do not overwrite a previous layer file with empty
        # contents, but do not break refresh.sh either.
        print(f"  skipped: {e}")
        return None
    return write_layer(NAME, SOURCE, SITE_URL, feats)


if __name__ == "__main__":
    sys.exit(run(main, name=NAME))
