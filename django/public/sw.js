const CACHE_VERSION = 'vdruzya-dj-v20';
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

self.addEventListener('push', (event) => {
    let payload = {
        title: 'ВДрузья',
        body: 'Новое уведомление',
        url: '/notifications',
    };
    if (event.data) {
        try {
            payload = { ...payload, ...event.data.json() };
        } catch {
            payload.body = event.data.text();
        }
    }
    event.waitUntil(
        self.registration.showNotification(payload.title, {
            body: payload.body,
            icon: '/favicon-192x192.png',
            badge: '/favicon-32x32.png',
            tag: payload.type ? `vdruzya-${payload.type}` : 'vdruzya-notification',
            data: { url: payload.url || '/notifications' },
        }),
    );
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    const targetUrl = event.notification.data?.url || '/notifications';
    const absoluteUrl = new URL(targetUrl, self.location.origin).href;
    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
            for (const client of clients) {
                if (client.url.startsWith(self.location.origin) && 'focus' in client) {
                    if ('navigate' in client) {
                        return client.navigate(absoluteUrl).then(() => client.focus());
                    }
                    return client.focus();
                }
            }
            if (self.clients.openWindow) {
                return self.clients.openWindow(absoluteUrl);
            }
        }),
    );
});
