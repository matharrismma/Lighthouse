/**
 * a11y.js — Site-wide accessibility upgrades.
 *
 * Auto-runs on every page (no manual setup needed):
 *
 *   1. Skip-to-content link (visually hidden, visible on focus)
 *   2. Focus indicators on all interactive elements
 *   3. Auto-set role="main" if no <main> exists
 *   4. Add alt="" to decorative SVGs (chi-rho marks, dividers)
 *   5. Ensure form inputs have accessible labels
 *   6. Add aria-current="page" to active nav links
 *   7. Improve keyboard nav: Esc closes modals/popovers, / focuses search
 *   8. Announce route changes for screen readers (aria-live region)
 *
 * No external dependencies. Inserts a <style> block + a few DOM patches.
 * Idempotent — safe to load on every page.
 */
(function () {
  'use strict';

  // ── 1. Inject base a11y styles ────────────────────────────────────
  const style = document.createElement('style');
  style.id = 'a11y-base';
  style.textContent = `
    /* Skip link — visible only when focused via keyboard */
    .a11y-skiplink {
      position: absolute;
      left: -9999px;
      top: 0;
      z-index: 9999;
      padding: 10px 16px;
      background: var(--accent, #c9a87c);
      color: #0a0810;
      font-family: 'Inter', system-ui, sans-serif;
      font-weight: 600;
      font-size: 14px;
      border-radius: 0 0 6px 0;
      text-decoration: none;
    }
    .a11y-skiplink:focus {
      left: 0;
      outline: 3px solid #fff;
      outline-offset: 2px;
    }

    /* Visible, consistent focus ring across all interactive elements */
    *:focus-visible {
      outline: 2px solid var(--accent, #c9a87c);
      outline-offset: 2px;
      border-radius: 3px;
    }

    /* Don't show outlines on mouse clicks (only keyboard focus) */
    *:focus:not(:focus-visible) {
      outline: none;
    }

    /* Touch targets — minimum 44x44 per WCAG 2.5.5 (AA) */
    @media (pointer: coarse) {
      a, button, input[type="button"], input[type="submit"], select {
        min-height: 44px;
      }
      /* Compact density still possible inside dense lists */
      .a11y-allow-compact, .a11y-allow-compact * {
        min-height: 0 !important;
      }
    }

    /* Reduce motion respect */
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
      }
    }

    /* Visually hidden but available to screen readers */
    .a11y-sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }

    /* Active nav link affordance */
    nav a[aria-current="page"] {
      color: var(--accent, #c9a87c) !important;
      font-weight: 600;
    }
  `;
  if (!document.getElementById('a11y-base')) {
    document.head.appendChild(style);
  }

  function onReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  onReady(function () {
    // ── 2. Skip link ────────────────────────────────────────────────
    if (!document.querySelector('.a11y-skiplink')) {
      const skip = document.createElement('a');
      skip.href = '#main';
      skip.className = 'a11y-skiplink';
      skip.textContent = (window._i18n && _i18n.t('a11y.skip_to_content', 'Skip to main content'))
        || 'Skip to main content';
      document.body.insertBefore(skip, document.body.firstChild);
    }

    // ── 3. Ensure a #main landmark exists ───────────────────────────
    let main = document.querySelector('main, [role="main"], #main');
    if (!main) {
      // Heuristic: find the most likely main content container
      const candidate = document.querySelector('.container, .wrap, [class*="main"], section');
      if (candidate) {
        candidate.setAttribute('role', 'main');
        if (!candidate.id) candidate.id = 'main';
        main = candidate;
      }
    } else if (!main.id) {
      main.id = 'main';
    }

    // ── 4. Mark decorative SVGs ─────────────────────────────────────
    // Chi-rho marks, dividers, and other inline SVGs with no aria-label
    // should be aria-hidden so screen readers skip them.
    document.querySelectorAll('svg:not([aria-label]):not([aria-labelledby]):not([role="img"])').forEach(svg => {
      if (!svg.hasAttribute('aria-hidden')) {
        svg.setAttribute('aria-hidden', 'true');
      }
    });

    // ── 5. Auto-label nav landmark ──────────────────────────────────
    const topnav = document.querySelector('nav.topnav, nav[class*="nav"]');
    if (topnav && !topnav.hasAttribute('aria-label')) {
      topnav.setAttribute('aria-label',
        (window._i18n && _i18n.t('a11y.primary_nav', 'Primary navigation')) || 'Primary navigation');
    }

    // ── 6. aria-current on active nav link ──────────────────────────
    const currentPath = location.pathname.replace(/\/$/, '') || '/';
    document.querySelectorAll('nav a[href]').forEach(a => {
      try {
        const href = new URL(a.href, location.origin).pathname.replace(/\/$/, '') || '/';
        if (href === currentPath) {
          a.setAttribute('aria-current', 'page');
        }
      } catch (e) { /* invalid href, ignore */ }
    });

    // ── 7. Keyboard shortcuts ───────────────────────────────────────
    // "/" focuses the first search input on the page
    document.addEventListener('keydown', function (e) {
      if (e.key === '/' && !isTyping(e.target)) {
        const search = document.querySelector('input[type="search"], input[name="q"], #heroQuery, [data-search-input]');
        if (search) {
          e.preventDefault();
          search.focus();
        }
      }
      // Escape closes any [data-popover], [data-modal]
      if (e.key === 'Escape') {
        document.querySelectorAll('[data-popover-open], [data-modal-open]').forEach(el => {
          el.removeAttribute('data-popover-open');
          el.removeAttribute('data-modal-open');
          el.style.display = 'none';
        });
      }
    });

    function isTyping(el) {
      if (!el) return false;
      const tag = el.tagName;
      return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
    }

    // ── 8. Live region for status announcements ────────────────────
    if (!document.getElementById('a11y-live')) {
      const live = document.createElement('div');
      live.id = 'a11y-live';
      live.className = 'a11y-sr-only';
      live.setAttribute('aria-live', 'polite');
      live.setAttribute('aria-atomic', 'true');
      document.body.appendChild(live);
    }

    // Expose announcement helper
    window._a11y = {
      announce: function (msg) {
        const live = document.getElementById('a11y-live');
        if (live) {
          live.textContent = '';
          // Slight delay so screen readers pick up the change
          setTimeout(() => { live.textContent = msg; }, 50);
        }
      }
    };

    // ── 9. Register service worker for offline support ────────────
    // Skips localhost dev — the SW caches aggressively and gets in
    // the way of hot reloads. Only registers in production.
    if ('serviceWorker' in navigator
        && location.protocol === 'https:'
        && location.hostname !== 'localhost'
        && location.hostname !== '127.0.0.1') {
      navigator.serviceWorker.register('/sw.js').catch(() => { /* best-effort */ });
    }
  });
})();
