(function () {
  const state = {
    search: '',
    layers: new Set(),        // enabled layer ids
    features: new Set(),      // required feature tags
    region: '',               // selected region (empty = all)
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

  function setFeature(tag, enabled) {
    if (enabled) state.features.add(tag); else state.features.delete(tag);
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

    // Feature flags
    if (state.features.size > 0) {
      const flags = new Set(props.features || []);
      for (const required of state.features) {
        if (!flags.has(required)) return false;
      }
    }

    // Region
    if (state.region && props.region !== state.region) return false;

    return true;
  }

  function clear() {
    state.search = '';
    state.features.clear();
    state.region = '';
    // layers intentionally kept (toggling all off would hide everything)
    notify();
  }

  window.Filters = { state, set, setLayer, setFeature, onChange, matches, clear };
})();
