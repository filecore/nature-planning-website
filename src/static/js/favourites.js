(function () {
  const KEY = 'nature.favourites.v1';

  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }

  function save(list) {
    localStorage.setItem(KEY, JSON.stringify(list));
  }

  function makeId(layerId, featureId) {
    return layerId + ':' + featureId;
  }

  function has(layerId, featureId) {
    const id = makeId(layerId, featureId);
    return load().some(f => f.id === id);
  }

  function add(entry) {
    const list = load();
    if (list.some(f => f.id === entry.id)) return list;
    list.push(Object.assign({ added_at: new Date().toISOString() }, entry));
    save(list);
    return list;
  }

  function remove(id) {
    const list = load().filter(f => f.id !== id);
    save(list);
    return list;
  }

  function toggle(entry) {
    return has(entry.layerId, entry.featureId) ? remove(entry.id) : add(entry);
  }

  window.Favourites = { load, save, makeId, has, add, remove, toggle, KEY };
})();
