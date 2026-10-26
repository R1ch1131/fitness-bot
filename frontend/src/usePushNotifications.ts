import { useEffect, useState } from 'react';

function availability(): string | null {
  if (!window.isSecureContext) return 'Для уведомлений откройте сайт по HTTPS.';
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const standalone = window.matchMedia('(display-mode: standalone)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone;
  if (ios && !standalone) return 'На iPhone: Safari → Поделиться → На экран «Домой». Затем откройте приложение с его значка. Нужна iOS 16.4 или новее.';
  if (!('Notification' in window) || !('serviceWorker' in navigator) || !('PushManager' in window))
    return 'Этот браузер не поддерживает Web Push. На iPhone нужна iOS 16.4 или новее и запуск с экрана «Домой».';
  if (Notification.permission === 'denied') return 'Уведомления запрещены. Разрешите их в настройках уведомлений iPhone для FitPulse, затем вернитесь в приложение.';
  return null;
}

async function jsonRequest(path: string, body?: unknown) {
  const response = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(15000),
    cache: 'no-store',
  });
  const data = await response.json();
  if (!response.ok || data.status === 'error') throw new Error(data.detail || 'Сервер не подтвердил операцию с уведомлениями.');
  return data;
}

async function registration() {
  await navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' });
  let timer: ReturnType<typeof setTimeout>;
  try {
    return await Promise.race([
      navigator.serviceWorker.ready,
      new Promise<never>((_, reject) => { timer = setTimeout(() => reject(new Error('Не удалось запустить уведомления. Перезапустите приложение и повторите.')), 15000); }),
    ]);
  } finally { clearTimeout(timer!); }
}

export function usePushNotifications() {
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('Включите уведомления, чтобы получать напоминания при закрытом приложении.');
  const [blocked, setBlocked] = useState(availability);
  const [scheduledTest, setScheduledTest] = useState<number | null>(null);
  const error = (e: unknown) => { setMessage(e instanceof Error ? e.message : 'Не удалось подключить уведомления. Повторите попытку.'); };

  async function subscribe(create: boolean) {
    const reg = await registration();
    const { public_key } = await jsonRequest('/api/notifications/vapid_key');
    if (!public_key) throw new Error('Сервер не настроил ключ уведомлений.');
    const key = Uint8Array.from(atob(public_key.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
    let sub = await reg.pushManager.getSubscription();
    const oldKey = sub?.options.applicationServerKey;
    if (sub && oldKey && Array.from(new Uint8Array(oldKey)).join() !== Array.from(key).join()) {
      setReady(false);
      if (!create) throw new Error('Ключ уведомлений изменился. Нажмите «Включить», чтобы обновить подписку.');
      await sub.unsubscribe();
      sub = null;
    }
    if (!sub && create) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
    if (!sub) { setReady(false); return null; }
    await jsonRequest('/api/notifications/subscribe', sub.toJSON());
    setReady(true);
    return sub;
  }

  useEffect(() => {
    const refresh = () => {
      setBlocked(availability());
      if ('Notification' in window && Notification.permission === 'granted' && !availability()) {
        void subscribe(false).then(sub => {
          if (sub) setMessage('Подписка сохранена. Нажмите «Тест», чтобы проверить получение уведомлений на этом устройстве.');
          if (sub) void jsonRequest('/api/notifications/test_push/status', { endpoint: sub.endpoint })
            .then(data => setScheduledTest(data.pending?.due_at || null)).catch(() => {});
        }).catch(e => { setReady(false); error(e); });
      } else setReady(false);
    };
    refresh();
    window.addEventListener('focus', refresh);
    window.addEventListener('fitpulse:server-ready', refresh);
    return () => {
      window.removeEventListener('focus', refresh);
      window.removeEventListener('fitpulse:server-ready', refresh);
    };
  }, []);

  async function enable() {
    const reason = availability();
    setBlocked(reason);
    if (reason || busy) return;
    setBusy(true);
    setReady(false);
    try {
      // Must be called directly from the tap, before any network/SW await on iOS.
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') { setBlocked(availability()); setMessage('Разрешение на уведомления не получено. Нажмите «Включить», чтобы повторить.'); return; }
      await subscribe(true);
      setMessage('Подписка сохранена. Нажмите «Тест», затем сверните приложение, чтобы проверить уведомление на экране блокировки.');
    } catch (e) { error(e); } finally { setBusy(false); }
  }

  async function test(delaySeconds = 0) {
    if (busy) return;
    setBusy(true);
    try {
      const sub = await subscribe(false);
      if (!sub) throw new Error('Сначала включите уведомления.');
      const result = await jsonRequest('/api/notifications/test_push', { endpoint: sub.endpoint, delay_seconds: delaySeconds });
      if (result.scheduled) {
        setScheduledTest(result.due_at);
        setMessage(`Тест сохранён на сервере: через ${delaySeconds / 60} мин. Закрой приложение и проверь уведомление на экране блокировки.`);
        return;
      }
      setMessage(result.sent === 1 ? 'Push-сервис принял тест. Проверьте уведомление на iPhone; при необходимости проверьте режим «Фокусирование».' : 'Push-сервис не принял тест. Повторно включите уведомления или проверьте сервер.');
      if (result.sent !== 1) setReady(false);
    } catch (e) { error(e); } finally { setBusy(false); }
  }

  async function cancelTest() {
    if (busy) return;
    setBusy(true);
    try {
      const reg = await registration();
      const sub = await reg.pushManager.getSubscription();
      if (!sub) throw new Error('Подписка этого устройства не найдена.');
      await jsonRequest('/api/notifications/test_push/cancel', { endpoint: sub.endpoint });
      setScheduledTest(null);
      setMessage('Отложенный тест отменён.');
    } catch (e) { error(e); } finally { setBusy(false); }
  }

  async function disable() {
    if (busy) return;
    setBusy(true);
    try {
      const reg = await registration();
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        await jsonRequest('/api/notifications/unsubscribe', { endpoint: sub.endpoint });
        if (!await sub.unsubscribe()) throw new Error('Не удалось отключить подписку на устройстве. Повторите попытку.');
      }
      setReady(false);
      setScheduledTest(null);
      setMessage('Уведомления для этого устройства отключены.');
    } catch (e) { error(e); } finally { setBusy(false); }
  }
  return { ready, busy, message, blocked, scheduledTest, enable, test, cancelTest, disable };
}
