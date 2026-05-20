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

    // Group by category
    const grouped = new Map();
    for (const s of DATA.sources) {
      if (!grouped.has(s.category)) grouped.set(s.category, []);
      grouped.get(s.category).push(s);
    }

    for (const [catId, items] of grouped) {
      const h = document.createElement('h3');
      h.textContent = categories.get(catId) || catId;
      h.style.fontSize = '12px';
      h.style.textTransform = 'uppercase';
      h.style.letterSpacing = '0.6px';
      h.style.color = '#888';
      h.style.margin = '14px 0 6px';
      container.appendChild(h);

      for (const src of items) {
        container.appendChild(makeCard(src, onInline));
      }
    }
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
