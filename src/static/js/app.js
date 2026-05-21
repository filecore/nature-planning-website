(function () {
  // Layer registry. Each entry maps a GeoJSON file in data/layers/ to a
  // user-facing label and a marker color. Adding a new mapped source is a
  // one-liner here plus a new adapter that writes the matching file.
  // Every layer belongs to a group. Order of layers within a group, and of
  // groups themselves, follows the GROUP_ORDER list below.
  const LAYERS = [
    { id: 'national-parks',   file: 'national-parks.geojson',   label: 'National parks and hiking areas', color: '#1f7a3a', icon: '\u{1F332}', group: 'hiking' },
    { id: 'laavut',           file: 'laavut.geojson',           label: 'Laavus and kotas',                 color: '#7a4a1f', icon: '\u{1F3D5}', group: 'hiking' },
    { id: 'saunas',           file: 'saunas.geojson',           label: 'Saunas in nature',                 color: '#8a4fcf', icon: '\u{1F9D6}', group: 'hiking' },
    { id: 'uusimaa-classics', file: 'uusimaa-classics.geojson', label: 'Uusimaa classics',                 color: '#facc15', icon: '⭐',    group: 'hiking' },
    { id: 'archaeology',      file: 'archaeology.geojson',      label: 'Archaeological sites (VARK)',      color: '#a0292e', icon: '\u{1F3DB}', group: 'natural-sites' },
    { id: 'sacred-sites',     file: 'sacred-sites.geojson',     label: 'Sacred natural sites',             color: '#5b3a8a', icon: '✨',    group: 'natural-sites' },
    { id: 'caves',            file: 'caves.geojson',            label: 'Caves',                            color: '#5a4a36', icon: '\u{1F573}️', group: 'natural-sites' },
    { id: 'beaches',          file: 'beaches.geojson',          label: 'Public swimming beaches',          color: '#4ec3e0', icon: '\u{1F3D6}', group: 'swimming-water' },
    { id: 'water-sensors',    file: 'water-sensors.geojson',    label: 'Live water temperature (Helsinki)',color: '#14b8a6', icon: '\u{1F321}', group: 'swimming-water' },
    { id: 'algae',            file: 'algae.geojson',            label: 'Recent algae observations',        color: '#84cc16', icon: '\u{1F33F}', group: 'swimming-water' },
    { id: 'waterfalls',       file: 'waterfalls.geojson',       label: 'Waterfalls',                       color: '#2e7bd6', icon: '\u{1F30A}', group: 'swimming-water' },
    { id: 'lakes',            file: 'lakes.geojson',            label: 'Lakes (≥ 0.5 km², Järviwiki)', color: '#0b6fb2', icon: '\u{1F3DE}', group: 'swimming-water' },
    { id: 'breweries',        file: 'breweries.geojson',        label: 'Breweries',                        color: '#d4a017', icon: '\u{1F37A}', group: 'alcohol' },
    { id: 'wineries',         file: 'wineries.geojson',         label: 'Wineries',                         color: '#8a1b3b', icon: '\u{1F377}', group: 'alcohol' },
    { id: 'distilleries',     file: 'distilleries.geojson',     label: 'Distilleries',                     color: '#c97a3d', icon: '\u{1F943}', group: 'alcohol' },
  ];

  const GROUPS = {
    'hiking':          { label: 'Hiking' },
    'natural-sites':   { label: 'Natural sites' },
    'swimming-water':  { label: 'Swimming and water' },
    'alcohol':         { label: 'Alcohol' },
  };
  const GROUP_ORDER = ['hiking', 'natural-sites', 'swimming-water', 'alcohol'];

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

  function savePrefs() {
    const layers = {};
    for (const layer of LAYERS) {
      layers[layer.id] = Filters.state.layers.has(layer.id);
    }
    const prefs = {
      layers,
      features: Array.from(Filters.state.features),
      region: Filters.state.region,
      search: Filters.state.search,
    };
    try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); } catch (e) {}
  }

  function initialLayerChecked(layerId) {
    const prefs = loadPrefs();
    if (prefs && prefs.layers && Object.prototype.hasOwnProperty.call(prefs.layers, layerId)) {
      return Boolean(prefs.layers[layerId]);
    }
    return DEFAULT_ON_LAYERS.has(layerId);
  }

  const FINLAND_CENTER = [64.5, 26.0];
  const FINLAND_ZOOM = 6;

  let map;
  let leafletLayers = new Map();  // layerId -> Leaflet LayerGroup
  let featureLookup = new Map();  // 'layerId:featureId' -> Leaflet marker
  let lastFreshness = null;

  /* ---------- Map bootstrap ---------- */

  function initMap() {
    map = L.map('map', {
      center: FINLAND_CENTER,
      zoom: FINLAND_ZOOM,
      zoomControl: true,
    });

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

  function buildLeafletLayer(feature, layer) {
    const props = feature.properties || {};
    const name = props.name || '(unnamed)';
    let lyr;

    if (feature.geometry && feature.geometry.type === 'Point') {
      const [lat, lon] = featureCentroid(feature);
      lyr = L.circleMarker([lat, lon], {
        radius: 7,
        color: '#fff',
        weight: 1.5,
        fillColor: layer.color,
        fillOpacity: 0.85,
      });
      lyr._kind = 'point';
    } else {
      lyr = L.geoJSON(feature, {
        style: {
          color: layer.color,
          weight: 1.5,
          fillColor: layer.color,
          fillOpacity: 0.18,
        },
      });
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

  function mapsLink(lat, lon, name) {
    // Universal Google Maps deeplink with a label. Works on desktop and
    // hands off cleanly to the native maps app on iOS / Android.
    const q = encodeURIComponent(`${lat},${lon}`);
    const label = name ? '+' + encodeURIComponent(`(${name})`) : '';
    return `https://www.google.com/maps/search/?api=1&query=${q}${label}`;
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

  async function loadAllLayers() {
    const allRegions = new Set();
    for (const layer of LAYERS) {
      const geo = await loadLayer(layer);
      if (!geo || !Array.isArray(geo.features)) continue;

      const group = L.layerGroup().addTo(map);
      leafletLayers.set(layer.id, group);

      for (const feature of geo.features) {
        // Tag every feature with its owning layer so filters can match.
        feature.properties = feature.properties || {};
        feature.properties.layer = layer.id;
        const featureId = feature.properties.id || (feature.properties.name + ':' + JSON.stringify(featureCentroid(feature)));
        const lyr = buildLeafletLayer(feature, layer);
        lyr._feature = feature;
        lyr.addTo(group);
        featureLookup.set(Favourites.makeId(layer.id, featureId), lyr);
        if (feature.properties.region) allRegions.add(feature.properties.region);
      }

      if (geo.generated_at && (!lastFreshness || geo.generated_at > lastFreshness)) {
        lastFreshness = geo.generated_at;
      }
    }
    populateRegionSelect(Array.from(allRegions).sort());
    updateFreshness();
  }

  function populateRegionSelect(regions) {
    const sel = document.getElementById('region-select');
    for (const r of regions) {
      const opt = document.createElement('option');
      opt.value = r;
      opt.textContent = r;
      sel.appendChild(opt);
    }
    // Re-apply the saved region now that the option exists.
    if (sel.dataset.pending) {
      sel.value = sel.dataset.pending;
      delete sel.dataset.pending;
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

    for (const groupId of orderedGroups) {
      const layers = groupedByKey.get(groupId);
      const meta = GROUPS[groupId] || { label: groupId };
      const wrap = document.createElement('details');
      wrap.className = 'layer-group';
      wrap.open = true;

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
    }
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
    const searchBox = document.getElementById('search-box');
    const regionSel = document.getElementById('region-select');

    // Restore non-layer prefs.
    if (typeof prefs.search === 'string') {
      searchBox.value = prefs.search;
      Filters.set({ search: prefs.search });
    }
    if (Array.isArray(prefs.features)) {
      for (const tag of prefs.features) Filters.setFeature(tag, true);
      document.querySelectorAll('#feature-toggles input[type="checkbox"]').forEach(cb => {
        cb.checked = prefs.features.includes(cb.value);
      });
    }
    if (typeof prefs.region === 'string' && prefs.region) {
      // Region values are populated later from layer data, but the saved
      // string can be set immediately; the select shows it once populateRegionSelect runs.
      regionSel.dataset.pending = prefs.region;
      Filters.set({ region: prefs.region });
    }

    searchBox.addEventListener('input', (e) => {
      Filters.set({ search: e.target.value });
      savePrefs();
    });

    document.querySelectorAll('#feature-toggles input[type="checkbox"]').forEach(cb => {
      cb.addEventListener('change', () => {
        Filters.setFeature(cb.value, cb.checked);
        savePrefs();
      });
    });

    regionSel.addEventListener('change', (e) => {
      Filters.set({ region: e.target.value });
      savePrefs();
    });

    document.getElementById('clear-filters').addEventListener('click', () => {
      searchBox.value = '';
      document.querySelectorAll('#feature-toggles input[type="checkbox"]').forEach(cb => cb.checked = false);
      regionSel.value = '';
      Filters.clear();
      savePrefs();
    });

    Filters.onChange(applyFilters);
  }

  function applyFilters() {
    let visible = 0;
    for (const [layerId, group] of leafletLayers) {
      group.eachLayer(lyr => {
        const match = Filters.matches(lyr._feature);
        if (match) visible++;
        const fillTarget = lyr._kind === 'polygon' ? 0.18 : 0.85;
        const styleOn  = { opacity: 1, fillOpacity: fillTarget };
        const styleOff = { opacity: 0, fillOpacity: 0 };
        const apply = (sub) => {
          if (typeof sub.setStyle === 'function') sub.setStyle(match ? styleOn : styleOff);
        };
        if (typeof lyr.eachLayer === 'function') {
          lyr.eachLayer(apply);
        } else {
          apply(lyr);
        }
      });
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

  function isMobile() { return window.innerWidth <= MOBILE_BP; }

  function clampVh(v) { return Math.min(80, Math.max(15, v)); }

  function applySidebarSize() {
    const sidebar = document.getElementById('sidebar');
    if (isMobile()) {
      const vh = parseFloat(localStorage.getItem(STORAGE_KEY_VH) || '40');
      sidebar.style.height = clampVh(vh) + 'vh';
    } else {
      sidebar.style.height = '';
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
      const vh = parseFloat(sidebar.style.height) || 40;
      localStorage.setItem(STORAGE_KEY_VH, clampVh(vh));
      // Leaflet needs a nudge when its container resizes mid-gesture
      if (typeof map !== 'undefined' && map) map.invalidateSize();
    }

    function moveTo(clientY) {
      // The sidebar sits at the top of the viewport; its height equals the
      // pointer's Y position minus any offset above (none here since #app
      // fills the viewport). Subtract a small fudge for the divider itself.
      const vh = (clientY / window.innerHeight) * 100;
      sidebar.style.height = clampVh(vh) + 'vh';
      if (typeof map !== 'undefined' && map) map.invalidateSize();
    }

    divider.addEventListener('touchstart', (e) => {
      if (!isMobile()) return;
      resizing = true;
      divider.classList.add('active');
      e.preventDefault();
    }, { passive: false });

    document.addEventListener('touchmove', (e) => {
      if (!resizing) return;
      moveTo(e.touches[0].clientY);
      e.preventDefault();
    }, { passive: false });

    document.addEventListener('touchend', endDrag);
    document.addEventListener('touchcancel', endDrag);

    // Mouse drag for desktop-mode testing in narrow windows.
    divider.addEventListener('mousedown', (e) => {
      if (!isMobile()) return;
      resizing = true;
      divider.classList.add('active');
      document.body.style.userSelect = 'none';
      e.preventDefault();
    });
    document.addEventListener('mousemove', (e) => {
      if (!resizing) return;
      if (e.buttons === 0) { endDrag(); return; }
      moveTo(e.clientY);
    }, true);
    document.addEventListener('mouseup', () => {
      if (!resizing) return;
      document.body.style.userSelect = '';
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
      floating = document.createElement('button');
      floating.className = 'sidebar-toggle-floating';
      floating.setAttribute('aria-label', 'Open sidebar');
      // U+203A single right-pointing angle quotation: "open / expand"
      floating.innerHTML = '&#x203A; Menu';
      floating.addEventListener('click', () => {
        sidebar.classList.add('open');
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
    setTimeout(() => map.invalidateSize(), 200);
  }

  function wireInlinePanel() {
    document.getElementById('inline-panel-close').addEventListener('click', () => {
      const panel = document.getElementById('inline-panel');
      panel.classList.add('hidden');
      document.getElementById('inline-panel-frame').src = 'about:blank';
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
      fly.textContent = 'Fly to';
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

  function wireFavourites() {
    document.getElementById('export-favourites').addEventListener('click', () => {
      const blob = new Blob([JSON.stringify(Favourites.load(), null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'nature-favourites.json';
      a.click();
      URL.revokeObjectURL(url);
    });
    renderFavourites();
  }

  /* ---------- Boot ---------- */

  document.addEventListener('DOMContentLoaded', async () => {
    initMap();
    buildLayerToggles();
    wireFilters();
    wireTabs();
    wireSidebar();
    wireDivider();
    wireInlinePanel();
    wireFavourites();
    await wireResources();
    await loadAllLayers();
    applyFilters();
  });
})();
