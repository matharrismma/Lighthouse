/**
 * vibe.js — site-wide atmospheric interactions.
 *
 * Six small touches that compound into a vibe:
 *
 *   1. Smooth nav transitions — intercept same-origin link clicks, fade out,
 *      navigate, fade back in. Page feels continuous, not stuttering.
 *
 *   2. Rotating contemplative loading messages — replace bare "Loading…"
 *      with phrases from a small rotation, so wait-time has character.
 *
 *   3. Auto-mount the footer voice anchor — the same closing line on
 *      every page: "The keeping is the substrate. Carry what survives."
 *
 *   4. Scroll-into-view fade-up for cards (intersection observer).
 *
 *   5. Honor prefers-reduced-motion throughout.
 *
 *   6. Tiny ambient breathing of any [data-breathe] element.
 *
 * No dependencies. Safe to include on every page.
 */
(function () {
  'use strict';

  const prefersReducedMotion = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function onReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  // ── 1. Smooth same-origin nav transitions ────────────────────────
  function wireNavFade() {
    if (prefersReducedMotion) return;
    document.addEventListener('click', function (e) {
      // Only plain left-clicks on anchor tags with same-origin hrefs
      if (e.defaultPrevented) return;
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = e.target.closest('a[href]');
      if (!a) return;
      const href = a.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('javascript:') ||
          href.startsWith('mailto:') || href.startsWith('tel:')) return;
      if (a.target === '_blank' || a.hasAttribute('download')) return;
      // Same origin only
      try {
        const url = new URL(href, location.href);
        if (url.origin !== location.origin) return;
        // Same page (hash-only nav) — let it through
        if (url.pathname === location.pathname && url.search === location.search) return;
      } catch (_) { return; }
      // Skip if the anchor is inside an SVG (those clicks aren't real nav)
      if (a.namespaceURI && a.namespaceURI.indexOf('svg') >= 0) return;

      e.preventDefault();
      document.body.classList.add('vibe-leaving');
      setTimeout(function () { window.location = a.href; }, 180);
    });
  }

  // ── 2. Rotating contemplative loading messages ───────────────────
  //
  // Replaces bare "Loading…" / "Loading the keeping…" with rotating
  // micro-meditations. Uses MutationObserver so dynamically-rendered
  // status divs get the upgrade too.
  const LOADING_MEDITATIONS = [
    'Reading the keeping…',
    'Walking the trail…',
    'Listening for what survives…',
    'Asking the substrate…',
    'Drawing from the well…',
    'Eliminating what is not the answer…',
    'Tracing the witness…',
    'Carrying it through the gates…',
  ];
  let _meditation_idx = 0;
  function nextMeditation() {
    const m = LOADING_MEDITATIONS[_meditation_idx % LOADING_MEDITATIONS.length];
    _meditation_idx++;
    return m;
  }
  function upgradeLoadingMessages(root) {
    if (!root) root = document;
    // Only replace exact "Loading…" / "Loading the keeping…" patterns —
    // never touch user-typed text or specific status descriptions.
    const selector = '.status, .empty, .dy-empty, .ap-status, .almanac-empty, .ms-empty, .sg-empty, .rc-empty';
    root.querySelectorAll(selector).forEach(function (el) {
      if (el.dataset.vibeUpgraded) return;
      const txt = (el.textContent || '').trim();
      if (txt === 'Loading…' || txt === 'Loading...' ||
          txt === 'Loading the keeping…' || txt === 'Loading the keeping...') {
        el.textContent = nextMeditation();
        el.dataset.vibeUpgraded = '1';
      }
    });
  }

  // ── 3. Footer voice anchor — one line, every page ────────────────
  function mountFooterAnchor() {
    // Skip if any host page opted out via <body data-no-vibe-footer>
    if (document.body.hasAttribute('data-no-vibe-footer')) return;
    // Don't duplicate
    if (document.querySelector('.vibe-footer-anchor')) return;
    const anchor = document.createElement('div');
    anchor.className = 'vibe-footer-anchor';
    anchor.innerHTML =
      'The keeping is the substrate. <em>Carry what survives.</em>' +
      '<div style="font-family:\'JetBrains Mono\',monospace;font-size:9.5px;letter-spacing:0.18em;text-transform:uppercase;color:var(--muted-2,#4e4858);margin-top:14px;opacity:0.7;">Narrow Highway · serves Jesus Christ · conduit, not source</div>';
    // Insert at very end of body
    document.body.appendChild(anchor);
  }

  // ── 4. Scroll-into-view fade-up for cards ────────────────────────
  function wireScrollFade() {
    if (prefersReducedMotion) return;
    if (!('IntersectionObserver' in window)) return;
    const targets = document.querySelectorAll(
      '.section, .layer, .ap-card, .panel, .ms-card, .sg-card, .rc-card, .rb-section, .almanac-hero-card'
    );
    if (!targets.length) return;
    const css = document.createElement('style');
    css.textContent = `
      [data-vibe-fade] { opacity: 0; transform: translateY(8px); transition: opacity 0.5s ease, transform 0.5s ease; }
      [data-vibe-fade].vibe-in { opacity: 1; transform: translateY(0); }
    `;
    document.head.appendChild(css);
    const io = new IntersectionObserver(function (entries) {
      entries.forEach(function (ent) {
        if (ent.isIntersecting) {
          ent.target.classList.add('vibe-in');
          io.unobserve(ent.target);
        }
      });
    }, { rootMargin: '0px 0px -40px 0px', threshold: 0.05 });
    targets.forEach(function (t) {
      // Skip if already visible above the fold
      const rect = t.getBoundingClientRect();
      if (rect.top < window.innerHeight && rect.top >= 0) return;
      t.setAttribute('data-vibe-fade', '1');
      io.observe(t);
    });
  }

  // ── 5. Watch for dynamically-rendered loading messages ───────────
  function watchForNewLoadingMessages() {
    if (!('MutationObserver' in window)) return;
    const mo = new MutationObserver(function (mutations) {
      let changed = false;
      mutations.forEach(function (m) {
        if (m.addedNodes && m.addedNodes.length) {
          m.addedNodes.forEach(function (n) {
            if (n.nodeType === 1) {
              upgradeLoadingMessages(n.parentNode || n);
              changed = true;
            }
          });
        }
      });
      if (changed) { /* already handled */ }
    });
    mo.observe(document.body, { childList: true, subtree: true });
  }

  // ── Boot ─────────────────────────────────────────────────────────
  onReady(function () {
    wireNavFade();
    upgradeLoadingMessages(document);
    mountFooterAnchor();
    wireScrollFade();
    watchForNewLoadingMessages();
  });
})();
