# nature.togneri.net

One-stop aggregator for Finnish outdoor planning resources. Pure static site
(Leaflet + vanilla JS) served by nginx behind Traefik on the homelab server at
https://nature.togneri.net/.

## What it does

- Renders an interactive map with waypoints from multiple Finnish outdoor datasets.
- Lets you filter waypoints by category, region, and features
  (sauna / fire pit / laavu / accessible / winter route).
- Curated link directory for resources that cannot reasonably be mapped
  (tools, wikis, weather radar, Google My Maps lists, GPS-device maps).
- Local-only favourites via browser localStorage.

## Stack

- nginx:alpine container, no application backend.
- Frontend: vanilla HTML + CSS + JS, Leaflet for the map.
- Data layers: pre-built GeoJSON files in `src/data/layers/`, produced locally
  by Python adapters in `adapters/`. Refresh is a manual step; see below.
- Reverse proxy: Traefik on the homelab server, subdomain routed via Cloudflare Companion.

## Layout

```
nature/
  docker-compose.yml      nginx:alpine + Traefik labels (uses ${NATURE_DOMAIN})
  nginx.conf              site config bind-mounted into the container
  .env.example            copy to .env and fill in
  deploy.sh               rsync to the homelab server + docker compose up -d
  refresh.sh              run all adapters, write src/data/layers/*.geojson
  adapters/
    common.py             shared schema, helpers, polygon simplification
    outdoors_fi.py        National parks + wilderness areas (SYKE WFS)
    laavu_org.py          Laavus and kotas across Finland (laavu.org GPX)
    saunas_sheet.py       Saunas joined to parks (Google Sheet CSV)
  src/
    index.html
    static/
      css/style.css
      js/app.js           bootstrap, layer load, popups, polygon + point rendering
      js/filters.js       client-side filter logic
      js/favourites.js    localStorage CRUD
      js/sources.js       link-directory rendering + iframe panel
    data/
      sources.json        link directory (hand-curated)
      layers/             written by refresh.sh, gitignored except .gitkeep
```

## Local smoke test

```
cp .env.example .env
sed -i 's/^NATURE_DOMAIN=.*/NATURE_DOMAIN=localhost/' .env
cd src && python3 -m http.server 9888
# Open http://localhost:9888 in a browser. Layer data must already exist in
# src/data/layers/ for the map to show markers.
```

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
   single GPX with all ~4500 waypoints). Pikakartta, järviwiki, kyppi.fi
   often have similar buttons.
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
  `has-laavu`, `enclosed-fire`, `accessible`, `dogs-allowed`,
  `winter-route` so the frontend filter chips light up correctly.
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

### Sources currently outside the map

The site at https://www.tulikartta.fi/ (fire spots) moved to a paid
subscription model in 2026 and is no longer parseable for free. It remains
in `sources.json` as an outbound link.

Several other interesting datasets are link-only in
`src/data/sources.json` (waterfalls, järviwiki, kyppi.fi archaeology,
small breweries, winter routes, sacred sites). Promoting any of these to a
real mapped layer is exactly the workflow above.

## Out of scope

Accounts, server-side favourites, GPX import/export, offline / PWA,
reverse-engineering Google My Maps beyond iframe embedding.
