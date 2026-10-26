import { useEffect, useState } from 'react';

export function useServerConnection() {
  const [status, setStatus] = useState<'checking' | 'ready' | 'waking' | 'offline'>('checking');
  useEffect(() => {
    let stopped = false;
    let waiting = false;
    let inFlight = false;
    let timer: ReturnType<typeof setTimeout>;
    let request: AbortController | undefined;
    const probe = async () => {
      if (stopped || inFlight) return;
      clearTimeout(timer);
      if (document.visibilityState !== 'visible') return;
      if (!navigator.onLine) {
        waiting = true;
        setStatus('offline');
        timer = setTimeout(probe, 5000);
        return;
      }
      inFlight = true;
      request = new AbortController();
      const timeout = setTimeout(() => request?.abort(), 8000);
      try {
        const response = await fetch('/health', { cache: 'no-store', signal: request.signal });
        if (!response.ok || !(response.headers.get('Content-Type') || '').includes('application/json')) throw Error('Server waking');
        const health = await response.json();
        if (health.status !== 'ok' || !health.app) throw Error('Server not ready');
        if (stopped) return;
        setStatus('ready');
        if (waiting) window.dispatchEvent(new Event('fitpulse:server-ready'));
        waiting = false;
        const registration = await navigator.serviceWorker?.getRegistration();
        if (registration) void registration.update().catch(() => {});
      } catch {
        if (!stopped) {
          waiting = true;
          setStatus(navigator.onLine ? 'waking' : 'offline');
          timer = setTimeout(probe, 3000);
        }
      } finally {
        clearTimeout(timeout);
        inFlight = false;
      }
    };
    const resume = () => {
      if (!navigator.onLine) {
        waiting = true;
        setStatus('offline');
        request?.abort();
      } else if (document.visibilityState === 'visible') void probe();
    };
    void probe();
    window.addEventListener('online', resume);
    window.addEventListener('offline', resume);
    document.addEventListener('visibilitychange', resume);
    return () => {
      stopped = true;
      clearTimeout(timer);
      request?.abort();
      window.removeEventListener('online', resume);
      window.removeEventListener('offline', resume);
      document.removeEventListener('visibilitychange', resume);
    };
  }, []);
  return status;
}
