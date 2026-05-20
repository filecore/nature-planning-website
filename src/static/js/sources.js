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

    const blurb = document.createElement('p');
    blurb.className = 'blurb';
    blurb.textContent = src.blurb;
    card.appendChild(blurb);

    const actions = document.createElement('div');
    actions.className = 'card-actions';

    const openLink = document.createElement('a');
    openLink.href = src.url;
    openLink.target = '_blank';
    openLink.rel = 'noopener';
    const openBtn = document.createElement('button');
    openBtn.textContent = 'Open site';
    openBtn.className = 'ghost';
    openBtn.addEventListener('click', () => window.open(src.url, '_blank', 'noopener'));
    actions.appendChild(openBtn);

    if (src.inline) {
      const inlineBtn = document.createElement('button');
      inlineBtn.textContent = 'Open inline';
      inlineBtn.addEventListener('click', () => onInline(src));
      actions.appendChild(inlineBtn);
    }

    card.appendChild(actions);
    return card;
  }

  window.Sources = { load, renderList };
})();
