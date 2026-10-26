import { useEffect, useState } from 'react';
import { healthHeaders, saveHealthKey, responseError } from '../healthConnection';

type Night = { date: string; sleep_minutes: number | null; core_minutes: number; deep_minutes: number; rem_minutes: number; asleep_minutes: number; awake_minutes: number };
type Sleep = { nights: Night[]; tracked_nights: number; average_minutes: number | null; imported_at: string | null };
export const duration = (minutes: number | null) => minutes === null ? 'Нет данных' : `${Math.floor(Math.round(minutes) / 60)} ч ${Math.round(minutes) % 60} мин`;

export function SleepCard({ weekStart, onDiscuss }: { weekStart: string; onDiscuss: () => void }) {
  const [sleep, setSleep] = useState<Sleep | null>(null);
  const [token, setToken] = useState('');
  const [connected, setConnected] = useState(() => !!healthHeaders().Authorization);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [revision, setRevision] = useState(0);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetch('/api/health/status').then(r => r.ok ? r.json() : null).then(d => setConfigured(d?.configured ?? null)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!connected) return;
    const controller = new AbortController();
    setBusy(true); setError(''); setSleep(null);
    fetch(`/api/health/sleep?week_start=${weekStart}`, { headers: healthHeaders(), cache: 'no-store', signal: controller.signal })
      .then(async r => { if (!r.ok) throw await responseError(r); return r.json(); })
      .then(setSleep).catch(e => { if (!controller.signal.aborted) setError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [connected, weekStart, revision]);

  const connect = async () => {
    setBusy(true); setError('');
    try {
      const response = await fetch(`/api/health/sleep?week_start=${weekStart}`, { headers: { Authorization: `Bearer ${token.trim()}` }, cache: 'no-store' });
      if (!response.ok) throw await responseError(response);
      const data = await response.json();
      saveHealthKey(token.trim()); setSleep(data); setConnected(true); setToken('');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  const disconnect = () => {
    saveHealthKey(''); setConnected(false); setSleep(null); setConfirmDelete(false); setError(''); setMessage('');
  };

  const upload = async (file: File) => {
    setBusy(true); setError(''); setMessage('');
    try {
      if (file.size > 2_000_000) throw Error('Файл слишком большой. Выбери в экспорте только сон за последние 7 дней.');
      const text = await file.text();
      try { JSON.parse(text); } catch { throw Error('Не удалось прочитать JSON. Выбери экспорт в формате JSON, а не Markdown.'); }
      const response = await fetch('/api/health/sleep', {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...healthHeaders() }, body: text,
      });
      if (!response.ok) throw await responseError(response);
      const result = await response.json();
      if (result.status !== 'ok' || !Number.isInteger(result.imported_nights) || result.imported_nights < 1) throw Error('Сервер не подтвердил импорт. Повтори попытку.');
      setMessage(`Импортировано ночей: ${result.imported_nights}. Если записи не видны, выбери неделю, в которую они попадают.`);
      setRevision(r => r + 1);
      window.dispatchEvent(new Event('fitpulse:health-changed'));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  const remove = async () => {
    setBusy(true); setError(''); setMessage('');
    try {
      const response = await fetch('/api/health/sleep', { method: 'DELETE', headers: healthHeaders() });
      if (!response.ok) throw await responseError(response);
      setConfirmDelete(false); setRevision(r => r + 1);
      window.dispatchEvent(new Event('fitpulse:health-changed'));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  return <section aria-label="Сон Apple Watch" className="bg-[#111726] border border-[#1e293b] rounded-3xl p-5 space-y-3">
    <h2 className="font-bold text-white">Сон · Apple Watch</h2>
    <p className="text-xs text-[#94a3b8]">Данные из «Здоровья» передаёт команда на iPhone. Время и дни сна — по Омску.</p>
    {error && <p role="alert" className="text-xs text-rose-300">{error}</p>}
    {message && <p role="status" className="text-xs text-[#00d084]">{message}</p>}
    {!connected ? <>
      {configured === false && <p className="text-xs text-amber-300">На Render ещё нужно добавить HEALTH_IMPORT_TOKEN. Инструкция ниже.</p>}
      <label className="block text-xs text-[#94a3b8]">Ключ подключения
        <input type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} className="block w-full mt-2 p-3 rounded-xl bg-[#0b0f19] border border-[#334155] text-white" placeholder="Тот же ключ, что в команде и на Render" />
      </label>
      <p className="text-xs text-[#94a3b8]">При подключении ключ сохранится на этом устройстве. Импортированный сон будет доступен ИИ при запросах из приложения.</p>
      <button onClick={connect} disabled={busy || token.trim().length < 32} className="px-4 py-2 rounded-xl bg-[#00d084] text-[#0b0f19] text-sm disabled:opacity-40">{busy ? 'Подключаем…' : 'Подключить сон'}</button>
    </> : <>
      {busy && <p role="status" className="text-xs text-[#94a3b8]">Обновляем данные сна…</p>}
      {sleep && <>
        <p className="text-2xl font-bold text-[#c4b5fd]">{duration(sleep.average_minutes)}</p>
        <p className="text-xs text-[#94a3b8]">Среднее за неделю · ночей с данными: {sleep.tracked_nights} из 7</p>
        {!sleep.tracked_nights && <p className="text-xs text-[#94a3b8]">Запусти команду на iPhone, затем нажми «Обновить сон».</p>}
        <div className="space-y-2">
          {sleep.nights.map(n => <div key={n.date} className="rounded-xl bg-[#0b0f19] p-3 text-xs">
            <div className="flex justify-between gap-2"><span>{n.date.slice(8)}.{n.date.slice(5, 7)}</span><strong>{duration(n.sleep_minutes)}</strong></div>
            {n.sleep_minutes !== null && <p className="mt-1 text-[#94a3b8]">Базовый {duration(n.core_minutes)} · глубокий {duration(n.deep_minutes)} · REM {duration(n.rem_minutes)}{n.asleep_minutes > 0 && ` · без фазы ${duration(n.asleep_minutes)}`}</p>}
          </div>)}
        </div>
        {sleep.imported_at && <p className="text-xs text-[#94a3b8]">Последний импорт: {new Date(sleep.imported_at).toLocaleString('ru-RU', { timeZone: 'Asia/Omsk' })} по Омску</p>}
        <p className="text-xs text-[#94a3b8]">Это оценки часов. ИИ учтёт длительность, регулярность и твоё самочувствие; диагноз по фазам сна он ставить не должен.</p>
      </>}
      <div className="flex flex-wrap gap-3 text-xs">
        <button disabled={busy} onClick={() => { setRevision(r => r + 1); window.dispatchEvent(new Event('fitpulse:health-changed')); }} className="underline disabled:opacity-40">Обновить сон</button>
        {!!sleep?.tracked_nights && <button onClick={onDiscuss} className="text-[#00d084] underline">Спросить ИИ о сне</button>}
        <button disabled={busy} onClick={disconnect} className="underline disabled:opacity-40">Отключить устройство</button>
        <button disabled={busy} onClick={() => setConfirmDelete(true)} className="text-rose-300 underline disabled:opacity-40">Удалить данные с сервера</button>
      </div>
      <label className="block text-xs text-[#c4b5fd]">Загрузить JSON сна
        <input type="file" accept=".json,application/json" disabled={busy} className="block mt-2 w-full text-xs text-[#94a3b8] disabled:opacity-40" onChange={e => {
          const file = e.currentTarget.files?.[0];
          e.currentTarget.value = '';
          if (file) void upload(file);
        }} />
      </label>
      <p className="text-xs text-[#94a3b8]">Поддерживается JSON Health Export Kit. Импортируется только сон; остальные категории из файла не сохраняются. Повторная загрузка обновляет ночи без дублей.</p>
      {confirmDelete && <div className="text-xs space-y-2"><p>Удалить всю импортированную историю сна? Копии уже отправленных сообщений ИИ останутся в чате.</p><button disabled={busy} onClick={remove} className="text-rose-300 underline">Удалить историю сна</button><button onClick={() => setConfirmDelete(false)} className="ml-4 underline">Отмена</button></div>}
    </>}
    <details className="text-xs text-[#94a3b8] space-y-2">
      <summary className="cursor-pointer text-[#c4b5fd]">Как подключить Apple «Здоровье»</summary>
      <p>1. Добавь в Render переменную HEALTH_IMPORT_TOKEN — случайный секрет не короче 32 символов.</p>
      <p>2. В Health Export Kit выбери «Последние 7 дней» и JSON. Файл можно загрузить здесь или отправлять командой на {window.location.origin}/api/health/sleep с этим ключом.</p>
      <p>3. Разреши чтение сна, запусти команду вручную. Затем вставь ключ выше. Ежедневную автоматизацию настрой после успешной проверки на телефоне.</p>
      <a href="/api/health/setup" target="_blank" rel="noreferrer" className="inline-block underline text-[#00d084]">Подробная инструкция и формат команды</a>
    </details>
  </section>;
}
