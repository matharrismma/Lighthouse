/**
 * welcome.js — First-visit onboarding card.
 *
 * On a visitor's first ever visit (no localStorage flag), shows a small,
 * dismissable card with:
 *   1. One-line greeting + plain-language explanation
 *   2. Language hint if browser language isn't English ("Read in español?")
 *   3. Three doors: walk a situation / look up / teach a child
 *   4. "Got it" dismiss → sets visited flag so this never shows again
 *
 * Idempotent. Auto-runs on homepage only (other pages have their own context).
 */
(function () {
  'use strict';

  // Only show on homepage
  if (location.pathname !== '/' && location.pathname !== '/index.html') return;

  // Already greeted this session?
  try {
    if (sessionStorage.getItem('cnd_greeted')) return;
  } catch (e) {}

  // Determine first-visit vs returning-visit
  let firstVisitMs = 0;
  let lastVisitMs = 0;
  try {
    firstVisitMs = parseInt(localStorage.getItem('cnd_visited') || '0', 10) || 0;
    lastVisitMs = parseInt(localStorage.getItem('cnd_last_visit') || '0', 10) || 0;
  } catch (e) {}

  const isReturning = firstVisitMs > 0;
  const handle = (function () {
    try { return localStorage.getItem('hearth_handle') || ''; } catch (_) { return ''; }
  })();

  // Update last-visit stamp now
  try { localStorage.setItem('cnd_last_visit', String(Date.now())); } catch (e) {}
  // Mark greeted for this session so it doesn't re-show on every nav
  try { sessionStorage.setItem('cnd_greeted', '1'); } catch (e) {}

  // Detect browser language for language hint
  const browserLang = (navigator.language || 'en').split('-')[0].toLowerCase();
  const knownLangs = { es:'Español', fr:'Français', pt:'Português', de:'Deutsch',
                       zh:'中文', ar:'العربية', ja:'日本語', ko:'한국어', ru:'Русский',
                       hi:'हिन्दी', it:'Italiano', nl:'Nederlands', sw:'Kiswahili',
                       vi:'Tiếng Việt', fa:'فارسی', he:'עברית', uk:'Українська',
                       ro:'Română', ht:'Kreyòl', my:'မြန်မာ' };
  const langHint = (browserLang !== 'en' && knownLangs[browserLang])
    ? { code: browserLang, name: knownLangs[browserLang] } : null;

  function onReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  onReady(function () {
    // Build the card
    const card = document.createElement('div');
    card.id = 'welcome-card';
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-modal', 'false');
    card.setAttribute('aria-labelledby', 'welcome-title');
    card.style.cssText = `
      position: fixed;
      left: 50%;
      bottom: 24px;
      transform: translateX(-50%);
      max-width: 480px;
      width: calc(100vw - 32px);
      z-index: 1000;
      background: var(--surface, #161320);
      color: var(--text, #ede7db);
      border: 1px solid var(--accent, #c9a87c);
      border-radius: 12px;
      box-shadow: 0 12px 40px rgba(0,0,0,0.6);
      padding: 18px 22px 16px;
      font-family: 'Inter', system-ui, sans-serif;
      animation: welcomeIn 0.3s ease-out;
    `;

    const styleTag = document.createElement('style');
    styleTag.textContent = `
      @keyframes welcomeIn {
        from { opacity: 0; transform: translateX(-50%) translateY(20px); }
        to   { opacity: 1; transform: translateX(-50%) translateY(0); }
      }
      @keyframes welcomeOut {
        from { opacity: 1; transform: translateX(-50%) translateY(0); }
        to   { opacity: 0; transform: translateX(-50%) translateY(20px); }
      }
      #welcome-card .wc-eyebrow {
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--accent, #c9a87c);
        margin-bottom: 6px;
      }
      #welcome-card .wc-title {
        font-family: 'Crimson Pro', Georgia, serif;
        font-size: 19px;
        line-height: 1.3;
        margin: 0 0 8px;
        color: var(--text, #ede7db);
      }
      #welcome-card .wc-body {
        font-size: 14px;
        line-height: 1.55;
        color: var(--text-dim, #b3aabd);
        margin: 0 0 14px;
      }
      #welcome-card .wc-lang {
        display: inline-block;
        background: rgba(201,168,124,0.12);
        border: 1px solid var(--accent, #c9a87c);
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 13px;
        color: var(--accent, #c9a87c);
        text-decoration: none;
        margin-bottom: 12px;
      }
      #welcome-card .wc-lang:hover {
        background: rgba(201,168,124,0.22);
      }
      #welcome-card .wc-actions {
        display: flex;
        gap: 10px;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
      }
      #welcome-card .wc-ok {
        background: var(--accent, #c9a87c);
        color: #1a1208;
        border: none;
        border-radius: 6px;
        padding: 8px 18px;
        font-family: inherit;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        transition: background 0.15s;
      }
      #welcome-card .wc-ok:hover { background: var(--accent-hi, #e3c498); }
      #welcome-card .wc-close {
        background: transparent;
        color: var(--muted, #6e6878);
        border: none;
        font-size: 20px;
        line-height: 1;
        cursor: pointer;
        padding: 4px 8px;
        position: absolute;
        top: 8px;
        right: 8px;
      }
      #welcome-card .wc-close:hover { color: var(--text, #ede7db); }
      #welcome-card .wc-doors {
        font-size: 12.5px;
        color: var(--muted, #6e6878);
        margin: 0 0 14px;
      }
      #welcome-card .wc-doors strong { color: var(--accent, #c9a87c); font-weight: 500; }
    `;
    document.head.appendChild(styleTag);

    const langHintHtml = langHint ? `
      <a href="?lang=${langHint.code}" class="wc-lang" aria-label="Read in ${langHint.name}">
        🌐 Read in ${langHint.name} →
      </a>
    ` : '';

    // Compose greeting that varies by first-visit vs returning
    let eyebrow, title, body, doors, ok;

    if (!isReturning) {
      // First visit
      eyebrow = 'First visit · welcome';
      title   = 'Concordance — verified wisdom across many lenses.';
      body    = 'A free, Christ-anchored knowledge engine. Verifies claims across 63 domains. No AI opinions. No accounts. No tracking.';
      doors   = 'Three doors below: <strong>walk</strong> a situation · <strong>look up</strong> anything · <strong>teach</strong> a child.';
      ok      = 'Got it →';
    } else {
      // Returning visitor
      const sinceLast = lastVisitMs ? Date.now() - lastVisitMs : 0;
      let agoText = '';
      if (sinceLast > 0) {
        const d = sinceLast / 86400000;
        if (d < 1)     agoText = 'just a few hours ago';
        else if (d < 2) agoText = 'yesterday';
        else if (d < 14) agoText = Math.floor(d) + ' days ago';
        else if (d < 60) agoText = Math.floor(d / 7) + ' weeks ago';
        else            agoText = Math.floor(d / 30) + ' months ago';
      }
      eyebrow = 'Welcome back';
      title   = handle
        ? 'Good to see you, <em style="color:var(--accent,#c9a87c);font-style:italic;">' + handle.replace(/[<>&"]/g, '') + '</em>.'
        : 'Good to see you again.';
      body    = (agoText ? 'Last here ' + agoText + '. ' : '')
        + 'The keeping kept going. New seeds may have planted themselves while you were out.';
      doors   = 'Pick up where you left off — or step into <strong>the Hearth</strong> · <a href="/hearth.html" style="color:var(--accent,#c9a87c);">someone may be there now →</a>';
      ok      = 'Settle in →';
    }

    card.innerHTML = `
      <button class="wc-close" aria-label="Close welcome" type="button">×</button>
      <div class="wc-eyebrow">${eyebrow}</div>
      <h2 class="wc-title" id="welcome-title">${title}</h2>
      <p class="wc-body">${body}</p>
      ${langHintHtml}
      <p class="wc-doors">${doors}</p>
      <div class="wc-actions">
        <span style="font-size:11px;color:var(--muted,#6e6878);font-family:'JetBrains Mono',monospace;letter-spacing:0.06em;">
          The keeping is open.
        </span>
        <button class="wc-ok" type="button">${ok}</button>
      </div>
    `;
    document.body.appendChild(card);

    function dismiss() {
      card.style.animation = 'welcomeOut 0.2s ease-in';
      setTimeout(() => card.remove(), 200);
      try {
        // Preserve original first-visit timestamp on return visits
        if (!localStorage.getItem('cnd_visited')) {
          localStorage.setItem('cnd_visited', String(Date.now()));
        }
      } catch (e) {}
      if (window._a11y && window._a11y.announce) {
        window._a11y.announce('Welcome dismissed');
      }
    }

    card.querySelector('.wc-ok').addEventListener('click', dismiss);
    card.querySelector('.wc-close').addEventListener('click', dismiss);

    // Esc key closes it
    function onEsc(e) {
      if (e.key === 'Escape') {
        dismiss();
        document.removeEventListener('keydown', onEsc);
      }
    }
    document.addEventListener('keydown', onEsc);

    // Auto-dismiss after 30 seconds of no interaction
    setTimeout(() => {
      if (document.getElementById('welcome-card')) dismiss();
    }, 30000);
  });
})();
