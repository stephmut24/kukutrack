const CACHE_NAME = "kukutrack-shell-v9";
const SHELL_FILES = [
  "/", "/lots", "/index.html", "/batch.html", "/journal.html", "/style.css", "/manifest.webmanifest", "/icon.svg",
  "/js/shared.js", "/js/welcome.js", "/js/home.js", "/js/dashboard.js", "/js/journal.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) => Promise.all(
      names.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name)),
    )).then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  if (new URL(event.request.url).pathname.startsWith("/api/")) return;
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request)),
  );
});
