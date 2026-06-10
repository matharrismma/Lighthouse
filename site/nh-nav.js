/**
 * Narrow Highway unified top nav.
 *
 * Drop-in: <script src="/nh-nav.js" defer></script>
 *
 * Auto-injects a top nav strip at the start of <body> that matches the
 * Welcome Screen / TV / Radio / Kids / Games chrome. Reads the page title
 * from <title> or from data-nh-crumb on the body for breadcrumb display.
 *
 * Also exposes window.NH.openSearch() which spawns the same search overlay
 * the Welcome Screen uses, querying /index/packets/search.
 *
 * Safe to include on any page — won't double-inject; only adds CSS in the
 * --nh-* namespace.
 */
(function () {
  if (window.__NH_NAV_INSTALLED__) return;
  window.__NH_NAV_INSTALLED__ = true;

  // Read page identity for breadcrumb
  function getCrumb() {
    const explicit = document.body && document.body.dataset && document.body.dataset.nhCrumb;
    if (explicit) return explicit;
    const t = (document.title || '').split('·')[0].trim();
    if (t && t !== 'Narrow Highway') return t;
    const path = window.location.pathname.replace(/^\/+|\.html$/g, '').replace(/_/g, ' ');
    return (path || 'Home').replace(/\b\w/g, c => c.toUpperCase());
  }

  // Inject CSS variables and chrome styles, scoped to --nh-* names to avoid clashes
  const css = `
    .nh-nav-installed { padding-top: 56px !important; }
    .nh-topnav {
      position: fixed; top: 0; left: 0; right: 0; z-index: 99999;
      background: rgba(10,8,16,0.94); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
      border-bottom: 1px solid #29232f;
      display: flex; align-items: center; justify-content: space-between;
      padding: 0 24px; height: 56px;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      box-sizing: border-box;
    }
    .nh-wordmark {
      font-family: 'JetBrains Mono', ui-monospace, monospace;
      font-size: 12px; letter-spacing: 0.22em; text-transform: uppercase;
      color: #c9a87c; font-weight: 600; text-decoration: none;
      display: inline-flex; align-items: center; gap: 9px;
    }
    .nh-wordmark-dot {
      width: 8px; height: 8px; border-radius: 50%;
      background: #c9a87c; box-shadow: 0 0 8px rgba(201,168,124,0.55);
    }
    .nh-crumbs {
      font-family: 'JetBrains Mono', ui-monospace, monospace;
      font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase;
      color: #6e6878;
      display: flex; align-items: center; gap: 8px;
    }
    .nh-crumbs a { color: #b3aabd; text-decoration: none; }
    .nh-crumbs a:hover { color: #c9a87c; }
    .nh-crumb-sep { color: #4e4858; }
    .nh-search-btn {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 6px 12px; border-radius: 6px;
      background: #161320; border: 1px solid #29232f;
      font-family: 'JetBrains Mono', ui-monospace, monospace;
      font-size: 12px; letter-spacing: 0.04em;
      color: #b3aabd; cursor: pointer;
      transition: all 0.15s;
    }
    .nh-search-btn:hover { border-color: #c9a87c; color: #c9a87c; }
    @media (max-width: 600px) { .nh-crumbs { display: none; } }

    /* Search overlay (same as Welcome Screen) */
    .nh-search-overlay {
      position: fixed; inset: 0; background: rgba(10,8,16,0.85);
      backdrop-filter: blur(6px); display: none;
      align-items: flex-start; justify-content: center;
      padding-top: 12vh; z-index: 100000;
    }
    .nh-search-overlay.open { display: flex; }
    .nh-search-box {
      width: min(640px, 92vw);
      background: #161320; border: 1px solid #3a3142;
      border-radius: 12px; padding: 6px;
      box-shadow: 0 30px 80px rgba(0,0,0,0.6);
      font-family: 'Inter', sans-serif;
    }
    .nh-search-box input {
      width: 100%; padding: 18px 22px;
      background: transparent; border: none;
      color: #ede7db; font-size: 17px;
      font-family: inherit; outline: none;
    }
    .nh-search-results { padding: 4px; max-height: 50vh; overflow-y: auto; }
    .nh-search-result {
      display: block; padding: 10px 16px; border-radius: 6px;
      color: #b3aabd; font-size: 13px; text-decoration: none;
    }
    .nh-search-result:hover { background: #1d1828; color: #ede7db; }
    .nh-sr-kind {
      display: inline-block; font-family: 'JetBrains Mono', ui-monospace, monospace;
      font-size: 9.5px; letter-spacing: 0.12em; text-transform: uppercase;
      color: #c9a87c; margin-right: 10px; min-width: 70px;
    }
  `;

  function inject() {
    const style = document.createElement('style');
    style.id = 'nh-nav-style';
    style.textContent = css;
    document.head.appendChild(style);

    document.body.classList.add('nh-nav-installed');

    const crumb = getCrumb();
    const onHome = window.location.pathname === '/' || window.location.pathname === '/index.html';

    const nav = document.createElement('nav');
    nav.className = 'nh-topnav';
    nav.innerHTML = `
      <a href="/" class="nh-wordmark"><span class="nh-wordmark-dot"></span> Narrow Highway</a>
      <div class="nh-crumbs">
        ${onHome ? '<span>Home</span>' : '<a href="/">Home</a><span class="nh-crumb-sep">›</span><span>' + escapeHtml(crumb) + '</span>'}
      </div>
      <button class="nh-search-btn" type="button" aria-label="Search">🔍 Search</button>
    `;
    document.body.insertBefore(nav, document.body.firstChild);

    // Search overlay
    const ov = document.createElement('div');
    ov.className = 'nh-search-overlay';
    ov.innerHTML = `
      <div class="nh-search-box">
        <input type="search" placeholder="Search the substrate… (almanac, codex, scripture, packets)" autocomplete="off">
        <div class="nh-search-results"></div>
      </div>
    `;
    document.body.appendChild(ov);

    const btn = nav.querySelector('.nh-search-btn');
    const input = ov.querySelector('input');
    const results = ov.querySelector('.nh-search-results');

    function open() { ov.classList.add('open'); setTimeout(() => input.focus(), 50); }
    function close() { ov.classList.remove('open'); input.value = ''; results.innerHTML = ''; }

    btn.addEventListener('click', open);
    ov.addEventListener('click', e => { if (e.target === ov) close(); });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') close();
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); open(); }
    });

    let timer = null;
    input.addEventListener('input', e => {
      clearTimeout(timer);
      const q = e.target.value.trim();
      if (!q) { results.innerHTML = ''; return; }
      timer = setTimeout(async () => {
        try {
          const r = await fetch('/index/packets/search?q=' + encodeURIComponent(q) + '&limit=10');
          if (!r.ok) { results.innerHTML = '<div class="nh-search-result">No results.</div>'; return; }
          const j = await r.json();
          const items = j.items || j.results || j.packets || [];
          if (!items.length) { results.innerHTML = '<div class="nh-search-result">No results.</div>'; return; }
          results.innerHTML = items.map(it => {
            const kind = (it.kind || it.type || 'packet').toString().slice(0, 10);
            const title = (it.title || it.claim || it.subject || it.text || '').toString().slice(0, 100);
            const id = it.id || it.packet_id || '';
            const href = id ? '/packets.html?q=' + encodeURIComponent(id) : '/packets.html?q=' + encodeURIComponent(q);
            return '<a class="nh-search-result" href="' + href + '"><span class="nh-sr-kind">' + escapeHtml(kind) + '</span>' + escapeHtml(title) + '</a>';
          }).join('');
        } catch (e) { results.innerHTML = '<div class="nh-search-result">Search unavailable.</div>'; }
      }, 200);
    });

    window.NH = window.NH || {};
    window.NH.openSearch = open;
  }

  function escapeHtml(s) {
    return (s || '').toString()
      .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
      .replaceAll('"','&quot;').replaceAll("'",'&#39;');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inject);
  } else {
    inject();
  }
})();
