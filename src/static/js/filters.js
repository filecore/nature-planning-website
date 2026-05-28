(function () {
  const GEO_LAYERS = new Set(['geo-bedrock', 'geo-boulders', 'geo-moraines', 'geo-eolian']);

  const state = {
    search: '',
    layers: new Set(),        // enabled layer ids
    regions: new Set(),       // selected regions (empty set = all)
    geoClasses: new Set([1]),  // SYKE arvoluokka, default to Unique only (class 1)
    timeWindow: null,          // {start, end} as 'YYYY-MM' strings, or null for all-time
  };

  const listeners = [];

  function set(partial) {
    Object.assign(state, partial);
    notify();
  }

  function setLayer(layerId, enabled) {
    if (enabled) state.layers.add(layerId); else state.layers.delete(layerId);
    notify();
  }

  function setGeoClass(cls, enabled) {
    if (enabled) state.geoClasses.add(cls); else state.geoClasses.delete(cls);
    notify();
  }

  function setRegion(region, enabled) {
    if (!region) return;
    if (enabled) state.regions.add(region); else state.regions.delete(region);
    notify();
  }

  function setRegions(iterable) {
    state.regions = new Set(iterable || []);
    notify();
  }

  // Set the time-window filter. Pass null (or both args null/undefined) to
  // clear it ("all time"). Otherwise pass two 'YYYY-MM' strings.
  function setTimeWindow(start, end) {
    if (!start || !end) {
      state.timeWindow = null;
    } else {
      state.timeWindow = { start: String(start), end: String(end) };
    }
    notify();
  }

  function onChange(cb) { listeners.push(cb); }

  function notify() {
    for (const cb of listeners) cb(state);
  }

  function matches(feature) {
    const props = feature.properties || {};

    // Layer toggle
    if (!state.layers.has(props.layer)) return false;

    // Search by name
    if (state.search) {
      const name = (props.name || '').toLowerCase();
      if (!name.includes(state.search.toLowerCase())) return false;
    }

    // Region (multi-select: feature must be in one of the selected regions)
    if (state.regions.size && !state.regions.has(props.region)) return false;

    // SYKE value-class filter applies only to the four geo-* layers.
    // Features carry a tag like "class-3" in their features list.
    if (GEO_LAYERS.has(props.layer)) {
      const tags = props.features || [];
      let cls = null;
      for (const t of tags) {
        if (typeof t === 'string' && t.startsWith('class-')) {
          cls = parseInt(t.slice(6), 10);
          break;
        }
      }
      // Untagged points are always shown - we only filter when we have a class.
      if (cls !== null && !state.geoClasses.has(cls)) return false;
    }

    return true;
  }

  function clear() {
    state.search = '';
    state.regions = new Set();
    state.geoClasses = new Set([1]);
    // layers intentionally kept (toggling all off would hide everything)
    notify();
  }

  window.Filters = { state, set, setLayer, setGeoClass, setRegion, setRegions, setTimeWindow, onChange, matches, clear };
})();
