# Manual data exports

This directory is the home for hand-placed source files used by adapters
that cannot live-fetch their upstream (paid APIs, private maps,
JS-only sites without a coord feed, retired endpoints, etc.).

The convention is one file per source, named to match the adapter that
reads it. The file is committed alongside the code so a fresh clone can
build the layer without manual steps.

## Current expectations

| Adapter | Manual file | Format | Where to obtain |
|---|---|---|---|
| `adapters/sacred_sites.py` | `pyhat_paikat.csv` (preferred) or `pyhat_paikat.kml` | CSV with `name,lat,lon,description`; or KML | The upstream is a Google Maps **List** (not My Maps); Google does not expose List pin data and there is no KML export. Two options: (a) install a Chrome extension such as "Maps List Export" or "Map Exporter for Google Maps", open the list, export to CSV, save here; or (b) hand-curate the CSV using `pyhat_paikat.csv.example` as a template. CSV wins if both files are present. |
| `adapters/uuvi_csv.py` | `uuvi.csv` | CSV (`name,lat,lon,services`) | uuvi.fi has no public coord feed. Either curate by hand or run a one-off geocode of the destination names through Nominatim and drop the result here. |
| `adapters/tulikartta_archive.py` | `tulikartta.kml` | KML | Optional: if you have a pre-paywall KML download of fire-spots from when tulikartta.fi was free, drop it here and the layer comes back. |

## Refreshing a manual file

Re-export from the upstream when the source has changed. Then commit the
new file. The next `bash refresh.sh && bash deploy.sh` picks it up
automatically -- no code changes needed unless the schema shifts.

## What NOT to put here

- Anything an adapter could fetch live (use `NATURE_<NAME>_FEED` env vars
  instead).
- Secrets (API keys, OAuth tokens).
- Generated GeoJSON output (that lives in `src/data/layers/` and is
  written by adapters, not hand-edited).
