/**
 * i18n.js — Site-wide translation layer.
 *
 * Include this on any page:  <script src="/i18n.js"></script>
 *
 * Detection priority:
 *   1. ?lang=xx in the URL (always wins)
 *   2. localStorage 'lang' (persists across pages)
 *   3. navigator.language (browser/OS setting)
 *   4. 'en' (floor)
 *
 * Public API:
 *   window._i18n.lang          — current language code
 *   window._i18n.t(key, fb)    — look up translated string (fallback = fb or English)
 *   window._i18n.langParam()   — returns '&lang=xx' or '' for appending to API URLs
 *   window._i18n.addLang(url)  — returns url with lang parameter added
 *   window._i18n.ready         — Promise that resolves when strings are loaded
 */
(function () {
  'use strict';

  // ── Language detection ────────────────────────────────────────────
  const params = new URLSearchParams(window.location.search);
  const urlLang = params.get('lang');
  const storedLang = localStorage.getItem('lang');
  const browserLang = (navigator.language || 'en').split('-')[0].toLowerCase();

  // Priority: URL > stored > browser > en
  const lang = urlLang || storedLang || browserLang || 'en';

  // Persist so other pages without ?lang= still use the same language
  if (lang !== 'en') {
    localStorage.setItem('lang', lang);
  } else {
    localStorage.removeItem('lang');
  }

  // Set <html lang="xx"> for accessibility / CSS :lang() selectors
  document.documentElement.lang = lang;

  // ── String store ──────────────────────────────────────────────────
  let _strings = {};   // key → translated text
  let _ready = false;
  let _readyResolve;
  const readyPromise = new Promise(resolve => { _readyResolve = resolve; });

  function t(key, fallback) {
    return _strings[key] || fallback || key;
  }

  function langParam() {
    return lang !== 'en' ? '&lang=' + encodeURIComponent(lang) : '';
  }

  function addLang(url) {
    if (lang === 'en') return url;
    const sep = url.includes('?') ? '&' : '?';
    return url + sep + 'lang=' + encodeURIComponent(lang);
  }

  // ── Fetch strings ─────────────────────────────────────────────────
  async function loadStrings() {
    if (lang === 'en') {
      _ready = true;
      _readyResolve();
      return;
    }

    // Check sessionStorage cache first (avoids re-fetch on every page nav)
    const cacheKey = '_i18n_' + lang;
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) {
      try {
        _strings = JSON.parse(cached);
        _ready = true;
        _readyResolve();
        applyTranslations();
        return;
      } catch (e) { /* fall through */ }
    }

    try {
      const resp = await fetch('/i18n/strings?lang=' + encodeURIComponent(lang));
      if (!resp.ok) throw new Error(resp.status);
      const data = await resp.json();
      _strings = data.strings || {};
      sessionStorage.setItem(cacheKey, JSON.stringify(_strings));
    } catch (e) {
      console.warn('[i18n] Failed to load strings for', lang, e);
      _strings = {};
    }
    _ready = true;
    _readyResolve();
    applyTranslations();
  }

  // ── Apply translations to DOM ─────────────────────────────────────
  function applyTranslations() {
    if (lang === 'en') return;

    // Replace text content of elements with data-i18n="key"
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      const translated = _strings[key];
      if (translated) {
        el.textContent = translated;
      }
    });

    // Replace placeholders with data-i18n-placeholder="key"
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      const translated = _strings[key];
      if (translated) {
        el.placeholder = translated;
      }
    });

    // Replace title attributes with data-i18n-title="key"
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      const key = el.getAttribute('data-i18n-title');
      const translated = _strings[key];
      if (translated) {
        el.title = translated;
      }
    });

    // Update page title if data-i18n-page-title is set on <html>
    const pageTitleKey = document.documentElement.getAttribute('data-i18n-page-title');
    if (pageTitleKey && _strings[pageTitleKey]) {
      document.title = _strings[pageTitleKey];
    }
  }

  // ── Language selector widget ──────────────────────────────────────
  const LANG_NAMES = {
    en: 'English', es: 'Español', fr: 'Français', pt: 'Português',
    de: 'Deutsch', it: 'Italiano', nl: 'Nederlands', ro: 'Română',
    ru: 'Русский', uk: 'Українська', ar: 'العربية', fa: 'فارسی',
    he: 'עברית', hi: 'हिन्दी', sw: 'Kiswahili', zh: '中文',
    ja: '日本語', ko: '한국어', vi: 'Tiếng Việt', my: 'မြန်မာ',
    ht: 'Kreyòl', la: 'Latina'
  };

  function createLangSelector(container) {
    if (!container) return;
    const select = document.createElement('select');
    select.style.cssText = 'background:var(--surface,#161320);color:var(--text-dim,#b3aabd);border:1px solid var(--border,#29232f);border-radius:6px;padding:5px 8px;font-family:inherit;font-size:12px;cursor:pointer;';
    select.title = 'Language';
    select.setAttribute('aria-label', 'Language');

    // Auto-detect option
    const autoOpt = document.createElement('option');
    autoOpt.value = '';
    autoOpt.textContent = '🌐 Auto';
    if (!urlLang && !storedLang) autoOpt.selected = true;
    select.appendChild(autoOpt);

    // Language options
    Object.entries(LANG_NAMES).forEach(([code, name]) => {
      const opt = document.createElement('option');
      opt.value = code;
      opt.textContent = name;
      if (code === lang) opt.selected = true;
      select.appendChild(opt);
    });

    select.addEventListener('change', () => {
      const chosen = select.value;
      if (chosen) {
        localStorage.setItem('lang', chosen);
      } else {
        localStorage.removeItem('lang');
      }
      // Reload with the new language in the URL
      const url = new URL(window.location);
      if (chosen && chosen !== 'en') {
        url.searchParams.set('lang', chosen);
      } else {
        url.searchParams.delete('lang');
      }
      window.location = url.toString();
    });

    container.appendChild(select);
  }

  // ── Expose public API ─────────────────────────────────────────────
  window._i18n = {
    lang: lang,
    t: t,
    langParam: langParam,
    addLang: addLang,
    ready: readyPromise,
    applyTranslations: applyTranslations,
    createLangSelector: createLangSelector,
    LANG_NAMES: LANG_NAMES,
  };

  // ── Auto-mount language selector ──────────────────────────────────
  // Look for an explicit mount point (id="langSelect"), then fall back
  // to inserting into any nav.topnav element. Pages that don't have
  // either still get silent language detection + persistence.
  function autoMountSelector() {
    let host = document.getElementById('langSelect');
    if (!host) {
      // Look for a nav container — try .navlinks first (index.html style),
      // then nav.topnav directly (scribe.html etc. style), then any <nav>.
      const navContainer =
        document.querySelector('nav.topnav .navlinks') ||
        document.querySelector('nav .navlinks') ||
        document.querySelector('nav.topnav') ||
        document.querySelector('nav');
      if (navContainer) {
        host = document.createElement('span');
        host.id = 'langSelect';
        host.style.cssText = 'display:inline-flex;align-items:center;margin-left:8px;';
        // Insert before any .cta link (e.g. "Connect →"), else append
        const anchor = navContainer.querySelector('.cta, .always');
        if (anchor) navContainer.insertBefore(host, anchor);
        else navContainer.appendChild(host);
      }
    }
    if (host && host.children.length === 0) {
      createLangSelector(host);
    }
  }

  // Run selector mount once DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', autoMountSelector);
  } else {
    autoMountSelector();
  }

  // RTL support — set dir="rtl" on document for Arabic/Hebrew/Persian
  if (['ar', 'he', 'fa'].includes(lang)) {
    document.documentElement.dir = 'rtl';
  }

  // ── Boot ──────────────────────────────────────────────────────────
  loadStrings();
})();
