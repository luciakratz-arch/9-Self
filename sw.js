const CACHE_NAME = '9self-v4';
const ASSETS = [
  './index.html',
  './cadastro.html',
  './instalar-app.html',
  './offline.html',
  './manifest.json',
  './9Self logo.png',
  './9Self logo 512.png',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  if (
    e.request.url.includes('firestore') ||
    e.request.url.includes('firebase') ||
    e.request.url.includes('googleapis') ||
    e.request.url.includes('mercadopago') ||
    e.request.url.includes('run.app') ||
    e.request.url.includes('gstatic')
  ) { return; }

  e.respondWith(
    caches.match(e.request).then(cached => {
      const network = fetch(e.request).then(res => {
        if (res && res.status === 200 && e.request.method === 'GET') {
          const clone = res.clone();
          caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
        }
        return res;
      }).catch(() => {
        if (e.request.mode === 'navigate') return caches.match('./offline.html');
        return cached;
      });
      return cached || network;
    })
  );
});

self.addEventListener('push', e => {
  const data = e.data ? e.data.json() : {};
  const title = data.title || '9&Self';
  const options = {
    body: data.body || 'Você tem uma atualização.',
    icon: './9Self logo.png',
    badge: './9Self logo.png',
    vibrate: [200, 100, 200],
    data: { url: data.url || './index.html' }
  };
  e.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(clients.openWindow(e.notification.data.url || './index.html'));
});
