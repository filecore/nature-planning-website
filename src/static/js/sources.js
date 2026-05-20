(function () {
  let DATA = null;

  async function load() {
    if (DATA) return DATA;
    const res = await fetch('data/sources.json', { cache: 'no-cache' });
    DATA = await res.json();
    return DATA;
  }

  function renderList(container, onInline) {
    if (!DATA) return;
    const categories = new Map(DATA.categories.map(c => [c.id, c.label]));
    container.innerHTML = '';

    // Two accordions: Web resources (anything whose category does not start
    // with apps-) and Mobile apps (category starts with apps-). Group by
    // category within each, in the order categories appear in the manifest.
    const groupedAll = new Map();
    for (const s of DATA.sources) {
      if (!groupedAll.has(s.category)) groupedAll.set(s.category, []);
      groupedAll.get(s.category).push(s);
    }

    const webGroups = new Map();
    const appGroups = new Map();
    for (const [catId, items] of groupedAll) {
      (catId.startsWith('apps-') ? appGroups : webGroups).set(catId, items);
    }

    const accordions = [
      { id: 'web',  label: 'Web resources', groups: webGroups },
      { id: 'apps', label: 'Mobile apps',   groups: appGroups },
    ];

    for (const acc of accordions) {
      if (acc.groups.size === 0) continue;
      const wrap = document.createElement('details');
      wrap.className = 'resource-accordion';
      wrap.dataset.accordion = acc.id;
      // Both top-level accordions start collapsed; the user opens what
      // they want explicitly.

      const summary = document.createElement('summary');
      summary.className = 'resource-accordion-summary';
      const countN = Array.from(acc.groups.values()).reduce((n, items) => n + items.length, 0);
      summary.innerHTML = `<span class="resource-accordion-label">${acc.label}</span>` +
                         `<span class="resource-accordion-count">${countN}</span>`;
      wrap.appendChild(summary);

      const body = document.createElement('div');
      body.className = 'resource-accordion-body';

      // One nested <details> per category so the user can drill in further
      // without scrolling through every category at once.
      for (const [catId, items] of acc.groups) {
        const sub = document.createElement('details');
        sub.className = 'resource-subgroup';
        sub.dataset.subgroup = catId;
        // Subgroups also start collapsed.

        const subSummary = document.createElement('summary');
        subSummary.className = 'resource-subgroup-summary';
        const label = (categories.get(catId) || catId).replace(/^Apps - /, '');
        subSummary.innerHTML = `<span class="resource-subgroup-label">${label}</span>` +
                               `<span class="resource-subgroup-count">${items.length}</span>`;
        sub.appendChild(subSummary);

        const subBody = document.createElement('div');
        subBody.className = 'resource-subgroup-body';
        for (const src of items) {
          subBody.appendChild(makeCard(src, onInline));
        }
        sub.appendChild(subBody);
        body.appendChild(sub);
      }
      wrap.appendChild(body);
      container.appendChild(wrap);
    }

    // Exclusive-open behaviour: opening one closes the other, and the
    // just-opened summary scrolls to the top of the sidebar scroll area.
    const all = container.querySelectorAll('details.resource-accordion');
    const scroller = document.getElementById('sidebar-scroll');
    all.forEach((d) => {
      d.addEventListener('toggle', () => {
        if (!d.open) return;
        all.forEach((other) => { if (other !== d) other.open = false; });
        if (scroller) {
          // Use the summary's offset relative to the scroll container so
          // sticky headers / sibling content don't throw the position off.
          const summary = d.querySelector('summary');
          if (summary) {
            const offsetTop = summary.offsetTop - scroller.offsetTop;
            scroller.scrollTo({ top: offsetTop, behavior: 'smooth' });
          }
        }
      });
    });
  }

  function makeCard(src, onInline) {
    const card = document.createElement('article');
    card.className = 'resource-card';

    const title = document.createElement('h3');
    title.textContent = src.title;
    card.appendChild(title);

    if (src.blurb) {
      const blurb = document.createElement('p');
      blurb.className = 'blurb';
      blurb.textContent = src.blurb;
      card.appendChild(blurb);
    }

    const actions = document.createElement('div');
    actions.className = 'card-actions';

    // Dual store links for Play-Store-backed apps; a single "Open site"
    // button for everything else.
    if (src.android_url || src.ios_url) {
      if (src.android_url) actions.appendChild(makeStoreLink('Android', src.android_url, 'ghost'));
      if (src.ios_url)     actions.appendChild(makeStoreLink('iOS',     src.ios_url,     'ghost'));
    } else {
      const openBtn = document.createElement('button');
      openBtn.type = 'button';
      openBtn.textContent = 'Open site';
      openBtn.className = 'ghost';
      openBtn.addEventListener('click', () => window.open(src.url, '_blank', 'noopener'));
      actions.appendChild(openBtn);
    }

    if (src.inline) {
      const inlineBtn = document.createElement('button');
      inlineBtn.type = 'button';
      inlineBtn.textContent = 'Open inline';
      inlineBtn.addEventListener('click', () => onInline(src));
      actions.appendChild(inlineBtn);
    }

    card.appendChild(actions);
    return card;
  }

  function makeStoreLink(label, url, cls) {
    const a = document.createElement('a');
    a.href = url;
    a.target = '_blank';
    a.rel = 'noopener';
    a.className = cls || '';
    a.textContent = label;
    return a;
  }

  window.Sources = { load, renderList };
})();
