/* =========================================================================
   RoadWatch — service worker
   Caches the app shell (HTML/CSS/JS/icons + the CDN libraries) so the app
   installs as a PWA and opens instantly on repeat visits. API calls
   (/predict, /complaints, /insights, ...) are always network-first — this
   is a live municipal dashboard, not something to serve stale from cache.
   ========================================================================= */

const CACHE_NAME = "roadwatch-shell-v1";
const APP_SHELL = [
  "./",
  "./index.html",
  "./style.css",
  "./script.js",
  "./auth.js",
  "./citizen.js",
  "./admin.js",
  "./manifest.json",
  "./icon.svg",
  "./icon-192.png",
  "./icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  const isAppShell = url.origin === self.location.origin && APP_SHELL.some((p) => url.pathname.endsWith(p.replace("./", "/")));

  if (event.request.method !== "GET") return; // never intercept POST/PATCH/DELETE (predict, status changes, etc.)

  if (isAppShell) {
    // Cache-first for the shell itself, so the app opens even offline.
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
    return;
  }

  // Everything else (API calls, uploaded images, map tiles) — network first,
  // falling back to cache only if the network is genuinely unreachable.
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
