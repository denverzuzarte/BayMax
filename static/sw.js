// BayMax Service Worker — caches app shell for offline access
const CACHE = "baymax-v1";
const SHELL = ["/", "/static/manifest.json"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener("fetch", e => {
  // Network-first for API calls — always want fresh data
  if (e.request.url.includes("/api/")) return;
  // Cache-first for static shell
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});
