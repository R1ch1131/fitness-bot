import { useEffect, useState } from 'react';
import { healthHeaders, responseError } from '../healthConnection';

export function CoachMemory() {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setReady(false);
    setError('');
    setSaved(false);
    void (async () => {
      try {
        const response = await fetch('/api/chat/memory', { headers: healthHeaders(), cache: 'no-store', signal: controller.signal });
        if (!response.ok) throw await responseError(response);
        const data = await response.json();
        if (typeof data.text !== 'string') throw Error('Не удалось прочитать память');
        if (!controller.signal.aborted) { setText(data.text); setReady(true); }
      } catch (err) {
        if (!controller.signal.aborted) setError((err as Error).message);
      }
    })();
    return () => controller.abort();
  }, [open, retry]);
  const save = async () => {
    if (!ready || busy) return;
    setBusy(true); setError(''); setSaved(false);
    try {
      const response = await fetch('/api/chat/memory', { method: 'PUT', headers: { 'Content-Type': 'application/json', ...healthHeaders() }, body: JSON.stringify({ text }) });
      if (!response.ok) throw await responseError(response);
      const data = await response.json();
      setText(data.text); setSaved(true);
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  };
  return <div className="shrink-0 my-1 text-xs">
    <button type="button" aria-expanded={open} aria-controls="coach-memory-editor" disabled={busy} onClick={() => setOpen(value => !value)} className="px-3 py-2 rounded-xl border border-emerald-400/25 text-emerald-200">Память тренера</button>
    {open && <div id="coach-memory-editor" className="mt-2 p-3 rounded-xl border border-[#334155] bg-[#111726] space-y-2">
      <p className="text-[#94a3b8]">Что тренер должен помнить о тебе. Очистка переписки эти сведения не удаляет.</p>
      {!ready && !error && <p role="status">Загружаем память…</p>}
      <textarea aria-label="Постоянная память тренера" maxLength={10000} rows={5} disabled={!ready || busy} value={text} onChange={event => { setText(event.target.value); setSaved(false); }} className="w-full p-3 rounded-xl bg-[#0b0f19] border border-[#334155] text-white resize-y max-h-48" />
      {error && <p role="alert" className="text-rose-300">{error}{!ready && <button type="button" onClick={() => setRetry(value => value + 1)} className="underline ml-2">Повторить</button>}</p>}
      {saved && <p role="status" className="text-emerald-300">Память сохранена</p>}
      <button type="button" disabled={!ready || busy} onClick={() => void save()} className="px-3 py-2 rounded-lg bg-emerald-400 text-[#0b0f19] disabled:opacity-40">{busy ? 'Сохраняем…' : 'Сохранить память'}</button>
      <p className="text-[#94a3b8]">Чтобы удалить память, очисти поле и сохрани.</p>
    </div>}
  </div>;
}
