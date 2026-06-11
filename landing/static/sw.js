const CACHE = 'kr-tools-v9';
const PRECACHE = [
  '/',
  '/assets/css/styles.css',
  '/assets/js/index.js',
  '/assets/images/kr-logo.png',
  '/gradient-background-dark.svg',
  '/icon-192.png',
  '/icon-512.png',
  '/manifest.json',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET' || !e.request.url.startsWith(self.location.origin)) return;
  e.respondWith(
    caches.match(e.request).then(cached => {
      const fresh = fetch(e.request).then(res => {
        if (res.ok) {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return res;
      }).catch(() => cached);
      return cached || fresh;
    })
  );
});

// ── Push notifications ────────────────────────────────────────────────────────

self.addEventListener('push', e => {
  let data = {};
  try { data = e.data ? e.data.json() : {}; } catch {}

  const title = data.title || 'New Webhook';
  const options = {
    body:     data.body || 'A new request arrived',
    icon:     '/icon-192.png',
    badge:    '/icon-192.png',
    tag:      'webhook-' + Date.now(),
    data:     { path: data.path || '', badge: data.badge || 1 },
  };

  e.waitUntil(
    self.registration.showNotification(title, options)
  );

  if ('setAppBadge' in self.registration) {
    self.registration.setAppBadge(data.badge || 1);
  }
});

// ── Notification click: open/focus the app on the Webhooks panel ─────────────

self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      const existing = list.find(c => c.url.includes('kenleyr.com'));
      if (existing) {
        existing.focus();
        existing.postMessage({ type: 'OPEN_PANEL', panel: 'webhooks' });
      } else {
        clients.openWindow('/?panel=webhooks');
      }
    })
  );
  if ('clearAppBadge' in self.registration) self.registration.clearAppBadge();
});
