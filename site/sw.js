// sw.js — minimal service worker for PWA install eligibility.
//
// We don't aggressively cache the engine surfaces (the journal,
// the well, the porch) because data freshness matters more than
// offline-first browsing here. The service worker exists so the
// browser will offer "Add to Home Screen" and so Web Share Target
// works (the OS requires a registered SW for a PWA to receive
// shares).
//
// Per the deployment-modes doctrine: Pyodide (/pyodide.html)
// already provides a fully offline path — that's the substrate
// for restricted/lockdown modes. This SW is for Open mode
// convenience.

const CACHE = 'concordance-shell-v1';
const SHELL = [
  '/',
  '/manifest.json',
  '/favicon.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL))
      .catch(() => {})  // best-effort; don't block install
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

// Network-first for everything; fall back to cache only on failure.
// This keeps the well, porch, and journal fresh while still
// allowing the shell to load when offline.
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
