// Service Worker for FitPulse AI Coach PWA Push Notifications
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

// Real background Web Push event handler (works even when app is closed on iPhone)
self.addEventListener('push', (event) => {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = { body: event.data.text() };
    }
  }

  const title = data.title || 'Ну чё, как тренировка? 💪';
  const options = {
    body: data.body || 'Прошло 20 минут после тренировки. Самое время зафиксировать ощущения!',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    data: data.data || { url: '/?tab=chat' },
    vibrate: [200, 100, 200],
    tag: 'workout-checkin',
    renotify: true,
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// Click on lock screen notification
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const urlToOpen = event.notification.data?.url || '/?tab=chat';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ('focus' in client) {
          if (client.url.includes(self.location.origin)) {
            client.postMessage({ type: 'OPEN_CHAT_CHECKIN' });
            return client.focus();
          }
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});
