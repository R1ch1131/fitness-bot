import { useRef, useState } from 'react';
import type { ChatMessage } from '../types';
import { healthHeaders, responseError } from '../healthConnection';

export function EveningReportTest({ onMessage }: { onMessage: (message: ChatMessage) => void }) {
  const requestId = useRef<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const send = async () => {
    if (busy) return;
    requestId.current ??= crypto.randomUUID();
    setBusy(true); setStatus(''); setError('');
    try {
      const response = await fetch('/api/chat/evening/test', { method: 'POST', headers: { 'Content-Type': 'application/json', ...healthHeaders() }, body: JSON.stringify({ request_id: requestId.current }) });
      if (!response.ok) throw await responseError(response);
      const data = await response.json();
      onMessage(data.message);
      setStatus(data.push_accepted ? 'Отчёт в чате. Push принят службой доставки.' : 'Отчёт в чате. Push не подтверждён — проверь подключение уведомлений на телефоне.');
      requestId.current = null;
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  };
  return <div className="shrink-0 mb-1 text-xs">
    <button type="button" disabled={busy} onClick={() => void send()} className="px-3 py-2 rounded-xl border border-[#33473b] text-[#b4cabb] disabled:opacity-50">{busy ? 'Тренер готовит отчёт…' : 'Тестовый отчёт и push'}</button>
    {status && <p role="status" className="mt-1 text-emerald-300">{status}</p>}
    {error && <p role="alert" className="mt-1 text-rose-300">{error}</p>}
  </div>;
}
