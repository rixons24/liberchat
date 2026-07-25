// LiberChat service worker — app-shell caching only.
//
// IMPORTANT: this intentionally does NOT cache anything from /api/*,
// message content, or media responses. Caching those would directly
// undermine the view-once/disappearing-media model (a cached copy is
// a copy that didn't actually disappear). Only the static shell
// (HTML/CSS/JS/icons/manifest) is cached, purely so the app installs
// and its chrome loads instantly — not for offline messaging.

const CACHE_NAME = "liberchat-shell-v1";
const SHELL_ASSETS = [
  "./index.html",
  "./manifest.json",
  "./icon-192.png",
  "./icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
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

  // Never intercept API calls, media, or anything not part of the static shell.
  if (url.pathname.startsWith("/api/")) return;
  if (!SHELL_ASSETS.some((asset) => url.pathname.endsWith(asset.replace("./", "")))) return;

  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
