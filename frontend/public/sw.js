// Web Push must always display a notification, including empty/malformed payloads.
const SHELL_CACHE = 'fitpulse-shell-' + "__BUILD_VERSION__";
const SHELL_HTML = "__BUILD_HTML__";
const BUILD_ASSETS = ["__BUILD_ASSETS__"];
const SHELL_KEY = '/__fitpulse_shell__';

self.addEventListener('install', event => {
  // public/sw.js is only a template; development must never install placeholders.
  if (!SHELL_HTML.startsWith('<!doctype html>')) return;
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL_CACHE);
    try {
      for (const path of BUILD_ASSETS) {
        const response = await fetch(new Request(path, { cache: 'reload' }));
        if (!response.ok) throw new Error('App asset unavailable');
        const type = response.headers.get('Content-Type') || '';
        if (type.includes('text/html') || (path.endsWith('.png') && !type.startsWith('image/')) ||
            (path.endsWith('.json') && !type.includes('json')))
          throw new Error('Render wake-up page is not an app asset');
        await cache.put(path, response);
      }
      await cache.put(SHELL_KEY, new Response(SHELL_HTML, { headers: { 'Content-Type': 'text/html; charset=utf-8' } }));
      await self.skipWaiting();
    } catch (error) {
      await caches.delete(SHELL_CACHE);
      throw error; // Leave the previous working service worker active.
    }
  })());
});

self.addEventListener('activate', event => event.waitUntil((async () => {
  const versions = (await caches.keys()).filter(key => key.startsWith('fitpulse-shell-'));
  // Retain the previous build for tabs still referencing its hashed assets.
  for (const key of versions.filter(key => key !== SHELL_CACHE).slice(0, -1)) await caches.delete(key);
  await self.clients.claim();
})()));

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  // API responses and mutations always reach the server, never Cache Storage.
  if (url.pathname.startsWith('/api/') || url.pathname === '/health') return;
  if (request.mode === 'navigate' && url.pathname === '/') {
    event.respondWith((async () => {
      const cached = await (await caches.open(SHELL_CACHE)).match(SHELL_KEY);
      return cached || fetch(request);
    })());
    return;
  }
  if (url.pathname.startsWith('/assets/') || BUILD_ASSETS.includes(url.pathname)) {
    event.respondWith((async () => (await caches.match(request, { ignoreSearch: true })) || fetch(request))());
  }
});
self.addEventListener('push', event => {
  let payload = {};
  try { payload = event.data?.json() || {}; }
  catch { payload = { body: event.data?.text() }; }
  if (!payload || typeof payload !== 'object') payload = {};
  event.waitUntil(self.registration.showNotification(payload.title || 'FitPulse', {
    body: payload.body || 'Откройте приложение, чтобы посмотреть напоминание.',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    tag: payload.tag || 'fitpulse',
    data: payload.data || { url: '/' },
  }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  let target = new URL('/', self.location.origin);
  try {
    const requested = new URL(event.notification.data?.url || '/', self.location.origin);
    if (requested.origin === self.location.origin) target = requested;
  } catch { /* Use the app home for invalid URLs. */ }
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const client of windows) {
      if (new URL(client.url).origin === self.location.origin && 'navigate' in client) {
        const navigated = await client.navigate(target.href);
        if (navigated) return navigated.focus();
      }
    }
    return self.clients.openWindow(target.href);
  })());
});
