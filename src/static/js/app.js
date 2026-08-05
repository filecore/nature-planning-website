(function () {
  // Layer registry. Each entry maps a GeoJSON file in data/layers/ to a
  // user-facing label and a marker color. Adding a new mapped source is a
  // one-liner here plus a new adapter that writes the matching file.
  // Every layer belongs to a group. Order of layers within a group, and of
  // groups themselves, follows the GROUP_ORDER list below.
  const LAYERS = [
    { id: 'national-parks',    file: 'national-parks.geojson',    label: 'National parks',                  color: '#1f7a3a', icon: '\u{1F332}', group: 'hiking' },
    { id: 'wilderness-areas',  file: 'wilderness-areas.geojson',  label: 'Wilderness areas',                color: '#5c7a3f', icon: '\u{1F97E}', group: 'hiking' },
    { id: 'nature-reserves',   file: 'nature-reserves.geojson',   label: 'Nature reserves',                 color: '#3a6b7a', icon: '\u{1F33F}', group: 'hiking' },
    { id: 'natura-2000',      file: 'natura-2000.geojson',      label: 'Natura 2000 areas',                color: '#6b8f3a', icon: '\u{1F310}', group: 'hiking' },
    { id: 'tree-species',     file: 'tree-species.geojson',     label: 'Tree species composition',         color: '#2d6a1f', icon: '\u{1F333}', group: 'hiking' },
    { id: 'lean-tos',          file: 'lean-tos.geojson',          label: 'Lean-to shelters',                color: '#7a4a1f', icon: '\u{1F3D5}', group: 'hiking' },
    { id: 'wilderness-huts',   file: 'wilderness-huts.geojson',   label: 'Wilderness huts',                 color: '#4a3520', icon: '\u{1F3E0}', group: 'hiking' },
    { id: 'saunas',           file: 'saunas.geojson',           label: 'Saunas in nature',                 color: '#8a4fcf', icon: '\u{1F9D6}', group: 'hiking' },
    { id: 'uusimaa-classics', file: 'uusimaa-classics.geojson', label: 'Uusimaa classics',                 color: '#facc15', icon: '⭐',    group: 'hiking', pane: 'uusimaaPane' },
    { id: 'bucket-list',      file: 'bucket-list.geojson',      label: 'Bucket list',                      color: '#ec4899', icon: '\u{1F3AF}', group: 'hiking', pane: 'uusimaaPane' },
    { id: 'archaeology',      file: 'archaeology.geojson',      label: 'Archaeological sites',             color: '#a0292e', icon: '\u{1F3DB}', group: 'natural-sites' },
    { id: 'open-air-heritage',file: 'open-air-heritage.geojson',label: 'Open-air museums and ruins',       color: '#6b4226', icon: '\u{1F3DB}', group: 'natural-sites' },
    { id: 'sacred-sites',     file: 'sacred-sites.geojson',     label: 'Sacred natural sites',             color: '#5b3a8a', icon: '✨',    group: 'natural-sites' },
    { id: 'caves',            file: 'caves.geojson',            label: 'Caves',                            color: '#5a4a36', icon: '\u{1F573}️', group: 'geological' },
    { id: 'crags',            file: 'crags.geojson',            label: 'Climbing crags',                   color: '#737373', icon: '\u{1F9D7}', group: 'geological' },
    { id: 'geo-bedrock',      file: 'geo-bedrock.geojson',      label: 'Bedrock and cliffs',               color: '#8b6f47', icon: '\u{26F0}', group: 'geological' },
    { id: 'geo-boulders',     file: 'geo-boulders.geojson',     label: 'Boulder fields',                   color: '#6b6b6b', icon: '\u{1FAA8}', group: 'geological' },
    { id: 'geo-moraines',     file: 'geo-moraines.geojson',     label: 'Moraine formations',               color: '#b78a4a', icon: '\u{1F30D}', group: 'geological' },
    { id: 'geo-eolian',       file: 'geo-eolian.geojson',       label: 'Wind and shore deposits',          color: '#d4a574', icon: '\u{1F3D6}', group: 'geological' },
    { id: 'bird-hotspots',    file: 'bird-hotspots.geojson',    label: 'Bird-watching towers',             color: '#0891b2', icon: '\u{1F426}', group: 'wildlife' },
    { id: 'bird-atlas',       file: 'bird-atlas.geojson',       label: 'Bird Atlas (species richness)',    color: '#1e40af', icon: '\u{1F985}', group: 'wildlife' },
    { id: 'butterflies',      file: 'butterflies.geojson',      label: 'Butterflies (NAFI)',               color: '#f97316', icon: '\u{1F98B}', group: 'wildlife', timeAware: true, timeMode: 'aggregate' },
    { id: 'bumblebees',       file: 'bumblebees.geojson',       label: 'Bumblebees',                       color: '#facc15', icon: '\u{1F41D}', group: 'wildlife', timeAware: true, timeMode: 'aggregate' },
    { id: 'wolves',           file: 'wolves.geojson',           label: 'Wolf sightings',                   color: '#64748b', icon: '\u{1F43A}', group: 'wildlife', timeAware: true, timeMode: 'heat' },
    { id: 'bears',            file: 'bears.geojson',            label: 'Bear sightings',                   color: '#7c2d12', icon: '\u{1F43B}', group: 'wildlife', timeAware: true, timeMode: 'heat' },
    { id: 'lynx',             file: 'lynx.geojson',             label: 'Lynx sightings',                   color: '#16a34a', icon: '\u{1F408}', group: 'wildlife', timeAware: true, timeMode: 'heat' },
    { id: 'beaches',          file: 'beaches.geojson',          label: 'Public swimming beaches',          color: '#4ec3e0', icon: '\u{1F3D6}', group: 'swimming-water' },
    { id: 'local-beaches',    file: 'local-beaches.geojson',    label: 'Local beaches (personal)',         color: '#06b6d4', icon: '\u{1F3CA}', group: 'swimming-water', pane: 'uusimaaPane' },
    { id: 'water-sensors',    file: 'water-sensors.geojson',    label: 'Live water temperature (Helsinki only)',color: '#14b8a6', icon: '\u{1F321}', group: 'quality' },
    { id: 'algae',            file: 'algae.geojson',            label: 'Recent algae observations (rolling 6m)', color: '#84cc16', icon: '\u{1F33F}', group: 'quality' },
    { id: 'air-quality',      file: 'air-quality.geojson',      label: 'Air quality stations',             color: '#3b82f6', icon: '\u{1F32B}', group: 'quality' },
    { id: 'water-levels',     file: 'water-levels.geojson',     label: 'River and lake water levels',      color: '#0ea5e9', icon: '\u{1F30A}', group: 'quality' },
    { id: 'weather-alerts',   file: 'weather-alerts.geojson',   label: 'Weather warnings',                 color: '#dc2626', icon: '\u{26A0}', group: 'quality' },
    { id: 'pollen',           file: 'pollen.geojson',           label: 'Pollen forecast (today)',          color: '#f59e0b', icon: '\u{1F33C}', group: 'quality' },
    { id: 'tick-density',     file: 'tick-density.geojson',     label: 'Tick observation density',         color: '#be185d', icon: '\u{1FAB2}', group: 'wildlife', timeAware: true, timeMode: 'aggregate' },
    { id: 'lakes',            file: 'lakes.geojson',            label: 'Lakes (≥ 0.5 km²)',            color: '#0b6fb2', icon: '\u{1F3DE}', group: 'swimming-water' },
    { id: 'rapids',           file: 'rapids.geojson',           label: 'Rapids and fast water',            color: '#1e3a8a', icon: '\u{1F30A}', group: 'swimming-water' },
    { id: 'waterfalls',       file: 'waterfalls.geojson',       label: 'Waterfalls',                       color: '#2e7bd6', icon: '\u{1F30A}', group: 'swimming-water' },
    { id: 'breweries',        file: 'breweries.geojson',        label: 'Breweries',                        color: '#d4a017', icon: '\u{1F37A}', group: 'alcohol' },
    { id: 'wineries',         file: 'wineries.geojson',         label: 'Wineries',                         color: '#8a1b3b', icon: '\u{1F377}', group: 'alcohol' },
    { id: 'distilleries',     file: 'distilleries.geojson',     label: 'Distilleries',                     color: '#c97a3d', icon: '\u{1F943}', group: 'alcohol' },
  ];

  const GROUPS = {
    'hiking':          { label: 'Outdoors recreation' },
    'natural-sites':   { label: 'Natural sites' },
    'geological':      { label: 'Geological features' },
    'wildlife':        { label: 'Wildlife' },
    'swimming-water':  { label: 'Swimming and water' },
    'quality':         { label: 'Environmental quality' },
    'alcohol':         { label: 'Alcohol' },
  };
  const GROUP_ORDER = ['hiking', 'natural-sites', 'geological', 'wildlife', 'swimming-water', 'quality', 'alcohol'];

  // Default ON layers on first visit so the user is not greeted by a
  // blank map. Anything not listed here starts unchecked.
  const DEFAULT_ON_LAYERS = new Set(['national-parks', 'uusimaa-classics']);

  /* ---------- Persistent filter state ---------- */
  // Single localStorage blob holding every checkbox + select state so the
  // sidebar restores exactly as the user left it on the next visit.
  const PREFS_KEY = 'nature.prefs.v1';

  function loadPrefs() {
    try {
      const raw = localStorage.getItem(PREFS_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  // Per-group accordion open/closed overrides set by the user.
  // Missing key = "auto" (open if any child is checked).
  const userGroupOverrides = {};

  function savePrefs() {
    const layers = {};
    for (const layer of LAYERS) {
      layers[layer.id] = Filters.state.layers.has(layer.id);
    }
    const prefs = {
      layers,
      regions: Array.from(Filters.state.regions).sort(),
      search: Filters.state.search,
      geoClasses: Array.from(Filters.state.geoClasses).sort(),
      groupOpen: { ...userGroupOverrides },
      timeWindow: Filters.state.timeWindow,
    };
    try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); } catch (e) {}
    syncUrl();
  }

  // Reflect current filter state in the URL bar so users can copy a
  // deep-link straight from the address bar. Multi-value params (one
  // ?key=value pair per layer / class) so the URL reads naturally
  // without %2C-encoded commas. Omits params that match the site's
  // default state to keep the URL clean.
  function syncUrl() {
    if (typeof window === 'undefined' || !window.history || !window.history.replaceState) return;
    const params = new URLSearchParams();

    const active = Array.from(Filters.state.layers).sort();
    const defaultActive = Array.from(DEFAULT_ON_LAYERS).sort();
    if (active.join(',') !== defaultActive.join(',')) {
      for (const id of active) params.append('layers', id);
    }
    for (const r of Array.from(Filters.state.regions).sort()) {
      params.append('region', r);
    }
    if (Filters.state.search) params.set('q', Filters.state.search);

    const geo = Array.from(Filters.state.geoClasses).sort((a,b) => a - b);
    if (geo.length !== 1 || geo[0] !== 1) {
      for (const n of geo) params.append('geo', String(n));
    }

    if (Filters.state.timeWindow) {
      params.set('window', Filters.state.timeWindow.start + '_' + Filters.state.timeWindow.end);
    }

    const qs = params.toString();
    const url = window.location.pathname + (qs ? '?' + qs : '') + window.location.hash;
    try { window.history.replaceState(null, '', url); } catch (e) {}
  }

  // URL-param overrides applied at boot. Cached once so every consumer
  // sees the same parse. Supported keys (use multi-value form so the
  // URL bar reads ?layers=a&layers=b not ?layers=a%2Cb):
  //   ?layers=a&layers=b   -> exactly these layer ids on (everything else off)
  //   ?region=Lappi                       -> single region filter preset
  //   ?region=Uusimaa&region=Kanta-Häme   -> multi-region (stack for border targeting)
  //   ?q=koski             -> name-search preset
  //   ?geo=1&geo=2         -> SYKE value-class chip preset
  // Legacy comma-separated values are still parsed for backwards compat
  // with already-shared links.
  let _urlOverridesCache = undefined;
  function urlOverrides() {
    if (_urlOverridesCache !== undefined) return _urlOverridesCache;
    let params;
    try { params = new URLSearchParams(window.location.search); }
    catch (e) { params = new URLSearchParams(); }
    const multi = (k) => {
      const all = params.getAll(k);
      if (!all.length) return null;
      const items = [];
      for (const v of all) {
        for (const part of String(v).split(',')) {
          const t = part.trim();
          if (t) items.push(t);
        }
      }
      return items;
    };
    const layers = multi('layers');
    const geo = multi('geo');
    const regions = multi('region');
    let timeWindow = null;
    const win = params.get('window');
    if (win) {
      const parts = win.split('_');
      if (parts.length === 2 && /^\d{4}-\d{2}$/.test(parts[0]) && /^\d{4}-\d{2}$/.test(parts[1])) {
        timeWindow = { start: parts[0], end: parts[1] };
      }
    }
    _urlOverridesCache = {
      layers: layers === null ? null : new Set(layers),
      regions: regions === null ? null : new Set(regions),
      search: params.get('q'),
      geoClasses: geo === null ? null : new Set(geo.map(s => parseInt(s, 10)).filter(n => n >= 1 && n <= 4)),
      timeWindow,
    };
    return _urlOverridesCache;
  }

  function initialLayerChecked(layerId) {
    const ov = urlOverrides();
    if (ov.layers) return ov.layers.has(layerId);
    const prefs = loadPrefs();
    if (prefs && prefs.layers && Object.prototype.hasOwnProperty.call(prefs.layers, layerId)) {
      return Boolean(prefs.layers[layerId]);
    }
    return DEFAULT_ON_LAYERS.has(layerId);
  }

  const FINLAND_CENTER = [64.5, 26.0];
  const FINLAND_ZOOM = 6;

  let map;
  // layerId -> { cluster: L.MarkerClusterGroup | null,
  //              polygons: L.LayerGroup | null,
  //              pointMarkers: array of L.CircleMarker,
  //              polygonLayers: array of L.geoJSON wrappers }
  // Point markers go through the cluster group; polygons go through the
  // separate plain layerGroup so they stay rendered as outlines.
  let leafletLayers = new Map();
  let featureLookup = new Map();  // 'layerId:featureId' -> Leaflet marker
  let lastFreshness = null;

  /* ---------- Map bootstrap ---------- */

  function initMap() {
    map = L.map('map', {
      center: FINLAND_CENTER,
      zoom: FINLAND_ZOOM,
      // Suppress the default top-left zoom control; we add it back in the
      // top-right so the collapsed-sidebar "Menu" floating button has the
      // top-left corner to itself.
      zoomControl: false,
    });
    L.control.zoom({ position: 'topright' }).addTo(map);

    // Custom pane for layers we want to float above the default marker stack.
    // Default markerPane is z-index 600; popupPane is 700. 650 keeps our
    // curated overlay above other markers but below open popups.
    map.createPane('uusimaaPane');
    map.getPane('uusimaaPane').style.zIndex = 650;

    const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    const opentopo = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
      maxZoom: 17,
      attribution: 'Map data: &copy; OpenStreetMap, SRTM | &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)',
    });

    L.control.layers(
      { 'OpenStreetMap': osm, 'OpenTopoMap': opentopo },
      null,
      { position: 'bottomleft', collapsed: false }
    ).addTo(map);

    L.control.scale({ imperial: false, position: 'bottomright' }).addTo(map);
  }

  /* ---------- Layer loading ---------- */

  async function loadLayer(layer) {
    try {
      const res = await fetch('data/layers/' + layer.file, { cache: 'no-cache' });
      if (!res.ok) return null;
      const geo = await res.json();
      return geo;
    } catch (e) {
      console.warn('Layer not available yet:', layer.id, e.message);
      return null;
    }
  }

  function featureCentroid(feature) {
    const g = feature.geometry || {};
    if (g.type === 'Point') {
      return [g.coordinates[1], g.coordinates[0]];
    }
    const cached = (feature.properties || {}).centroid;
    if (Array.isArray(cached) && cached.length >= 2) {
      return [Number(cached[1]), Number(cached[0])];
    }
    // Fallback: walk Polygon/MultiPolygon coordinates and use bbox centre.
    let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
    const walk = (seq) => {
      if (!seq) return;
      if (typeof seq[0] === 'number') {
        const lon = seq[0], lat = seq[1];
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
        if (lon < minLon) minLon = lon;
        if (lon > maxLon) maxLon = lon;
        return;
      }
      for (const s of seq) walk(s);
    };
    walk(g.coordinates);
    if (!isFinite(minLat)) return [64.5, 26.0];
    return [(minLat + maxLat) / 2, (minLon + maxLon) / 2];
  }

  // Map a coordinate-uncertainty value (metres) to a marker style.
  // Higher confidence = larger and more opaque; lower confidence =
  // smaller and more faded. No border / dash distinction, only size
  // and opacity, since the dashes turned out to be visually noisy.
  function styleForUncertainty(uncertaintyM) {
    // No data: treat as precise.
    if (uncertaintyM == null) {
      return { radius: 9, fillOpacity: 0.9,  tier: 'unknown' };
    }
    const km = Number(uncertaintyM) / 1000;
    if (km < 10)  return { radius: 9, fillOpacity: 0.9,  tier: 'short' };
    if (km < 30)  return { radius: 8, fillOpacity: 0.7,  tier: 'mid' };
    if (km < 50)  return { radius: 7, fillOpacity: 0.4,  tier: 'long-mid' };
    return        { radius: 6, fillOpacity: 0.2,  tier: 'long' };
  }

  // Pick a fill opacity for a grid-cell layer (bird-atlas, butterflies,
  // bumblebees) from the adapter-emitted "richness-{low|mid|high}" tag.
  // The per-layer threshold lives in the adapter so each taxon's idea
  // of "rich" is honoured (8 species for bumblebees ~ 60 for birds).
  // Adjacent cells overlap visually into a contiguous choropleth at
  // these opacities, which is the whole point of the rectangle render.
  function richnessOpacity(featureTags) {
    if (Array.isArray(featureTags)) {
      if (featureTags.includes('richness-high')) return 0.55;
      if (featureTags.includes('richness-mid'))  return 0.32;
      if (featureTags.includes('richness-low'))  return 0.16;
    }
    return 0.32;
  }

  function buildLeafletLayer(feature, layer) {
    const props = feature.properties || {};
    const name = props.name || '(unnamed)';
    let lyr;

    const isCell = (
      feature.geometry
      && feature.geometry.type === 'Point'
      && props.render_as === 'cell'
      && props.bin_lat_deg != null
      && props.bin_lon_deg != null
    );

    if (isCell) {
      const [lat, lon] = featureCentroid(feature);
      const dLat = Number(props.bin_lat_deg) / 2;
      const dLon = Number(props.bin_lon_deg) / 2;
      const bounds = [[lat - dLat, lon - dLon], [lat + dLat, lon + dLon]];
      const fillOpacity = richnessOpacity(props.features);
      const opts = {
        color: layer.color,
        weight: 0,
        fillColor: layer.color,
        fillOpacity,
      };
      if (layer.pane) opts.pane = layer.pane;
      lyr = L.rectangle(bounds, opts);
      lyr._kind = 'cell';
      // Cache the richness-based fill opacity so applyFilters can
      // restore it on filter re-show without clobbering it with the
      // generic polygon default (0.18).
      lyr._origFillOpacity = fillOpacity;
    } else if (feature.geometry && feature.geometry.type === 'Point') {
      const [lat, lon] = featureCentroid(feature);
      const uncStyle = styleForUncertainty(props.coordinate_uncertainty_m);
      const opts = {
        radius: uncStyle.radius,
        color: '#fff',
        weight: 1.5,
        fillColor: layer.color,
        fillOpacity: uncStyle.fillOpacity,
      };
      if (layer.pane) opts.pane = layer.pane;
      lyr = L.circleMarker([lat, lon], opts);
      lyr._kind = 'point';
      lyr._uncertaintyStyle = uncStyle;
    } else {
      const geoJSONOpts = {
        style: {
          color: layer.color,
          weight: 1.5,
          fillColor: layer.color,
          fillOpacity: 0.18,
        },
      };
      if (layer.pane) geoJSONOpts.pane = layer.pane;
      lyr = L.geoJSON(feature, geoJSONOpts);
      lyr._kind = 'polygon';
    }

    lyr.bindTooltip(name, { sticky: true, direction: 'top', offset: [0, -6] });
    lyr.bindPopup(() => buildPopup(feature, layer), { maxWidth: 320 });
    return lyr;
  }

  // Map a leading keyword in a description segment to a single emoji icon.
  // The adapter still produces plain "key: value · key: value" text; the
  // popup splits and inserts an icon per row. Falls back to a generic dot
  // when nothing matches.
  const POPUP_ROW_ICONS = [
    [/^area\b|^pinta-ala\b/i,                      '\u{1F4CF}'],  // 📏
    [/^elevation\b|^korkeustaso\b/i,               '\u{1F4D0}'],  // 📐
    [/^watercourse\b|^p[äa]{1,2}vesist[öo]\b/i,    '\u{1F30A}'],  // 🌊
    [/^ecological status\b|^water type\b|^freshwater\b|^coastal\b/i, '\u{1F33F}'],  // 🌿
    [/^water temperature\b|^water[: ]\b/i,         '\u{1F321}'],  // 🌡
    [/^read\b|^observed\b|^updated\b/i,            '\u{1F552}'],  // 🕒
    [/^algae level\b/i,                            '\u{1F33F}'],  // 🌿
    [/^iucn\b/i,                                   '\u{1F4DC}'],  // 📜
    [/^established\b/i,                            '\u{1F4C5}'],  // 📅
    [/^address\b|^osoite\b/i,                      '\u{1F4CD}'],  // 📍
    [/^coords printed\b|^pin at\b/i,               '\u{1F4CD}'],  // 📍
    [/^sauna in\b/i,                               '\u{1F9D6}'],  // 🧖
    [/^near\b|^l[äa]hell[äa]\b/i,                  '\u{1F4CD}'],  // 📍
    [/^eu-regulated\b|^small bathing\b/i,          '\u{2705}'],   // ✅
  ];

  function pickRowIcon(text) {
    for (const [re, icon] of POPUP_ROW_ICONS) {
      if (re.test(text)) return icon;
    }
    return '\u{1F539}';  // small blue diamond as neutral bullet
  }

  function splitDescription(raw) {
    if (!raw) return { rows: [], prose: '' };
    const sepRe = /\s+·\s+/;
    const lines = raw.split(/\n+/);
    // If a description has multiple lines, the last block becomes the
    // free-text "prose" excerpt (this is how the lakes adapter emits its
    // Excerpt_fi). Earlier blocks split on " · " into individual rows.
    let prose = '';
    const rowSource = [];
    for (let i = 0; i < lines.length; i++) {
      const ln = lines[i].trim();
      if (!ln) continue;
      if (i === lines.length - 1 && !sepRe.test(ln) && lines.length > 1) {
        prose = ln;
      } else {
        rowSource.push(ln);
      }
    }
    const rows = [];
    for (const block of rowSource) {
      if (sepRe.test(block)) {
        for (const part of block.split(sepRe)) {
          if (part.trim()) rows.push(part.trim());
        }
      } else {
        rows.push(block);
      }
    }
    return { rows, prose };
  }

  // Open-Meteo lookup. Free, no API key, ~10k requests per IP per day,
  // which is plenty for popup-on-demand use. Cache by 3-decimal-rounded
  // coordinate (~100 m) so the same area never re-fetches in one session,
  // and de-dupe in-flight promises so two popups opened on neighbouring
  // markers only fire one network call.
  const WEATHER_CACHE = new Map();
  const WEATHER_INFLIGHT = new Map();
  const WMO = {
    0:  ['☀️',   'Clear'],
    1:  ['\u{1F324}️','Mainly clear'],
    2:  ['⛅',          'Partly cloudy'],
    3:  ['☁️',   'Overcast'],
    45: ['\u{1F32B}️','Fog'],
    48: ['\u{1F32B}️','Freezing fog'],
    51: ['\u{1F326}️','Light drizzle'],
    53: ['\u{1F326}️','Drizzle'],
    55: ['\u{1F326}️','Heavy drizzle'],
    56: ['\u{1F326}️','Freezing drizzle'],
    57: ['\u{1F326}️','Freezing drizzle'],
    61: ['\u{1F327}️','Light rain'],
    63: ['\u{1F327}️','Rain'],
    65: ['\u{1F327}️','Heavy rain'],
    66: ['\u{1F327}️','Freezing rain'],
    67: ['\u{1F327}️','Freezing rain'],
    71: ['❄️',    'Light snow'],
    73: ['❄️',    'Snow'],
    75: ['❄️',    'Heavy snow'],
    77: ['❄️',    'Snow grains'],
    80: ['\u{1F326}️','Rain showers'],
    81: ['\u{1F327}️','Rain showers'],
    82: ['\u{1F327}️','Heavy rain showers'],
    85: ['❄️',    'Snow showers'],
    86: ['❄️',    'Heavy snow showers'],
    95: ['⛈️',   'Thunderstorm'],
    96: ['⛈️',   'Thunderstorm with hail'],
    99: ['⛈️',   'Thunderstorm with heavy hail'],
  };

  function weatherKey(lat, lon) {
    return lat.toFixed(3) + ',' + lon.toFixed(3);
  }

  function fetchWeather(lat, lon) {
    const key = weatherKey(lat, lon);
    if (WEATHER_CACHE.has(key)) return Promise.resolve(WEATHER_CACHE.get(key));
    if (WEATHER_INFLIGHT.has(key)) return WEATHER_INFLIGHT.get(key);

    const url = 'https://api.open-meteo.com/v1/forecast?' +
      'latitude=' + lat.toFixed(4) +
      '&longitude=' + lon.toFixed(4) +
      '&current=temperature_2m,weather_code,wind_speed_10m' +
      '&timezone=auto';
    const p = fetch(url)
      .then(r => r.ok ? r.json() : null)
      .then(j => {
        if (!j || !j.current) return null;
        const c = j.current;
        const out = {
          temp: c.temperature_2m,
          code: c.weather_code,
          wind: c.wind_speed_10m,
          unit: (j.current_units && j.current_units.temperature_2m) || '°C',
        };
        WEATHER_CACHE.set(key, out);
        return out;
      })
      .catch(() => null)
      .finally(() => WEATHER_INFLIGHT.delete(key));
    WEATHER_INFLIGHT.set(key, p);
    return p;
  }

  function renderWeatherInto(row, weather) {
    if (!weather) {
      row.remove();
      return;
    }
    const [emoji, label] = WMO[weather.code] || ['\u{1F321}️', 'Weather'];
    const ico = document.createElement('span');
    ico.className = 'popup-icon';
    ico.textContent = emoji;
    const txt = document.createElement('span');
    const t = typeof weather.temp === 'number' ? Math.round(weather.temp) + weather.unit : '';
    txt.textContent = [t, label].filter(Boolean).join(', ');
    row.innerHTML = '';
    row.appendChild(ico);
    row.appendChild(txt);
  }

  function mapsLink(lat, lon /*, name */) {
    // Universal Google Maps deeplink. Coordinates-only - appending a
    // `(name)` label makes Google Maps run a *named-place* search at the
    // coordinates, which often returns "no results" for natural / unnamed
    // sites. Plain coords just drop a pin where we want it.
    const q = encodeURIComponent(`${lat},${lon}`);
    return `https://www.google.com/maps/search/?api=1&query=${q}`;
  }

  function buildPopup(feature, layer) {
    const props = feature.properties || {};
    const featureId = props.id || (props.name + ':' + feature.geometry.coordinates.join(','));
    const favEntryId = Favourites.makeId(layer.id, featureId);
    const isFav = Favourites.has(layer.id, featureId);
    const [centroidLat, centroidLon] = featureCentroid(feature);

    const container = document.createElement('div');
    container.className = 'popup';

    const title = document.createElement('h3');
    title.textContent = (layer.icon ? layer.icon + ' ' : '') + (props.name || '(unnamed)');
    container.appendChild(title);

    const subtitle = props.region || layer.label;
    if (subtitle) {
      const meta = document.createElement('p');
      meta.className = 'popup-meta';
      meta.textContent = subtitle;
      container.appendChild(meta);
    }

    const { rows, prose } = splitDescription(props.description);
    const rowsBox = document.createElement('div');
    rowsBox.className = 'popup-rows';

    // Weather row goes first (after region subtitle) so the
    // most-time-sensitive information is at eye-level. Starts as a
    // placeholder "..." while the fetch completes.
    if (isFinite(centroidLat) && isFinite(centroidLon)) {
      const weatherRow = document.createElement('div');
      weatherRow.className = 'popup-row popup-weather';
      const wIco = document.createElement('span');
      wIco.className = 'popup-icon';
      wIco.textContent = '\u{1F321}️';
      const wTxt = document.createElement('span');
      wTxt.className = 'popup-weather-loading';
      wTxt.textContent = '…';
      weatherRow.appendChild(wIco);
      weatherRow.appendChild(wTxt);
      rowsBox.appendChild(weatherRow);
      fetchWeather(centroidLat, centroidLon)
        .then(w => renderWeatherInto(weatherRow, w))
        .catch(() => weatherRow.remove());
    }

    for (const text of rows) {
      const row = document.createElement('div');
      row.className = 'popup-row';
      const ico = document.createElement('span');
      ico.className = 'popup-icon';
      ico.textContent = pickRowIcon(text);
      const txt = document.createElement('span');
      txt.textContent = text;
      row.appendChild(ico);
      row.appendChild(txt);
      rowsBox.appendChild(row);
    }
    if (rowsBox.children.length) container.appendChild(rowsBox);
    if (prose) {
      const p = document.createElement('p');
      p.className = 'popup-prose';
      p.textContent = prose;
      container.appendChild(p);
    }

    if (Array.isArray(props.features) && props.features.length > 0) {
      const featBox = document.createElement('div');
      featBox.className = 'popup-features';
      for (const f of props.features) {
        const span = document.createElement('span');
        span.textContent = humaniseFeature(f);
        featBox.appendChild(span);
      }
      container.appendChild(featBox);
    }

    const actions = document.createElement('div');
    actions.className = 'popup-actions';

    if (isFinite(centroidLat) && isFinite(centroidLon)) {
      const mapBtn = document.createElement('a');
      mapBtn.href = mapsLink(centroidLat, centroidLon, props.name);
      mapBtn.target = '_blank';
      mapBtn.rel = 'noopener';
      mapBtn.className = 'popup-btn popup-btn-primary';
      mapBtn.textContent = 'Open in maps ↗';
      actions.appendChild(mapBtn);
    }

    if (props.source_url) {
      const link = document.createElement('a');
      link.href = props.source_url;
      link.target = '_blank';
      link.rel = 'noopener';
      link.className = 'popup-btn popup-btn-secondary';
      link.textContent = 'View source ↗';
      actions.appendChild(link);
    }

    const star = document.createElement('button');
    star.type = 'button';
    star.className = 'popup-btn popup-btn-star' + (isFav ? ' active' : '');
    star.textContent = isFav ? '★ Saved' : '☆ Save to favourites';
    star.addEventListener('click', () => {
      const [favLat, favLon] = featureCentroid(feature);
      Favourites.toggle({
        id: favEntryId,
        layerId: layer.id,
        featureId,
        name: props.name || '(unnamed)',
        lat: favLat,
        lon: favLon,
      });
      const nowFav = Favourites.has(layer.id, featureId);
      star.classList.toggle('active', nowFav);
      star.textContent = nowFav ? '★ Saved' : '☆ Save to favourites';
      renderFavourites();
    });
    actions.appendChild(star);

    container.appendChild(actions);
    return container;
  }

  function humaniseFeature(tag) {
    return tag.replace(/^has-/, '').replace(/-/g, ' ');
  }

  function makeClusterIconFactory(color) {
    return function (cluster) {
      const n = cluster.getChildCount();
      // Three size tiers, mirroring marker-cluster's default but with
      // per-layer colour and a single ring style.
      const size = n < 10 ? 32 : n < 100 ? 38 : 46;
      const html = (
        '<div class="nature-cluster-inner" style="background:' + color + ';' +
        'width:' + size + 'px;height:' + size + 'px;line-height:' + size + 'px;">' +
        '<span>' + n + '</span></div>'
      );
      return L.divIcon({
        html: html,
        className: 'nature-cluster',
        iconSize: L.point(size, size),
      });
    };
  }

  function makeClusterGroup(layer) {
    return L.markerClusterGroup({
      chunkedLoading: true,
      maxClusterRadius: 50,
      // Intentionally no `disableClusteringAtZoom`: markers at the same
      // (or very close) coordinates would otherwise render on top of
      // each other at high zoom and one would be unclickable. Keeping
      // clustering enabled at all zoom levels lets `spiderfyOnMaxZoom`
      // fan co-located markers out when the cluster is clicked at max
      // zoom. Spread-out markers still break apart naturally via
      // `maxClusterRadius` as the user zooms in.
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      iconCreateFunction: makeClusterIconFactory(layer.color),
      ...(layer.pane ? { clusterPane: layer.pane } : {}),
    });
  }

  async function loadAllLayers() {
    const allRegions = new Set();
    for (const layer of LAYERS) {
      const geo = await loadLayer(layer);
      if (!geo || !Array.isArray(geo.features)) continue;

      // Heat-mode time-aware layers (carnivores) render through a single
      // L.heatLayer rebuilt per time-window change. We skip the per-feature
      // marker / cluster pipeline entirely and just stash the raw features
      // with their observed_on dates for the filter step.
      if (layer.timeAware && layer.timeMode === 'heat') {
        const heatFeatures = [];
        for (const feature of geo.features) {
          feature.properties = feature.properties || {};
          feature.properties.layer = layer.id;
          if (!feature.geometry || feature.geometry.type !== 'Point') continue;
          const lat = feature.geometry.coordinates[1];
          const lon = feature.geometry.coordinates[0];
          if (lat == null || lon == null) continue;
          heatFeatures.push({ feature, lat, lon, observed_on: feature.properties.observed_on || '' });
          if (feature.properties.region) allRegions.add(feature.properties.region);
        }
        leafletLayers.set(layer.id, {
          cluster: null,
          polygons: null,
          pointMarkers: [],
          polygonLayers: [],
          heatFeatures,
          heatLayer: null,
          // Carnivore data is coarsened to ~25 km grid then triangle-offset
          // per species. radius 28 / blur 22 gives circles slightly larger
          // than that grid so they read as zones rather than pinpoints.
          heatOptions: { radius: 28, blur: 22, minOpacity: 0.35, maxZoom: 12 },
        });
        if (geo.generated_at && (!lastFreshness || geo.generated_at > lastFreshness)) {
          lastFreshness = geo.generated_at;
        }
        await new Promise(resolve => setTimeout(resolve, 0));
        continue;
      }

      // Sort features by geometry kind. Points cluster; polygons render
      // as outlines in a parallel plain layerGroup so they stay visible
      // at all zooms.
      const pointMarkers = [];
      const polygonLayers = [];

      for (const feature of geo.features) {
        feature.properties = feature.properties || {};
        feature.properties.layer = layer.id;
        const featureId = feature.properties.id || (feature.properties.name + ':' + JSON.stringify(featureCentroid(feature)));
        const lyr = buildLeafletLayer(feature, layer);
        lyr._feature = feature;
        // Time-aware aggregate layers (butterflies, bumblebees, ticks)
        // carry a by_year breakdown. Cache the full-window richness tier
        // as the baseline so applyTimeFilter can restore it when the
        // slider is widened back to "all time".
        if (layer.timeAware && layer.timeMode === 'aggregate') {
          lyr._byYear = feature.properties.by_year || null;
          lyr._baseFeatures = feature.properties.features || [];
        }
        if (lyr._kind === 'point') {
          pointMarkers.push(lyr);
        } else {
          polygonLayers.push(lyr);
        }
        featureLookup.set(Favourites.makeId(layer.id, featureId), lyr);
        if (feature.properties.region) allRegions.add(feature.properties.region);
      }

      // Build groups in memory; do NOT addTo(map) yet. addLayers on a
      // detached cluster group is synchronous (chunkedLoading is only
      // honoured once the group is on the map), so the internal cluster
      // tree finishes before we move on to the next layer.
      const cluster = pointMarkers.length ? makeClusterGroup(layer) : null;
      if (cluster) cluster.addLayers(pointMarkers);
      const polygons = polygonLayers.length ? L.layerGroup() : null;
      if (polygons) {
        for (const p of polygonLayers) p.addTo(polygons);
      }

      leafletLayers.set(layer.id, {
        cluster,
        polygons,
        pointMarkers,
        polygonLayers,
      });

      if (geo.generated_at && (!lastFreshness || geo.generated_at > lastFreshness)) {
        lastFreshness = geo.generated_at;
      }

      // Yield to the event loop so the spinner keeps animating between
      // layers (each layer's addLayers run can be tens of ms of work).
      await new Promise(resolve => setTimeout(resolve, 0));
    }
    populateRegionToggles(Array.from(allRegions).sort());
    updateFreshness();

    // Attach every group to the map in a single batch. This is the only
    // moment any markers / polygons become visible.
    for (const entry of leafletLayers.values()) {
      if (entry.cluster) entry.cluster.addTo(map);
      if (entry.polygons) entry.polygons.addTo(map);
    }
  }

  // Build a checkbox per region in the side panel. Mirrors the layer
  // toggles UI. Checking a box adds the region to Filters.state.regions;
  // an empty set means "all regions" (no filter).
  function populateRegionToggles(regions) {
    const wrap = document.getElementById('region-toggles');
    if (!wrap) return;
    wrap.textContent = '';
    for (const r of regions) {
      const label = document.createElement('label');
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.value = r;
      cb.checked = Filters.state.regions.has(r);
      cb.addEventListener('change', () => {
        Filters.setRegion(r, cb.checked);
        savePrefs();
        if (cb.checked) fitToRegions(Filters.state.regions);
      });
      label.appendChild(cb);
      label.appendChild(document.createTextNode(r));
      wrap.appendChild(label);
    }
  }

  function syncRegionCheckboxes() {
    const wrap = document.getElementById('region-toggles');
    if (!wrap) return;
    for (const cb of wrap.querySelectorAll('input[type="checkbox"]')) {
      cb.checked = Filters.state.regions.has(cb.value);
    }
  }

  function updateFreshness() {
    const el = document.getElementById('data-freshness');
    if (!el) return;
    el.textContent = lastFreshness ? new Date(lastFreshness).toLocaleString() : 'no data yet (run refresh.sh)';
  }

  /* ---------- Filter wiring ---------- */

  function buildLayerToggles() {
    const container = document.getElementById('layer-toggles');
    container.innerHTML = '';

    // Every layer is grouped. Render in GROUP_ORDER so the sidebar order
    // is deterministic regardless of LAYERS array order.
    const groupedByKey = new Map();
    for (const layer of LAYERS) {
      const g = layer.group || 'other';
      if (!groupedByKey.has(g)) groupedByKey.set(g, []);
      groupedByKey.get(g).push(layer);
    }
    const orderedGroups = GROUP_ORDER.filter(g => groupedByKey.has(g));
    for (const k of groupedByKey.keys()) {
      if (!orderedGroups.includes(k)) orderedGroups.push(k);
    }

    // Hydrate per-group open overrides from prefs before the first render
    // so accordion states match what the user last left them in.
    const bootPrefs = loadPrefs();
    if (bootPrefs && bootPrefs.groupOpen && typeof bootPrefs.groupOpen === 'object') {
      for (const k of Object.keys(bootPrefs.groupOpen)) {
        userGroupOverrides[k] = Boolean(bootPrefs.groupOpen[k]);
      }
    }

    for (const groupId of orderedGroups) {
      const layers = groupedByKey.get(groupId);
      const meta = GROUPS[groupId] || { label: groupId };
      const wrap = document.createElement('details');
      wrap.className = 'layer-group';
      // Initial open state: explicit user override wins; otherwise expand
      // when at least one layer in the group is checked (so a partial 1-of-N
      // selection is visible after page refresh).
      const anyChecked = layers.some(l => initialLayerChecked(l.id));
      wrap.open = Object.prototype.hasOwnProperty.call(userGroupOverrides, groupId)
        ? userGroupOverrides[groupId]
        : anyChecked;

      const summary = document.createElement('summary');
      const parentCb = document.createElement('input');
      parentCb.type = 'checkbox';
      parentCb.className = 'group-parent';
      parentCb.checked = false;
      summary.appendChild(parentCb);
      const summaryText = document.createElement('span');
      summaryText.className = 'group-label';
      summaryText.textContent = meta.label;
      summary.appendChild(summaryText);
      // Clicking the checkbox shouldn't also toggle the details open/close.
      parentCb.addEventListener('click', (e) => e.stopPropagation());
      wrap.appendChild(summary);

      const childWrap = document.createElement('div');
      childWrap.className = 'group-children';
      for (const layer of layers) {
        childWrap.appendChild(makeLayerLabel(layer));
      }
      wrap.appendChild(childWrap);
      container.appendChild(wrap);

      parentCb.addEventListener('change', () => {
        for (const layer of layers) {
          const childCb = childWrap.querySelector(`input[value="${layer.id}"]`);
          if (childCb) {
            childCb.checked = parentCb.checked;
            Filters.setLayer(layer.id, parentCb.checked);
          }
        }
        savePrefs();
      });

      // Reflect children -> parent: all/some/none indeterminate state.
      const syncParent = () => {
        const childCbs = Array.from(childWrap.querySelectorAll('input[type="checkbox"]'));
        const checkedCount = childCbs.filter(c => c.checked).length;
        parentCb.checked = checkedCount === childCbs.length;
        parentCb.indeterminate = checkedCount > 0 && checkedCount < childCbs.length;
      };
      childWrap.addEventListener('change', syncParent);
      // Initial sync so the parent reflects the restored child states.
      syncParent();

      // Record user-driven open/close so collapse persists across reloads
      // even when items inside the group are still checked. The collapse-all
      // button mutates ``wrap.open`` programmatically; that fires toggle too,
      // which is correct - it's a user action.
      wrap.addEventListener('toggle', () => {
        userGroupOverrides[groupId] = wrap.open;
        savePrefs();
      });
    }

    wireLayersCollapseToggle();
  }

  function wireLayersCollapseToggle() {
    const btn = document.getElementById('layers-collapse-toggle');
    if (!btn) return;
    const groups = () => document.querySelectorAll('#layer-toggles details.layer-group');
    const sync = () => {
      const list = groups();
      if (!list.length) return;
      const anyOpen = Array.from(list).some(d => d.open);
      btn.textContent = anyOpen ? 'Collapse all' : 'Expand all';
    };
    btn.addEventListener('click', () => {
      const list = groups();
      const anyOpen = Array.from(list).some(d => d.open);
      const target = !anyOpen;  // if all closed, expand; otherwise collapse
      for (const d of list) d.open = target;
      sync();
    });
    // Keep button label in sync if user toggles individual groups manually.
    for (const d of groups()) {
      d.addEventListener('toggle', sync);
    }
    sync();
  }

  function makeLayerLabel(layer) {
    const label = document.createElement('label');
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.value = layer.id;
    const initial = initialLayerChecked(layer.id);
    cb.checked = initial;
    Filters.setLayer(layer.id, initial);
    cb.addEventListener('change', () => {
      Filters.setLayer(layer.id, cb.checked);
      savePrefs();
    });
    const swatch = document.createElement('span');
    swatch.className = 'layer-swatch';
    swatch.style.background = layer.color;
    label.appendChild(cb);
    label.appendChild(swatch);
    label.appendChild(document.createTextNode(layer.label));
    return label;
  }

  function wireFilters() {
    const prefs = loadPrefs() || {};
    const ov = urlOverrides();
    const searchBox = document.getElementById('search-box');

    // Restore non-layer prefs (URL params win over saved prefs).
    const initialSearch = ov.search !== null ? ov.search : (typeof prefs.search === 'string' ? prefs.search : '');
    if (initialSearch) {
      searchBox.value = initialSearch;
      Filters.set({ search: initialSearch });
    }
    // Restore region(s) from URL (Set) -> prefs (array, new format) -> prefs (string, legacy)
    let initialRegions = null;
    if (ov.regions !== null) {
      initialRegions = ov.regions;
    } else if (Array.isArray(prefs.regions)) {
      initialRegions = new Set(prefs.regions.filter(s => typeof s === 'string' && s));
    } else if (typeof prefs.region === 'string' && prefs.region) {
      initialRegions = new Set([prefs.region]);
    }
    if (initialRegions && initialRegions.size) {
      // Checkboxes are built later from layer data; populateRegionToggles
      // reads Filters.state.regions to set initial checked state.
      Filters.setRegions(initialRegions);
    }

    searchBox.addEventListener('input', (e) => {
      Filters.set({ search: e.target.value });
      savePrefs();
    });

    // Geological value-class chips: restore from prefs, then wire toggles.
    // Help-panel toggle for SYKE value categories.
    const helpBtn = document.getElementById('geo-class-help');
    const helpPanel = document.getElementById('geo-class-help-panel');
    if (helpBtn && helpPanel) {
      helpBtn.addEventListener('click', () => {
        helpPanel.hidden = !helpPanel.hidden;
      });
    }

    const chipEls = Array.from(document.querySelectorAll('#geo-class-chips .chip'));
    let restored = null;
    if (ov.geoClasses && ov.geoClasses.size) {
      restored = ov.geoClasses;
      Filters.set({ geoClasses: restored });
    } else if (Array.isArray(prefs.geoClasses)) {
      restored = new Set(prefs.geoClasses.map(Number).filter(n => n >= 1 && n <= 4));
      if (restored.size) Filters.set({ geoClasses: restored });
    }
    for (const chip of chipEls) {
      const cls = parseInt(chip.dataset.class, 10);
      // No restore source -> mirror Filters.state default (Level 1 only).
      // URL or prefs -> trust the restored Set.
      const on = restored ? restored.has(cls) : (cls === 1);
      chip.classList.toggle('chip-on', on);
      chip.setAttribute('aria-pressed', on ? 'true' : 'false');
      chip.addEventListener('click', () => {
        const enabled = !chip.classList.contains('chip-on');
        chip.classList.toggle('chip-on', enabled);
        chip.setAttribute('aria-pressed', enabled ? 'true' : 'false');
        Filters.setGeoClass(cls, enabled);
        savePrefs();
      });
    }

    document.getElementById('region-clear').addEventListener('click', () => {
      Filters.setRegions([]);
      syncRegionCheckboxes();
      savePrefs();
    });

    document.getElementById('clear-filters').addEventListener('click', () => {
      searchBox.value = '';
      Filters.clear();
      syncRegionCheckboxes();
      // Reflect cleared geo-class state in the chip UI (class 1 only).
      for (const chip of document.querySelectorAll('#geo-class-chips .chip')) {
        const isOne = chip.dataset.class === '1';
        chip.classList.toggle('chip-on', isOne);
        chip.setAttribute('aria-pressed', isOne ? 'true' : 'false');
      }
      savePrefs();
    });

    Filters.onChange(applyFilters);
  }

  // Zoom the map to the union bounding box of every feature whose region
  // is in ``regions`` (a Set). Used on initial load (URL / prefs preset)
  // and when a region checkbox is ticked. Skips polygons-without-bounds
  // and never operates without a valid bounds object.
  function fitToRegions(regions) {
    if (!regions || !regions.size || !map) return;
    const bounds = L.latLngBounds([]);
    for (const entry of leafletLayers.values()) {
      if (entry.pointMarkers) {
        for (const m of entry.pointMarkers) {
          const f = m._feature;
          if (f && f.properties && regions.has(f.properties.region)) {
            try { bounds.extend(m.getLatLng()); } catch (e) {}
          }
        }
      }
      if (entry.polygonLayers) {
        for (const lyr of entry.polygonLayers) {
          const f = lyr._feature;
          if (f && f.properties && regions.has(f.properties.region) && typeof lyr.getBounds === 'function') {
            try { bounds.extend(lyr.getBounds()); } catch (e) {}
          }
        }
      }
    }
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 10 });
    }
  }

  /* ---------- Time-window helpers ---------- */

  // 'YYYY-MM' -> [year, month] integers, or null if unparseable.
  function parseYearMonth(s) {
    if (!s) return null;
    const m = String(s).match(/^(\d{4})-(\d{1,2})/);
    if (!m) return null;
    return [parseInt(m[1], 10), parseInt(m[2], 10)];
  }

  // True if the observed_on date string falls within the (inclusive) window.
  // Missing/unparseable dates are kept visible - we'd rather show a record
  // with no date than silently drop it.
  function inTimeWindow(observedOn, tw) {
    if (!tw) return true;
    const ym = parseYearMonth(observedOn);
    if (!ym) return true;
    const start = parseYearMonth(tw.start);
    const end = parseYearMonth(tw.end);
    if (!start || !end) return true;
    const k = ym[0] * 100 + ym[1];
    return k >= start[0] * 100 + start[1] && k <= end[0] * 100 + end[1];
  }

  // Years the window touches (inclusive). null if the window itself is null
  // (= "all time").
  function yearsTouchedByWindow(tw) {
    if (!tw) return null;
    const start = parseYearMonth(tw.start);
    const end = parseYearMonth(tw.end);
    if (!start || !end) return null;
    const out = [];
    for (let y = start[0]; y <= end[0]; y++) out.push(y);
    return out;
  }

  // Sum the per-year counts in `byYear` that fall inside the window. by_year
  // values can be either integers (ticks) or objects with a `count` field
  // (butterflies, bumblebees).
  function windowedByYearSum(byYear, tw) {
    if (!byYear || typeof byYear !== 'object') return 0;
    const yearKey = (v) => (typeof v === 'number') ? v : (v && typeof v.count === 'number' ? v.count : 0);
    const years = yearsTouchedByWindow(tw);
    if (!years) {
      let total = 0;
      for (const k of Object.keys(byYear)) total += yearKey(byYear[k]);
      return total;
    }
    let total = 0;
    for (const y of years) {
      const v = byYear[String(y)];
      if (v != null) total += yearKey(v);
    }
    return total;
  }

  // Total counts (window-agnostic) so we can derive a max for per-layer
  // opacity scaling. Memoised per (layerId).
  const _layerMaxCache = new Map();
  function layerMaxByYear(entry, layerId) {
    if (_layerMaxCache.has(layerId)) return _layerMaxCache.get(layerId);
    let max = 0;
    const consider = (lyr) => {
      if (!lyr._byYear) return;
      const t = windowedByYearSum(lyr._byYear, null);
      if (t > max) max = t;
    };
    if (entry.polygonLayers) for (const lyr of entry.polygonLayers) consider(lyr);
    if (entry.pointMarkers) for (const lyr of entry.pointMarkers) consider(lyr);
    _layerMaxCache.set(layerId, max);
    return max;
  }

  function haversineKm(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) ** 2 +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  function applyFilters() {
    const tw = Filters.state.timeWindow;
    let visible = 0;
    for (const [layerId, entry] of leafletLayers) {
      const layerCfg = LAYERS.find(l => l.id === layerId);
      const layerOn = Filters.state.layers.has(layerId);

      // Heat-mode time-aware layers: tear down any existing L.heatLayer
      // and rebuild from filtered features. Cheap enough to do on every
      // change at the data volumes we have (~ 1300 carnivore points
      // total).
      if (entry.heatFeatures) {
        if (entry.heatLayer) { map.removeLayer(entry.heatLayer); entry.heatLayer = null; }
        if (layerOn) {
          const pts = [];
          const search = (Filters.state.search || '').toLowerCase();
          for (const h of entry.heatFeatures) {
            const props = h.feature.properties || {};
            if (Filters.state.regions.size && !Filters.state.regions.has(props.region)) continue;
            if (search) {
              const name = (props.name || '').toLowerCase();
              if (!name.includes(search)) continue;
            }
            if (tw && !inTimeWindow(h.observed_on, tw)) continue;
            pts.push([h.lat, h.lon, 1]);
          }
          if (pts.length) {
            entry.heatLayer = L.heatLayer(pts, entry.heatOptions).addTo(map);
            visible += pts.length;
          }
        }
        continue;
      }

      // Point markers: add/remove from the cluster group so cluster
      // counts reflect filters. Batch via addLayers / removeLayers.
      if (entry.cluster) {
        const isTimeAggregate = layerCfg && layerCfg.timeAware && layerCfg.timeMode === 'aggregate';
        const toAdd = [];
        const toRemove = [];
        for (const m of entry.pointMarkers) {
          let match = layerOn && Filters.matches(m._feature);
          if (match && isTimeAggregate && m._byYear) {
            if (windowedByYearSum(m._byYear, tw) === 0) match = false;
          }
          if (match) {
            toAdd.push(m);
            visible++;
          } else {
            toRemove.push(m);
          }
        }
        if (toRemove.length) entry.cluster.removeLayers(toRemove);
        if (toAdd.length) entry.cluster.addLayers(toAdd);
      }

      // Polygons: opacity-toggle as before (they don't cluster).
      // Grid-cell rectangles share this branch but restore their
      // richness-derived fill opacity instead of the polygon default,
      // and use weight 0 so the cell edges don't reappear on re-show.
      if (entry.polygons) {
        const isTimeAggregate = layerCfg && layerCfg.timeAware && layerCfg.timeMode === 'aggregate';
        const layerMax = isTimeAggregate ? layerMaxByYear(entry, layerId) : 0;
        for (const lyr of entry.polygonLayers) {
          let match = layerOn && Filters.matches(lyr._feature);
          const isCell = lyr._kind === 'cell';
          let cellFillOpacity = lyr._origFillOpacity != null ? lyr._origFillOpacity : 0.32;
          if (match && isTimeAggregate && lyr._byYear) {
            const wsum = windowedByYearSum(lyr._byYear, tw);
            if (wsum === 0) {
              match = false;
            } else if (layerMax > 0) {
              // Scale the cell's fillOpacity between 0.12 (rare) and 0.55
              // (the densest cell in this layer at full window), using a
              // square-root curve so a handful of very dense cells don't
              // wash out the rest of the country.
              const ratio = Math.min(1, Math.sqrt(wsum / layerMax));
              cellFillOpacity = 0.12 + 0.43 * ratio;
            }
          }
          if (match) visible++;
          const styleOn  = isCell
            ? { opacity: 0, weight: 0, fillOpacity: cellFillOpacity }
            : { opacity: 1, fillOpacity: 0.18 };
          const styleOff = { opacity: 0, fillOpacity: 0 };
          const apply = (sub) => {
            if (typeof sub.setStyle === 'function') sub.setStyle(match ? styleOn : styleOff);
            if (sub._path) sub._path.style.pointerEvents = match ? '' : 'none';
            if (!match) {
              if (typeof sub.closeTooltip === 'function') sub.closeTooltip();
              if (typeof sub.closePopup === 'function') sub.closePopup();
            }
          };
          if (typeof lyr.eachLayer === 'function') lyr.eachLayer(apply);
          else apply(lyr);
        }
      }
    }
    document.getElementById('result-count').textContent = visible + ' shown';
  }

  /* ---------- Tabs ---------- */

  function wireTabs() {
    document.querySelectorAll('.tab-button').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-button').forEach(b => {
          b.classList.toggle('active', b === btn);
          b.setAttribute('aria-selected', b === btn ? 'true' : 'false');
        });
        document.querySelectorAll('.tab-panel').forEach(p => {
          p.classList.toggle('active', p.id === 'tab-' + btn.dataset.tab);
        });
      });
    });
  }

  /* ---------- Mobile resizable divider ---------- */
  // Mirrors the summer.togneri.net pattern: on mobile the sidebar lives
  // above the map and a 14px row-resize bar lets the user choose how much
  // vertical space each gets. Position persists in localStorage.

  const MOBILE_BP = 768;
  const STORAGE_KEY_VH = 'nature.sidebar_vh';
  const STORAGE_KEY_PX = 'nature.sidebar_width_px';

  function isMobile() { return window.innerWidth <= MOBILE_BP; }

  function clampVh(v) { return Math.min(80, Math.max(15, v)); }
  function clampPx(v) {
    const maxPx = Math.max(300, window.innerWidth - 200);
    return Math.min(maxPx, Math.max(220, v));
  }

  function applySidebarSize() {
    const sidebar = document.getElementById('sidebar');
    if (isMobile()) {
      const vh = parseFloat(localStorage.getItem(STORAGE_KEY_VH) || '40');
      sidebar.style.height = clampVh(vh) + 'vh';
      sidebar.style.width = '';
      sidebar.style.flexBasis = '';
    } else {
      sidebar.style.height = '';
      // Default sidebar takes 25% of the viewport on first visit so the
      // map has more room; user-resized values persist in localStorage
      // and override the default.
      const stored = localStorage.getItem(STORAGE_KEY_PX);
      const px = stored !== null ? parseFloat(stored) : Math.round(window.innerWidth * 0.25);
      const w = clampPx(px) + 'px';
      sidebar.style.width = w;
      sidebar.style.flexBasis = w;
    }
  }

  function wireDivider() {
    const divider = document.getElementById('divider');
    const sidebar = document.getElementById('sidebar');
    if (!divider) return;

    let resizing = false;

    function endDrag() {
      if (!resizing) return;
      resizing = false;
      divider.classList.remove('active');
      if (isMobile()) {
        const vh = parseFloat(sidebar.style.height) || 40;
        localStorage.setItem(STORAGE_KEY_VH, clampVh(vh));
      } else {
        const px = parseFloat(sidebar.style.width) || 340;
        localStorage.setItem(STORAGE_KEY_PX, clampPx(px));
      }
      document.body.style.userSelect = '';
      if (typeof map !== 'undefined' && map) map.invalidateSize();
    }

    function moveToY(clientY) {
      const vh = (clientY / window.innerHeight) * 100;
      sidebar.style.height = clampVh(vh) + 'vh';
      if (typeof map !== 'undefined' && map) map.invalidateSize();
    }

    function moveToX(clientX) {
      const w = clampPx(clientX) + 'px';
      sidebar.style.width = w;
      sidebar.style.flexBasis = w;
      if (typeof map !== 'undefined' && map) map.invalidateSize();
    }

    // Touch - mobile only
    divider.addEventListener('touchstart', (e) => {
      if (!isMobile()) return;
      resizing = true;
      divider.classList.add('active');
      e.preventDefault();
    }, { passive: false });
    document.addEventListener('touchmove', (e) => {
      if (!resizing) return;
      moveToY(e.touches[0].clientY);
      e.preventDefault();
    }, { passive: false });
    document.addEventListener('touchend', endDrag);
    document.addEventListener('touchcancel', endDrag);

    // Mouse - desktop + mobile
    divider.addEventListener('mousedown', (e) => {
      resizing = true;
      divider.classList.add('active');
      document.body.style.userSelect = 'none';
      e.preventDefault();
    });
    document.addEventListener('mousemove', (e) => {
      if (!resizing) return;
      if (e.buttons === 0) { endDrag(); return; }
      if (isMobile()) moveToY(e.clientY);
      else            moveToX(e.clientX);
    }, true);
    document.addEventListener('mouseup', () => {
      if (!resizing) return;
      endDrag();
    }, true);

    applySidebarSize();
    window.addEventListener('resize', applySidebarSize);
  }

  /* ---------- Sidebar toggle ---------- */

  function wireSidebar() {
    const sidebar = document.getElementById('sidebar');
    const btn = document.getElementById('sidebar-toggle');
    let floating = null;
    btn.addEventListener('click', () => {
      sidebar.classList.remove('open');
      // applySidebarSize() sets inline width / flexBasis, which beats
      // the .sidebar:not(.open) { width: 0 } rule on specificity. Clear
      // them when collapsing so the class-based hide actually takes
      // effect; applySidebarSize() will restore them on expand.
      sidebar.style.width = '';
      sidebar.style.flexBasis = '';
      sidebar.style.height = '';
      floating = document.createElement('button');
      floating.className = 'sidebar-toggle-floating';
      floating.setAttribute('aria-label', 'Open sidebar');
      // U+203A single right-pointing angle quotation: "open / expand"
      floating.innerHTML = '&#x203A; Menu';
      floating.addEventListener('click', () => {
        sidebar.classList.add('open');
        applySidebarSize();
        floating.remove();
        setTimeout(() => map.invalidateSize(), 200);
      });
      document.body.appendChild(floating);
      setTimeout(() => map.invalidateSize(), 200);
    });
  }

  /* ---------- Resources ---------- */

  async function wireResources() {
    await Sources.load();
    const list = document.getElementById('resources-list');
    Sources.renderList(list, openInline);
  }

  function openInline(src) {
    const panel = document.getElementById('inline-panel');
    const frame = document.getElementById('inline-panel-frame');
    const title = document.getElementById('inline-panel-title');
    title.textContent = src.title;
    frame.src = src.embedUrl || src.url;
    panel.classList.remove('hidden');
    document.getElementById('app').classList.add('inline-open');
    setTimeout(() => map.invalidateSize(), 200);
  }

  function wireInlinePanel() {
    document.getElementById('inline-panel-close').addEventListener('click', () => {
      const panel = document.getElementById('inline-panel');
      panel.classList.add('hidden');
      document.getElementById('inline-panel-frame').src = 'about:blank';
      document.getElementById('app').classList.remove('inline-open');
      setTimeout(() => map.invalidateSize(), 200);
    });
  }

  /* ---------- Favourites tab ---------- */

  function renderFavourites() {
    const list = document.getElementById('favourites-list');
    const favs = Favourites.load();
    list.innerHTML = '';
    if (favs.length === 0) {
      const p = document.createElement('p');
      p.className = 'muted small';
      p.textContent = 'No favourites yet. Click "Save" on any map popup to add one.';
      list.appendChild(p);
      return;
    }
    for (const f of favs) {
      const row = document.createElement('div');
      row.className = 'favourite-entry';

      const name = document.createElement('span');
      name.className = 'fav-name';
      name.textContent = f.name;
      row.appendChild(name);

      const actions = document.createElement('div');
      actions.className = 'fav-actions';

      const fly = document.createElement('button');
      fly.textContent = 'Center on map';
      fly.className = 'ghost';
      fly.addEventListener('click', () => {
        const lyr = featureLookup.get(f.id);
        if (lyr && typeof lyr.getBounds === 'function') {
          map.flyToBounds(lyr.getBounds(), { padding: [40, 40], maxZoom: 13 });
        } else {
          map.flyTo([f.lat, f.lon], 12);
        }
        if (lyr) setTimeout(() => lyr.openPopup(), 500);
      });
      actions.appendChild(fly);

      const del = document.createElement('button');
      del.textContent = 'Remove';
      del.className = 'ghost';
      del.addEventListener('click', () => {
        Favourites.remove(f.id);
        renderFavourites();
        const marker = featureLookup.get(f.id);
        if (marker && marker.isPopupOpen()) marker.closePopup();
      });
      actions.appendChild(del);

      row.appendChild(actions);
      list.appendChild(row);
    }
  }

  function xmlEscape(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function buildFavouritesKml(favs) {
    const placemarks = favs.map(f => (
      '  <Placemark>\n' +
      '    <name>' + xmlEscape(f.name) + '</name>\n' +
      (f.layer ? '    <description>' + xmlEscape(f.layer) + '</description>\n' : '') +
      '    <Point><coordinates>' + Number(f.lon).toFixed(6) + ',' + Number(f.lat).toFixed(6) + ',0</coordinates></Point>\n' +
      '  </Placemark>'
    )).join('\n');
    return (
      '<?xml version="1.0" encoding="UTF-8"?>\n' +
      '<kml xmlns="http://www.opengis.net/kml/2.2">\n' +
      '<Document>\n' +
      '  <name>Nature favourites</name>\n' +
      '  <description>Exported from nature.togneri.net</description>\n' +
      placemarks + '\n' +
      '</Document>\n' +
      '</kml>\n'
    );
  }

  function downloadBlob(content, mime, filename) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  function wireFavourites() {
    document.getElementById('export-favourites').addEventListener('click', () => {
      const favs = Favourites.load();
      if (!favs.length) { alert('No favourites yet.'); return; }
      downloadBlob(JSON.stringify(favs, null, 2), 'application/json', 'nature-favourites.json');
    });

    document.getElementById('export-favourites-kml').addEventListener('click', () => {
      const favs = Favourites.load();
      if (!favs.length) { alert('No favourites yet.'); return; }
      downloadBlob(buildFavouritesKml(favs), 'application/vnd.google-earth.kml+xml', 'nature-favourites.kml');
    });

    document.getElementById('open-favourites-gmaps').addEventListener('click', () => {
      const favs = Favourites.load();
      if (!favs.length) { alert('No favourites yet.'); return; }
      // Google Maps web caps directions URLs at ~10 stops; take the first 10.
      const slice = favs.slice(0, 10);
      const path = slice.map(f => Number(f.lat).toFixed(6) + ',' + Number(f.lon).toFixed(6)).join('/');
      window.open('https://www.google.com/maps/dir/' + path, '_blank', 'noopener');
    });

    renderFavourites();
  }

  /* ---------- Time-window UI (two-thumb range slider) ---------- */

  // The slider's integer position maps onto a month index. Position 0 is
  // MIN_YEAR-January; max position is the current month. Recomputed on
  // every page load, so the right handle's max really is "today".
  const TIME_WINDOW_MIN_YEAR = 2014;

  function currentYearMonth() {
    const now = new Date();
    return { y: now.getFullYear(), m: now.getMonth() + 1 };
  }

  function ymToIndex(ym) {
    return (ym.y - TIME_WINDOW_MIN_YEAR) * 12 + (ym.m - 1);
  }

  function indexToYM(i) {
    const total = TIME_WINDOW_MIN_YEAR * 12 + Math.max(0, Math.round(i));
    return { y: Math.floor(total / 12), m: (total % 12) + 1 };
  }

  function ymToString(ym) {
    return ym.y + '-' + String(ym.m).padStart(2, '0');
  }

  function parseYMString(s) {
    const m = /^(\d{4})-(\d{1,2})/.exec(String(s || ''));
    return m ? { y: parseInt(m[1], 10), m: parseInt(m[2], 10) } : null;
  }

  function defaultLast12Months() {
    const today = currentYearMonth();
    const startTotal = today.y * 12 + (today.m - 1) - 11; // 12 months inclusive of today
    const start = { y: Math.floor(startTotal / 12), m: (startTotal % 12) + 1 };
    return { start: ymToString(start), end: ymToString(today) };
  }

  function wireTimeWindow() {
    const block = document.getElementById('time-window-block');
    const startInput = document.getElementById('time-window-start');
    const endInput = document.getElementById('time-window-end');
    const last12 = document.getElementById('time-window-12m');
    const allTime = document.getElementById('time-window-all');
    const fromLabel = document.getElementById('time-window-from-label');
    const toLabel = document.getElementById('time-window-to-label');
    const fill = document.getElementById('time-window-fill');
    if (!block || !startInput || !endInput) return;

    const today = currentYearMonth();
    const minIndex = 0;
    const maxIndex = ymToIndex(today);
    startInput.min = String(minIndex);
    startInput.max = String(maxIndex);
    endInput.min = String(minIndex);
    endInput.max = String(maxIndex);

    const prefs = loadPrefs() || {};
    const ov = urlOverrides();
    let initWindow = null;
    if (ov.timeWindow) initWindow = ov.timeWindow;
    else if (prefs.timeWindow && prefs.timeWindow.start && prefs.timeWindow.end) initWindow = prefs.timeWindow;
    else initWindow = defaultLast12Months();

    function clampIndex(i) { return Math.min(maxIndex, Math.max(minIndex, i | 0)); }

    function setHandles(startYM, endYM) {
      // Clamp to slider range; if start > end after clamping, swap them.
      let si = clampIndex(ymToIndex(startYM));
      let ei = clampIndex(ymToIndex(endYM));
      if (si > ei) [si, ei] = [ei, si];
      startInput.value = String(si);
      endInput.value = String(ei);
      renderTrack();
    }

    function renderTrack() {
      const si = parseInt(startInput.value, 10);
      const ei = parseInt(endInput.value, 10);
      const range = Math.max(1, maxIndex - minIndex);
      const leftPct = ((si - minIndex) / range) * 100;
      const rightPct = ((ei - minIndex) / range) * 100;
      if (fill) {
        fill.style.left = leftPct + '%';
        fill.style.width = Math.max(0, rightPct - leftPct) + '%';
      }
      if (fromLabel) fromLabel.textContent = ymToString(indexToYM(si));
      if (toLabel) toLabel.textContent = ymToString(indexToYM(ei));
    }

    function commitFromInputs() {
      let si = clampIndex(parseInt(startInput.value, 10));
      let ei = clampIndex(parseInt(endInput.value, 10));
      // Don't let the thumbs cross: nudge whichever just moved.
      if (si > ei) {
        if (document.activeElement === startInput) ei = si;
        else si = ei;
        startInput.value = String(si);
        endInput.value = String(ei);
      }
      renderTrack();
      Filters.setTimeWindow(ymToString(indexToYM(si)), ymToString(indexToYM(ei)));
      savePrefs();
    }

    const startYM = parseYMString(initWindow.start) || { y: TIME_WINDOW_MIN_YEAR, m: 1 };
    const endYM = parseYMString(initWindow.end) || today;
    setHandles(startYM, endYM);
    Filters.setTimeWindow(ymToString(indexToYM(parseInt(startInput.value, 10))),
                         ymToString(indexToYM(parseInt(endInput.value, 10))));

    startInput.addEventListener('input', commitFromInputs);
    endInput.addEventListener('input', commitFromInputs);

    if (last12) last12.addEventListener('click', () => {
      const w = defaultLast12Months();
      setHandles(parseYMString(w.start), parseYMString(w.end));
      commitFromInputs();
    });
    if (allTime) allTime.addEventListener('click', () => {
      setHandles({ y: TIME_WINDOW_MIN_YEAR, m: 1 }, today);
      commitFromInputs();
    });

    // Show the panel block only when at least one time-aware layer is enabled.
    function syncVisibility() {
      let anyOn = false;
      for (const l of LAYERS) {
        if (l.timeAware && Filters.state.layers.has(l.id)) { anyOn = true; break; }
      }
      block.hidden = !anyOn;
    }
    syncVisibility();
    Filters.onChange(syncVisibility);
  }

  /* ---------- Heat-layer click popup ---------- */
  // L.heatLayer draws onto a canvas, so per-point click handlers aren't
  // possible. Instead listen on the map: when the click is in or near a
  // visible carnivore heat blob, summarise the nearby sightings.

  function wireHeatPopups() {
    map.on('click', (e) => {
      const tw = Filters.state.timeWindow;
      const radiusKm = 35;
      const byLayerHits = new Map();
      for (const layer of LAYERS) {
        if (!(layer.timeAware && layer.timeMode === 'heat')) continue;
        if (!Filters.state.layers.has(layer.id)) continue;
        const entry = leafletLayers.get(layer.id);
        if (!entry || !entry.heatFeatures) continue;
        const hits = [];
        for (const h of entry.heatFeatures) {
          const props = h.feature.properties || {};
          if (Filters.state.regions.size && !Filters.state.regions.has(props.region)) continue;
          if (tw && !inTimeWindow(h.observed_on, tw)) continue;
          const d = haversineKm(e.latlng.lat, e.latlng.lng, h.lat, h.lon);
          if (d <= radiusKm) hits.push(h);
        }
        if (hits.length) byLayerHits.set(layer, hits);
      }
      if (!byLayerHits.size) return;

      const div = document.createElement('div');
      div.className = 'popup';
      const title = document.createElement('h3');
      title.textContent = 'Sightings near this area';
      div.appendChild(title);
      const meta = document.createElement('p');
      meta.className = 'popup-meta';
      meta.textContent = 'Within ~35 km of click';
      div.appendChild(meta);

      const rowsBox = document.createElement('div');
      rowsBox.className = 'popup-rows';
      for (const [layer, hits] of byLayerHits) {
        const dates = hits.map(h => h.observed_on).filter(Boolean).sort();
        const earliest = dates[0];
        const latest = dates[dates.length - 1];
        const row = document.createElement('div');
        row.className = 'popup-row';
        const ico = document.createElement('span');
        ico.className = 'popup-icon';
        ico.textContent = layer.icon;
        const txt = document.createElement('span');
        const labelShort = layer.label.replace(/ sightings$/, '');
        const range = (earliest && latest && earliest !== latest)
          ? earliest + ' to ' + latest
          : (earliest || 'date unknown');
        txt.innerHTML = '<strong>' + hits.length + ' ' + labelShort + '</strong> (' + range + ')';
        row.appendChild(ico);
        row.appendChild(txt);
        rowsBox.appendChild(row);
      }
      div.appendChild(rowsBox);

      const note = document.createElement('p');
      note.className = 'muted small';
      note.style.marginTop = '6px';
      note.textContent = 'Coordinates are coarsened to ~25 km (FinBIF sensitive-species policy), so these mark roughly where sightings clustered, not exact locations.';
      div.appendChild(note);

      L.popup({ maxWidth: 320 }).setLatLng(e.latlng).setContent(div).openOn(map);
    });
  }

  /* ---------- Visibility filter (public vs personal map) ---------- */

  // Two faces of the site share the same static files:
  //   nature.togneri.net   -> public view (no auth); only "public" layers
  //   nature.nightjar.cc/map -> personal view (TinyAuth); all non-hidden
  // visibility.json (data/visibility.json) maps layer id -> "public" |
  // "personal" | "hidden". Edited via the nature-editor admin app.
  const PERSONAL_HOST = 'nature.nightjar.cc';
  const PERSONAL_MODE = (
    window.location.hostname === PERSONAL_HOST ||
    new URLSearchParams(window.location.search).get('personal') === '1'
  );

  async function applyVisibilityFilter() {
    try {
      const r = await fetch('data/visibility.json', { cache: 'no-cache' });
      if (!r.ok) return;
      const vis = await r.json();
      const before = LAYERS.length;
      // Mutate LAYERS in place to drop entries the current view shouldn't see.
      for (let i = LAYERS.length - 1; i >= 0; i--) {
        const v = vis[LAYERS[i].id] || 'public';
        const keep = PERSONAL_MODE ? v !== 'hidden' : v === 'public';
        if (!keep) LAYERS.splice(i, 1);
      }
      console.log(`visibility: ${PERSONAL_MODE ? 'personal' : 'public'} view, kept ${LAYERS.length}/${before} layers`);
    } catch (e) {
      console.warn('visibility.json load failed:', e);
    }
  }

  /* ---------- Boot ---------- */

  document.addEventListener('DOMContentLoaded', async () => {
    await applyVisibilityFilter();
    initMap();
    buildLayerToggles();
    wireFilters();
    wireTimeWindow();
    wireHeatPopups();
    wireTabs();
    wireSidebar();
    wireDivider();
    wireInlinePanel();
    wireFavourites();
    if (window.socialShare && typeof window.socialShare.render === 'function') {
      window.socialShare.render(document.getElementById('footer-share'));
    }
    await wireResources();
    try {
      await loadAllLayers();
      applyFilters();
      // If a region was set via URL / prefs at boot, zoom there
      // automatically so users landing on a deep-link see the area
      // they asked for rather than the whole-country default view.
      if (Filters.state.regions.size) fitToRegions(Filters.state.regions);
    } finally {
      const overlay = document.getElementById('map-loading');
      if (overlay) {
        overlay.classList.add('is-hidden');
        // Remove from layout after the fade transition so it doesn't
        // sit invisibly on top of map controls.
        setTimeout(() => { overlay.style.display = 'none'; }, 300);
      }
    }
  });
})();
