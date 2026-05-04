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

const CACHE = 'concordance-shell-v2';

// Pre-cached shell. Everything here loads once at install and is
// available offline thereafter.
const SHELL = [
  '/',
  '/manifest.json',
  '/favicon.svg',
  '/icon-192.svg',
  '/icon-512.svg',
  '/share.html',
  '/offline.html',
  '/llms.txt',
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

  event.respondWith((async () => {
    try {
      const fresh = await fetch(req);
      // Cache shell-shaped resources (HTML, JSON, SVG) silently for
      // offline use. The cache lookup below picks them up later.
      const ct = fresh.headers.get('content-type') || '';
      const cacheable =
        fresh.ok &&
        (ct.includes('text/html') ||
         ct.includes('application/manifest+json') ||
         ct.includes('image/svg') ||
         ct.includes('text/plain'));
      if (cacheable) {
        const copy = fresh.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
      }
      return fresh;
    } catch (_) {
      const cached = await caches.match(req);
      if (cached) return cached;
      // Last resort for navigations: the offline page.
      if (req.mode === 'navigate') {
        const fallback = await caches.match('/offline.html');
        if (fallback) return fallback;
      }
      // Truly nothing — let the browser handle it.
      return Response.error();
    }
  })());
});
