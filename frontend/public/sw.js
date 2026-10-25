// Web Push must always display a notification, including empty/malformed payloads.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
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
