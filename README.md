# nature.togneri.net

One-stop aggregator for Finnish outdoor planning resources. Pure static site
(Leaflet + vanilla JS) served at
https://nature.togneri.net/.

## What it does

- Renders an interactive map with waypoints from multiple Finnish outdoor datasets.
- Lets you filter waypoints by category, region, and features
  (sauna / fire pit / laavu / kota).
- Curated link directory for resources that cannot reasonably be mapped
  (tools, wikis, weather radar, Google My Maps lists, GPS-device maps).
- Local-only favourites via browser localStorage.

## Stack

- nginx:alpine container, no application backend.
- Frontend: vanilla HTML + CSS + JS, Leaflet for the map.
- Data layers: pre-built GeoJSON files in `src/data/layers/`, produced locally
  by Python adapters in `adapters/`. Refresh is a manual step; see below.
- Reverse proxy: Traefik on the homelab server, subdomain routed via Cloudflare Companion.

## Refresh data

```
bash refresh.sh
```

The script runs each adapter, writes a normalised GeoJSON to
`src/data/layers/<name>.geojson`, and refuses to overwrite an existing file
with zero features. All adapters use only the Python standard library; no
pip install required.

The full cycle is `bash refresh.sh && bash deploy.sh`. Run it monthly or
when you notice stale data.

## Deploy

```
bash deploy.sh
```

Requires a populated `.env` with `REMOTE_HOST`, `REMOTE_DIR`, and
`NATURE_DOMAIN`. The script rsyncs the tree to the homelab server and recreates the
container; Cloudflare Companion auto-creates the DNS record from the
Traefik labels.

## Adding a new data source

The hard part of any new source is finding a clean machine-readable feed.
This is the workflow used to wire up the current three layers; apply the
same pattern when you spot a new site worth pulling in.

### 1. Triage what shape of data the site exposes

In rough order of preference (most to least convenient):

1. **A documented open-data catalogue entry** — search the site name plus
   "avoindata" or "open data" on https://avoindata.suomi.fi/ or
   https://www.avoindata.fi/. CKAN datasets list their resources with
   format labels (GeoJSON, WFS, Shapefile, CSV, KML). Query the CKAN API
   for resource URLs:
   ```
   curl -sL 'https://avoindata.suomi.fi/data/api/3/action/package_show?id=<slug>' \
     | python3 -m json.tool
   ```
2. **A "download as GPX / KML / CSV / GeoJSON" link on the site** — laavu.org
   does this at https://laavu.org/lataa.php?paikkakunta=kaikki (returns a
   single GPX with all ~4500 waypoints). Pikakartta and similar tools
   often have analogous buttons.
3. **A Google Sheet with public viewing** — append `/export?format=csv` to
   the share URL to get a CSV. Used for the saunas list.
4. **A WMS / WFS endpoint** — open `GetCapabilities` in the browser to list
   feature types. GeoServer responds to `outputFormat=application/json` with
   GeoJSON, which is what `outdoors_fi.py` uses against
   https://paikkatiedot.ymparisto.fi/geoserver/inspire_ps/wfs.
5. **A Google My Maps embed** — extract the `mid=` query parameter and
   either iframe it under `src/data/sources.json` (with `embedUrl`), or use
   `https://www.google.com/maps/d/kml?mid=<id>&forcekml=1` to grab the
   underlying KML.
6. **An interactive map with no obvious download** — open browser DevTools,
   filter the Network tab to XHR / Fetch, then pan / zoom the map. Whatever
   endpoint the site polls for markers is your adapter's data source. Look
   for responses with `application/json` or `application/vnd.google-earth.kml`.
7. **Nothing of the above** — last resort, scrape the HTML. Tedious and
   fragile; consider keeping the site as an outbound link in
   `src/data/sources.json` instead.

### 2. Write an adapter

Copy the closest existing adapter as a template:

| Existing adapter | Best when the new source looks like |
|---|---|
| `outdoors_fi.py` | WFS / GeoServer endpoint with polygon features |
| `laavu_org.py`   | Single bulk GPX / KML download with hundreds of points |
| `saunas_sheet.py`| Google Sheet (or other tabular) joined to an existing layer |

Every adapter must:

- Be a runnable module with a `main()` that calls `common.write_layer(...)`.
- Emit `Point` (use `common.make_feature`) or `Polygon` / `MultiPolygon`
  (use `common.make_polygon_feature` which auto-simplifies coordinates).
- Set normalised feature tags like `has-sauna`, `has-fire-pit`,
  `has-laavu`, `enclosed-fire` so the frontend filter chips light up
  correctly.
- Read its primary URL from an env var override (e.g. `NATURE_<NAME>_FEED`)
  so the source can be redirected without editing code.
- Fail loudly via `RuntimeError` if the source returns zero features, so a
  silent breakage does not overwrite a known-good layer with empty data.

### 3. Register and ship

1. Add the module to the `ADAPTERS=(...)` list in `refresh.sh`.
2. Add the layer to `LAYERS` in `src/static/js/app.js` (one line with id,
   filename, label, marker colour, letter).
3. Optionally add a card to `src/data/sources.json` for an outbound link
   that lives alongside the mapped data.
4. `bash refresh.sh && bash deploy.sh`.

### Offline-export adapters

Some sources cannot be live-fetched (paid APIs, unlisted Google My Maps,
sites that load coordinates from a JS-only endpoint). For these, drop a
hand-exported file at `data/manual/<name>.<ext>` and write a thin
adapter that reads it. The pattern is captured in `adapters/sacred_sites.py`:

- The adapter raises a sentinel exception when the manual file is missing
  and its `main()` soft-skips (prints a notice, exits clean) so the rest
  of `refresh.sh` is unaffected. The layer just stays empty until the
  file appears.
- `data/manual/README.md` lists every expected file with download steps.
- Manual files ARE committed to git so a fresh clone can rebuild the
  layer without a re-export.

### Sources currently outside the map

The site at https://www.tulikartta.fi/ (fire spots) moved to a paid
subscription model in 2026 and is no longer parseable for free. It remains
in `sources.json` as an outbound link. Data dropped into `data/manual/tulikartta.kml` and a small adapter can
bring the layer back.

A few other interesting datasets remain link-only in
`src/data/sources.json` (winter routes, retkipaikka tips, Uuvi list).
Promoting any of these to a real mapped layer is exactly the workflow
above. (kyppi.fi is already mapped as the **archaeology** layer via the
Museovirasto WFS; järviwiki is mapped as the **lakes** layer via its
Semantic MediaWiki API.)

## Out of scope

Accounts, server-side favourites, GPX import/export, offline / PWA,
reverse-engineering Google My Maps beyond iframe embedding.
