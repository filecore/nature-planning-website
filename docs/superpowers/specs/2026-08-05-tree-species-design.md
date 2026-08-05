# Tree species composition layer - design

Date: 2026-08-05

## Purpose

Add a new layer to nature.togneri.net showing which tree species dominate
each Finnish region and their approximate share of the growing stock, so
Jason can see at a glance what kind of forest to expect in an area he's
planning to hike in. Starting point: the Luke.fi "kotimaiset puulajit"
page, which lists Finland's native tree species and notes that pine,
spruce, silver birch and downy birch are the four dominant species
nationwide, with additional species (oak, maple, elm, alder) appearing
only in southern Finland.

## Data source

**Luke PxWeb statistics table 1.16** (`Puuston tilavuus metsä- ja
kitumaalla puulajeittain` / "Growing stock volume on forest land and
poorly productive forest land by tree species"), inventory NFI 13/14
(2020-2024), all 19 maakunta regions.

Endpoint (POST, JSON body, `json-stat2` response format):

```
https://statdb.luke.fi/PXWeb/api/v1/en/LUKE/met/zzz_lak/06%20Metsavarat/1.16_Puuston_tilavuus_metsa_ja_kitumaalla_pu.px
```

Query dimensions:
- `inventointi`: filter to `"14"` (NFI 13/14, 2020-2024 - the latest)
- `maakunta`: all 19 region codes (`1.1.1` through `1.1.21`, excluding the
  whole-country/Southern/Northern aggregate codes `1`, `1.1`, `1.2`)
- `puulaji`: `Mänty` (pine), `Kuusi` (spruce), `Koivu` (birch), `Muut
  lehtipuut` (other broadleaved) - the four species groups Luke publishes
  volume for; values are in million m³

### Why not the MVMI raster (rejected)

Luke's higher-resolution multi-source NFI (MVMI) publishes per-species
volume as 16m-grid GeoTIFFs, which would give a genuinely fine-grained
"density" layer like the bumblebees/butterflies grid-cell pattern. This
was tested and rejected: WMS `GetFeatureInfo` on the volume layers
(`manty_1923`, `kuusi_1923`, etc.) returns `queryable="0"` in
GetCapabilities and refuses the request; Luke only distributes this data
as downloadable GeoTIFFs. Parsing GeoTIFF requires a raster library
(rasterio/GDAL), which is not available under the project's stdlib-only
`refresh.sh` convention. PxWeb table 1.16 is the best available source
that stays inside that constraint.

### Region mapping

`maakunta` region codes/labels returned by table 1.16 map 1:1 onto
`common.py`'s existing 19-entry `REGIONS` list (English labels from the
API need mapping to the canonical Finnish names already used elsewhere,
e.g. "South Karelia" -> "Etelä-Karjala", "Central Finland" ->
"Keski-Suomi"). No changes to `common.py` are needed - `REGIONS` already
has centroids for all 19.

## Adapter: `adapters/tree_species.py`

Follows the `ticks.py` shape (one feature per region, at the region
centroid) rather than the `bumblebees.py`/`butterflies.py` grid-cell
shape, since the source data is regional, not point-occurrence.

1. POST the query above, parse the `json-stat2` response.
2. For each of the 19 regions, extract the four species volumes (million
   m³).
3. Compute:
   - `total_million_m3` = sum of the four
   - `pct` per species = `species / total * 100`, rounded to 1 decimal
   - `dominant_species` = species with the highest volume
4. Emit one feature per region via `make_feature(...)`:
   - `category`: `"tree-species"`
   - `region`: canonical maakunta name (matches existing region filter)
   - `tags`/`features`: `[f"dominant-{dominant_species_slug}"]` (slug:
     `pine`, `spruce`, `birch`, `other-broadleaved`)
   - `description`: e.g. `"Pine 45.2%, Spruce 32.8%, Birch 17.6%, Other
     4.4% of 78.3 million m³ growing stock (NFI 13/14, 2020-2024)"`
   - `properties.species` object with the four raw million-m³ values and
     their pct shares, plus `properties.total_million_m3`, so the
     frontend could later do custom rendering if desired (not required
     for v1 - popup text is enough)
5. `write_layer("tree-species", SOURCE, SITE_URL, features)`

Not time-aware: NFI data refreshes on a multi-year inventory cycle, not
something a time-window slider is useful for. No `timeAware` flag.

## Frontend: `src/static/js/app.js`

Add to `LAYERS`, in the `natural-sites` group (forest composition is a
property of the land, not wildlife or geology):

```js
{ id: 'tree-species', file: 'tree-species.geojson', label: 'Tree species composition', color: '#2d6a1f', icon: '\u{1F332}', group: 'natural-sites' }
```

Rendered as ordinary points with popups (existing code path - no new
`render_as` mode needed, since this is one point per region rather than
a grid).

## Testing

- Adapter: run `python3 adapters/tree_species.py` standalone, verify
  `src/data/layers/tree-species.geojson` has exactly 19 features, each
  with `region` set to one of the 19 canonical `REGIONS` names, species
  percentages summing to ~100%, and a plausible dominant species (pine or
  spruce almost everywhere, per the Luke.fi source page).
- Frontend: `bash refresh.sh` then open the site locally (or after
  deploy) and confirm the new "Tree species composition" toggle appears
  under "Natural sites", plot points show at each region centroid, and
  popups render the species breakdown text correctly.

## Out of scope (this iteration)

- Fine-grained (sub-region) resolution - would require the MVMI raster
  route and a rasterio/GDAL dependency; not pursued given the stdlib-only
  convention.
- The full ~30-species list from the Luke.fi source page - Luke's own
  statistics only break volume down into the four groups (pine, spruce,
  birch, other broadleaved); finer species detail is not available as
  structured data.
- Any change to `common.py`'s `REGIONS` or `region_for()` - not needed.
