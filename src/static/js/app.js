(function () {
  // Layer registry. Each entry maps a GeoJSON file in data/layers/ to a
  // user-facing label and a marker color. Adding a new mapped source is a
  // one-liner here plus a new adapter that writes the matching file.
  const LAYERS = [
    { id: 'national-parks', file: 'national-parks.geojson', label: 'National parks and hiking areas', color: '#1f7a3a', letter: 'N' },
    { id: 'laavut',         file: 'laavut.geojson',         label: 'Laavus and kotas',                 color: '#7a4a1f', letter: 'L' },
    { id: 'saunas',         file: 'saunas.geojson',         label: 'Saunas in nature',                 color: '#8a4fcf', letter: 'S' },
    { id: 'waterfalls',     file: 'waterfalls.geojson',     label: 'Waterfalls',                       color: '#2e7bd6', letter: 'W' },
    { id: 'breweries',      file: 'breweries.geojson',      label: 'Breweries, wineries, distilleries',color: '#d4a017', letter: 'B' },
  ];

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

  function buildPopup(feature, layer) {
    const props = feature.properties || {};
    const featureId = props.id || (props.name + ':' + feature.geometry.coordinates.join(','));
    const favEntryId = Favourites.makeId(layer.id, featureId);
    const isFav = Favourites.has(layer.id, featureId);

    const container = document.createElement('div');

    const title = document.createElement('h3');
    title.textContent = props.name || '(unnamed)';
    container.appendChild(title);

    const meta = document.createElement('p');
    meta.className = 'popup-meta';
    meta.textContent = [layer.label, props.region].filter(Boolean).join(' · ');
    container.appendChild(meta);

    if (props.description) {
      const desc = document.createElement('p');
      desc.textContent = props.description;
      container.appendChild(desc);
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

    if (props.source_url) {
      const link = document.createElement('a');
      link.href = props.source_url;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = 'View source';
      actions.appendChild(link);
    }

    const star = document.createElement('button');
    star.className = 'star-button' + (isFav ? ' active' : '');
    star.textContent = isFav ? 'Saved' : 'Save';
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
      star.textContent = nowFav ? 'Saved' : 'Save';
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
    for (const layer of LAYERS) {
      const label = document.createElement('label');
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.value = layer.id;
      cb.checked = true;
      Filters.setLayer(layer.id, true);
      cb.addEventListener('change', () => {
        Filters.setLayer(layer.id, cb.checked);
      });
      const swatch = document.createElement('span');
      swatch.className = 'layer-swatch';
      swatch.style.background = layer.color;
      label.appendChild(cb);
      label.appendChild(swatch);
      label.appendChild(document.createTextNode(layer.label));
      container.appendChild(label);
    }
  }

  function wireFilters() {
    document.getElementById('search-box').addEventListener('input', (e) => {
      Filters.set({ search: e.target.value });
    });

    document.querySelectorAll('#feature-toggles input[type="checkbox"]').forEach(cb => {
      cb.addEventListener('change', () => Filters.setFeature(cb.value, cb.checked));
    });

    document.getElementById('region-select').addEventListener('change', (e) => {
      Filters.set({ region: e.target.value });
    });

    document.getElementById('clear-filters').addEventListener('click', () => {
      document.getElementById('search-box').value = '';
      document.querySelectorAll('#feature-toggles input[type="checkbox"]').forEach(cb => cb.checked = false);
      document.getElementById('region-select').value = '';
      Filters.clear();
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

  /* ---------- Sidebar toggle ---------- */

  function wireSidebar() {
    const sidebar = document.getElementById('sidebar');
    const btn = document.getElementById('sidebar-toggle');
    let floating = null;
    btn.addEventListener('click', () => {
      sidebar.classList.remove('open');
      floating = document.createElement('button');
      floating.className = 'sidebar-toggle-floating';
      floating.textContent = 'Menu';
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
    wireInlinePanel();
    wireFavourites();
    await wireResources();
    await loadAllLayers();
    applyFilters();
  });
})();
