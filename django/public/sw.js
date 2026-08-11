const CACHE_VERSION = 'vdruzya-dj-v21';
const PRECACHE_URLS = [
    '/offline.html',
    '/favicon.svg',
    '/favicon-192x192.png',
    '/favicon-512x512.png',
    '/site.webmanifest',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_VERSION)
            .then((cache) => Promise.allSettled(PRECACHE_URLS.map((url) => cache.add(url))))
            .then(() => self.skipWaiting()),
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys.filter((key) => key !== CACHE_VERSION).map((key) => caches.delete(key)),
            ),
        ).then(() => self.clients.claim()),
    );
});

self.addEventListener('fetch', (event) => {
    const { request } = event;
    if (request.method !== 'GET') return;

    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return;

    // Never cache HTML navigations (ETag alone can leave stale group/wall UI)
    if (request.mode === 'navigate' || (request.headers.get('accept') || '').includes('text/html')) {
        event.respondWith(
            fetch(request, { cache: 'no-store' }).catch(() =>
                caches.match(request).then((cached) => cached || caches.match('/offline.html')),
            ),
        );
        return;
    }

    // Static assets: stale-while-revalidate
    if (url.pathname.startsWith('/static/') || url.pathname.match(/\.(css|js|png|svg|ico|woff2?)$/)) {
        event.respondWith(
            caches.open(CACHE_VERSION).then((cache) =>
                cache.match(request).then((cached) => {
                    const network = fetch(request).then((response) => {
                        if (response.ok) cache.put(request, response.clone());
                        return response;
                    }).catch(() => cached);
                    return cached || network;
                }),
            ),
        );
    }
});
