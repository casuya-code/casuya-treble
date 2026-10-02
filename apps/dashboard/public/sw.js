/* Keeps “Add to Home screen” available without intercepting Next.js requests. */
self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/_next/") || url.pathname.startsWith("/api/")) return;
  if (event.request.method !== "GET") return;
});
