// Web Push must always display a notification, including empty/malformed payloads.
const SHELL_CACHE = 'fitpulse-shell-' + "9b270c1b62d0fbe6";
const SHELL_HTML = "<!doctype html>\n<html lang=\"ru\">\n  <head>\n    <meta charset=\"UTF-8\" />\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover\" />\n\n    <!-- PWA & iOS Meta Tags -->\n    <title>AI Coach</title>\n    <meta name=\"apple-mobile-web-app-title\" content=\"AI Coach\" />\n    <meta name=\"apple-mobile-web-app-capable\" content=\"yes\" />\n    <meta name=\"apple-mobile-web-app-status-bar-style\" content=\"black-translucent\" />\n    <meta name=\"theme-color\" content=\"#09090b\" />\n    <meta name=\"description\" content=\"Персональный фитнес-тренер и трекер калорий Hevy & YAZIO\" />\n\n    <!-- Apple Touch Icon -->\n    <link rel=\"apple-touch-icon\" href=\"/apple-touch-icon.png\" />\n    <link rel=\"icon\" type=\"image/png\" href=\"/icon-192.png\" />\n    <link rel=\"manifest\" href=\"/manifest.json\" />\n    <script type=\"module\" crossorigin src=\"/assets/index-Di7lpZKs.js\"></script>\n    <link rel=\"stylesheet\" crossorigin href=\"/assets/index-BigXb28N.css\">\n  </head>\n  <body class=\"bg-zinc-950 text-zinc-100 select-none\">\n    <div id=\"root\"></div>\n  </body>\n</html>\n";
const BUILD_ASSETS = ["/assets/index-BigXb28N.css","/assets/index-Di7lpZKs.js","/icon-192.png","/icon-512.png","/apple-touch-icon.png","/manifest.json"];
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
