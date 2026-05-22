// Footer social-share widget. Privacy-respecting:
//   - No third-party scripts. Inline SVG icons only.
//   - Web Share API used when available (mobile / Edge / Safari);
//     this routes to whichever apps the visitor has installed,
//     including Signal and Instagram which don't have web share URLs.
//   - When Web Share isn't supported, falls back to a row of
//     per-platform deep-link buttons + a "copy link" action.
//   - Nothing leaves the browser until the user taps a button.

(function () {
  'use strict';

  const SHARE_URL = 'https://nature.togneri.net/';
  const SHARE_TITLE = 'Natural data (Finland)';
  const SHARE_TEXT = 'A one-stop map of Finnish national parks, laavus, saunas, water levels, climbing crags, wildlife observations and more.';

  // Inline SVGs sourced from Simple Icons (CC0) and a couple of generic
  // glyphs. Each path is the single shape that defines the brand icon
  // at 24x24, drawn in currentColor so we can theme via CSS.
  const ICONS = {
    share: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92 1.61 0 2.92-1.31 2.92-2.92s-1.31-2.92-2.92-2.92z"/></svg>',
    whatsapp: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413"/></svg>',
    telegram: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>',
    facebook: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>',
    linkedin: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.063 2.063 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>',
    x: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>',
    email: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 12.713l-11.985-9.713h23.97l-11.985 9.713zm0 2.574l-12-9.725v15.438h24v-15.438l-12 9.725z"/></svg>',
    link: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z"/></svg>'
  };

  function enc(s) { return encodeURIComponent(s); }

  const TARGETS = [
    { key: 'whatsapp', label: 'WhatsApp', url: 'https://wa.me/?text=' + enc(SHARE_TITLE + ' - ' + SHARE_URL) },
    { key: 'telegram', label: 'Telegram', url: 'https://t.me/share/url?url=' + enc(SHARE_URL) + '&text=' + enc(SHARE_TITLE) },
    { key: 'facebook', label: 'Facebook', url: 'https://www.facebook.com/sharer/sharer.php?u=' + enc(SHARE_URL) },
    { key: 'linkedin', label: 'LinkedIn', url: 'https://www.linkedin.com/sharing/share-offsite/?url=' + enc(SHARE_URL) },
    { key: 'x',        label: 'X',        url: 'https://twitter.com/intent/tweet?text=' + enc(SHARE_TITLE) + '&url=' + enc(SHARE_URL) },
    { key: 'email',    label: 'Email',    url: 'mailto:?subject=' + enc(SHARE_TITLE) + '&body=' + enc(SHARE_TEXT + '\n\n' + SHARE_URL) }
  ];

  function svgButton(href, label, iconKey) {
    return '<a href="' + href + '" class="share-btn" target="_blank" rel="noopener noreferrer" aria-label="' + label + '" title="' + label + '">' + ICONS[iconKey] + '</a>';
  }

  function copyButton() {
    return '<button type="button" class="share-btn share-copy" aria-label="Copy link" title="Copy link">' + ICONS.link + '</button>';
  }

  function nativeShareButton(label) {
    return '<button type="button" class="share-btn share-native" aria-label="' + label + '" title="' + label + '">' + ICONS.share + '</button>';
  }

  function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      try {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        const ok = document.execCommand('copy');
        document.body.removeChild(ta);
        ok ? resolve() : reject(new Error('copy failed'));
      } catch (e) { reject(e); }
    });
  }

  function flashToast(msg) {
    let toast = document.getElementById('share-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'share-toast';
      toast.className = 'share-toast';
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.add('visible');
    clearTimeout(flashToast._t);
    flashToast._t = setTimeout(function () { toast.classList.remove('visible'); }, 2200);
  }

  function render(container) {
    if (!container) return;
    const supportsNative = typeof navigator.share === 'function';
    const buttons = [];
    if (supportsNative) {
      buttons.push(nativeShareButton('Share'));
    }
    TARGETS.forEach(function (tgt) {
      buttons.push(svgButton(tgt.url, tgt.label, tgt.key));
    });
    buttons.push(copyButton());

    container.innerHTML =
      '<span class="footer-share-label">Share this site</span>' +
      '<div class="share-buttons">' + buttons.join('') + '</div>';

    const nativeBtn = container.querySelector('.share-native');
    if (nativeBtn) {
      nativeBtn.addEventListener('click', function () {
        navigator.share({ title: SHARE_TITLE, text: SHARE_TEXT, url: SHARE_URL })
          .catch(function () { /* user cancelled */ });
      });
    }
    const copyBtn = container.querySelector('.share-copy');
    if (copyBtn) {
      copyBtn.addEventListener('click', function () {
        copyToClipboard(SHARE_URL)
          .then(function () { flashToast('Link copied to clipboard'); })
          .catch(function () { flashToast('Could not copy. Long-press the link to copy manually.'); });
      });
    }
  }

  window.socialShare = { render: render };
})();
