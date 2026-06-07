// sw.js — service worker for PWA install + offline shell.
//
// Two responsibilities:
//   1. Pre-cache the shell (HTML, manifest, icons) so the page
//      loads when the network is gone or hostile.
//   2. Network-first for everything else, with cache fallback,
//      and an offline.html fallback for navigations that have
//      neither network nor cache.
//
// We don't cache the engine surfaces (/journal, /capture, /ledger,
// etc.) — those are dynamic and freshness matters more than
// offline browsing. The Pyodide path (/pyodide.html) provides a
// fully offline-capable engine; this SW is for the live-server
// case where the user is online most of the time but the app
// shell should survive a momentary outage.
//
// Per the kingdom-economy substrate / deployment-modes doctrine:
// works for someone whose network is intermittently hostile, not
// just for the always-online happy path.

// v6: page navigations are now network-first with ONLY offline.html as the
// offline fallback (never a stale cached page), and HTML is no longer runtime-
// cached — so new and updated pages always show when online. The version bump
// purges any HTML that older versions cached.
const CACHE = 'concordance-shell-v6';

// Pre-cached shell. Everything here loads once at install and is
// available offline thereafter. The shared JS/CSS files are the
// real win — even when offline, every navigated-to page gets its
// translations + accessibility + mobile styling from cache.
const SHELL = [
  '/',
  '/manifest.json',
  '/favicon.svg',
  '/icon-192.svg',
  '/icon-512.svg',
  '/share.html',
  '/offline.html',
  '/nfc.html',
  '/reach.html',
  '/setup.html',
  '/llms.txt',
  // Shared JS — used by every page
  '/i18n.js',
  '/a11y.js',
  '/welcome.js',
  '/audio.js',
  '/vibe.js',
  // Shared CSS
  '/styles.css',
  '/mobile.css',
  '/lens-polish.css',
  '/vibe.css',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll(SHELL))
      .catch(() => {})  // best-effort; don't block install on a single 404
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Network-first strategy:
//   1. Try the network. If it succeeds, optionally cache the response
//      (only for shell paths) and return it.
//   2. If the network fails, return whatever's in the cache.
//   3. If nothing's in the cache and the request was a navigation,
//      return /offline.html so the user sees something graceful
//      rather than the browser's default error page.
self.addEventListener('fetch', (event) => {
  const req = event.request;

  // Don't intercept non-GET (POST to /capture etc. must hit the
  // origin to actually plant a seed). Also don't intercept
  // cross-origin requests — let the browser handle them.
  if (req.method !== 'GET') return;
  if (new URL(req.url).origin !== self.location.origin) return;

  // Page navigations: ALWAYS network-first, and on failure fall back ONLY to
  // the offline page — never a stale cached copy of the page. This guarantees
  // new and updated pages always show when online. (Pages are not cached here.)
  if (req.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        return await fetch(req);
      } catch (_) {
        return (await caches.match('/offline.html')) || Response.error();
      }
    })());
    return;
  }

  // Static assets (CSS / JS / SVG / manifest / text): network-first with a
  // cache fallback, and cache fresh copies for offline + speed. HTML is
  // intentionally NOT runtime-cached, so a page is never served stale.
  event.respondWith((async () => {
    try {
      const fresh = await fetch(req);
      const ct = fresh.headers.get('content-type') || '';
      const cacheable =
        fresh.ok &&
        (ct.includes('application/manifest+json') ||
         ct.includes('image/svg') ||
         ct.includes('text/plain') ||
         ct.includes('text/css') ||
         ct.includes('javascript'));
      if (cacheable) {
        const copy = fresh.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
      }
      return fresh;
    } catch (_) {
      const cached = await caches.match(req);
      return cached || Response.error();
    }
  })());
});
