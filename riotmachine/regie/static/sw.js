/* Service worker de la régie : il permet l'installation en application.
   Aucune donnée n'est mise en cache : la régie montre toujours l'état réel du studio.
   Seule la coquille (page, styles, script, icônes) est gardée pour s'ouvrir vite ; le réseau passe d'abord. */
const SHELL = "riot-shell-v1";
self.addEventListener("install", (e) => { self.skipWaiting(); });
self.addEventListener("activate", (e) => { e.waitUntil(self.clients.claim()); });
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/") || url.pathname.startsWith("/media/")) return;
  e.respondWith(fetch(e.request).then((r) => {
    if (r.ok && (url.pathname === "/" || url.pathname.startsWith("/static/"))) {
      const copy = r.clone(); caches.open(SHELL).then((c) => c.put(e.request, copy));
    }
    return r;
  }).catch(() => caches.match(e.request)));
});
