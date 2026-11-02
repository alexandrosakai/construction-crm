// Service Worker para funcionamento offline
const CACHE_NAME = 'exemplo-cache-v1';

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll([
        '/',
        '/css/styles.css',
        '/js/script.js',
        '/images/PLACEHOLDER-LOGO.png',
        '/manifest.json'
      ]);
    })
  );
});

// Estratégia offline-first
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request).then((response) => {
        return caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, response.clone());
          return response;
        });
      });
    })
  );
}); 