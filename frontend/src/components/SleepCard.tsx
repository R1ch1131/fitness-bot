import { useEffect, useState } from 'react';
import { Moon, Watch, RefreshCw, Sparkles, SlidersHorizontal, ChevronDown, LogOut, Trash2, Clock3 } from 'lucide-react';
import { healthHeaders, saveHealthKey, responseError } from '../healthConnection';

type Night = {
  date: string; start?: string | null; end?: string | null; sleep_minutes: number | null;
  core_minutes: number; deep_minutes: number; rem_minutes: number; asleep_minutes: number; awake_minutes: number;
};
type Sleep = { nights: Night[]; tracked_nights: number; average_minutes: number | null; imported_at: string | null };
export const duration = (minutes: number | null) => {
  if (minutes === null) return 'Нет данных';
  const rounded = Math.round(minutes);
  return rounded < 60 ? `${rounded} мин` : `${Math.floor(rounded / 60)} ч${rounded % 60 ? ` ${rounded % 60} мин` : ''}`;
};
const clock = (value?: string | null) => value && !Number.isNaN(Date.parse(value))
  ? new Date(value).toLocaleTimeString('ru-RU', { timeZone: 'Asia/Omsk', hour: '2-digit', minute: '2-digit' }) : '—';
const secondary = 'inline-flex items-center justify-center gap-2 min-h-11 px-3 py-2.5 rounded-xl border border-[#2b3850] bg-[#192235] text-xs font-medium text-[#cbd5e1] hover:bg-[#24304a] active:scale-[0.98] transition disabled:opacity-40';

function NightCard({ night, expanded }: { night: Night; expanded: boolean }) {
  const [open, setOpen] = useState(expanded);
  const parts = [
    { name: 'Базовый', minutes: night.core_minutes, color: '#818cf8' },
    { name: 'Глубокий', minutes: night.deep_minutes, color: '#a78bfa' },
    { name: 'REM', minutes: night.rem_minutes, color: '#38bdf8' },
    ...(night.asleep_minutes > 0 ? [{ name: 'Без фазы', minutes: night.asleep_minutes, color: '#64748b' }] : []),
  ];
  const total = parts.reduce((sum, part) => sum + part.minutes, 0);
  const title = new Date(night.date + 'T12:00:00Z').toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', timeZone: 'UTC' });
  const weekday = new Date(night.date + 'T12:00:00Z').toLocaleDateString('ru-RU', { weekday: 'long', timeZone: 'UTC' });
  return <article aria-label={`Сон за ${night.date}`} className="rounded-2xl border border-[#202b42] bg-[#0b101d] overflow-hidden">
    <button onClick={() => setOpen(v => !v)} aria-expanded={open} aria-label={`Фазы сна за ${night.date}`} className="w-full p-4 text-left flex items-center justify-between gap-2 hover:bg-white/[0.02] transition">
      <div><p className="text-[10px] uppercase tracking-wider text-[#64748b]">Ночь на {weekday}</p><h3 className="text-sm font-semibold text-white mt-0.5">{title}</h3></div>
      <div className="flex items-center gap-2"><strong className="text-sm text-[#ddd6fe]">{duration(night.sleep_minutes)}</strong><ChevronDown className={`w-4 h-4 text-[#64748b] transition-transform ${open ? 'rotate-180' : ''}`} /></div>
    </button>
    <div className="px-4 pb-4 space-y-3">
      <div className="flex items-center gap-2 text-xs text-[#94a3b8]"><Moon className="w-3.5 h-3.5 text-[#a78bfa]" /><span>{clock(night.start)}</span><span className="flex-1 h-px bg-[#263149]" /><Clock3 className="w-3.5 h-3.5 text-[#64748b]" /><span>{clock(night.end)}</span><span className="sr-only">Время начала и окончания сна по Омску</span></div>
      {total > 0 && <div role="img" aria-label={`Доли фаз сна: ${parts.map(p => `${p.name} ${duration(p.minutes)}`).join(', ')}`} className="h-2.5 rounded-full overflow-hidden flex bg-[#192235]">
        {parts.filter(p => p.minutes > 0).map(p => <span key={p.name} style={{ width: `${p.minutes / total * 100}%`, backgroundColor: p.color }} />)}
      </div>}
      {open && <div className="space-y-3">
        {total > 0 ? <div className={`grid gap-2 ${parts.length > 3 ? 'grid-cols-2' : 'grid-cols-3'}`}>
          {parts.map(p => <div key={p.name} className="rounded-xl bg-[#131b2c] px-2.5 py-2.5">
            <p className="text-[10px] text-[#94a3b8] flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: p.color }} />{p.name}</p>
            <p className="text-xs text-white font-semibold mt-1.5">{duration(p.minutes)}</p>
            <p className="text-[10px] text-[#64748b] mt-1">{Math.round(p.minutes / total * 100)}%</p>
          </div>)}
        </div> : <p className="text-xs text-[#94a3b8]">Часы не записали фазы сна.</p>}
        <div className="flex items-center justify-between text-[11px]"><span className="text-[#64748b]">Бодрствование</span><span className="text-[#cbd5e1]">{duration(night.awake_minutes)}</span></div>
      </div>}
    </div>
  </article>;
}

export function SleepCard({ weekStart, onDiscuss, disabled = false }: {
  weekStart: string; onDiscuss: (context: string) => void; disabled?: boolean;
}) {
  const [sleep, setSleep] = useState<Sleep | null>(null);
  const [token, setToken] = useState('');
  const [connected, setConnected] = useState(() => !!healthHeaders().Authorization);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [revision, setRevision] = useState(0);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const blocked = busy || disabled;

  useEffect(() => {
    fetch('/api/health/status').then(r => r.ok ? r.json() : null).then(d => setConfigured(d?.configured ?? null)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!connected) return;
    const controller = new AbortController();
    setBusy(true); setError(''); setSleep(null);
    fetch(`/api/health/sleep?week_start=${weekStart}`, { headers: healthHeaders(), cache: 'no-store', signal: controller.signal })
      .then(async r => { if (!r.ok) throw await responseError(r); return r.json(); })
      .then(data => { if (!controller.signal.aborted) setSleep(data); }).catch(e => { if (!controller.signal.aborted) setError(e.message); })
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
  const refresh = () => { setRevision(r => r + 1); window.dispatchEvent(new Event('fitpulse:health-changed')); };
  const disconnect = () => {
    saveHealthKey(''); setConnected(false); setSleep(null); setConfirmDelete(false); setSettingsOpen(false); setError('');
  };
  const remove = async () => {
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/health/sleep', { method: 'DELETE', headers: healthHeaders() });
      if (!response.ok) throw await responseError(response);
      setConfirmDelete(false); refresh();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  const nights = [...(sleep?.nights || [])].sort((a, b) => b.date.localeCompare(a.date));
  const dates = Array.from({ length: 7 }, (_, index) => new Date(Date.parse(weekStart + 'T12:00:00Z') + index * 86400000).toISOString().slice(0, 10));
  const activeDate = selectedDate && dates.includes(selectedDate) ? selectedDate : nights[0]?.date || weekStart;
  const activeNight = nights.find(night => night.date === activeDate);
  return <section aria-label="Сон Apple Watch" aria-busy={blocked} className="bg-[#111726] border border-[#1e293b] rounded-3xl p-4 sm:p-5 h-[600px] flex flex-col gap-4">
    <div className="flex items-center justify-between gap-3">
      <div className="flex items-center gap-3"><div className="w-10 h-10 rounded-2xl bg-[#a78bfa]/10 border border-[#a78bfa]/20 flex items-center justify-center"><Moon className="w-5 h-5 text-[#c4b5fd]" /></div><div><h2 className="font-bold text-white text-sm">Сон</h2><p className="text-[10px] text-[#64748b] mt-0.5 flex items-center gap-1"><Watch className="w-3 h-3" />Apple Watch · Омск</p></div></div>
      {connected && <button aria-label="Настройки сна" aria-expanded={settingsOpen} onClick={() => setSettingsOpen(v => !v)} className="w-10 h-10 rounded-xl flex items-center justify-center text-[#64748b] hover:text-white hover:bg-[#192235] transition"><SlidersHorizontal className="w-4 h-4" /></button>}
    </div>
    <div className="flex-1 min-h-0 overflow-y-auto space-y-4 [scrollbar-width:thin]">
    {error && <p role="alert" className="text-xs text-rose-300 rounded-xl bg-rose-500/5 p-3">{error}</p>}
    {!connected ? <div className="space-y-3">
      <p className="text-xs text-[#94a3b8]">Подключи сон для просмотра и разбора с ИИ.</p>
      {configured === false && <p className="text-xs text-amber-300">На сервере нужно настроить HEALTH_IMPORT_TOKEN.</p>}
      <label className="block text-xs text-[#94a3b8]">Ключ подключения<input type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} className="block w-full mt-2 p-3 rounded-xl bg-[#0b0f19] border border-[#334155] text-white" placeholder="Вставь ключ" /></label>
      <button onClick={connect} disabled={blocked || token.trim().length < 32} className="w-full px-4 py-3 rounded-xl bg-[#00d084] text-[#0b0f19] text-xs font-semibold disabled:opacity-40">{busy ? 'Подключаем…' : 'Подключить сон'}</button>
      <a href="/api/health/setup" target="_blank" rel="noreferrer" className={`${secondary} w-full`}>Как подключить</a>
    </div> : <>
      {busy && !sleep && <div role="status" aria-label="Загрузка сна" className="space-y-4 animate-pulse"><p className="text-xs text-[#94a3b8]">Обновляем сон…</p><div className="h-14 bg-[#192235] rounded-xl" /><div className="grid grid-cols-7 gap-1">{Array.from({ length: 7 }, (_, i) => <div key={i} className="h-20 rounded-xl bg-[#192235]" />)}</div><div className="h-64 bg-[#0b101d] rounded-2xl" /></div>}
      {sleep && <>
        {sleep.tracked_nights > 0 && <div className="flex items-end justify-between gap-2 px-1"><div><p className="text-[10px] uppercase tracking-wider text-[#64748b]">Средний сон</p><p className="text-3xl font-bold tracking-tight text-[#ddd6fe] mt-1">{duration(sleep.average_minutes)}</p></div><div className="text-right pb-1"><p className="text-sm font-semibold text-[#cbd5e1]">{sleep.tracked_nights} / 7</p><p className="text-[10px] text-[#64748b]">ночей с данными</p></div></div>}
        <div role="group" aria-label="Дни сна" className="grid grid-cols-7 gap-1">
          {dates.map((date, index) => {
            const night = nights.find(n => n.date === date);
            const minutes = night?.sleep_minutes;
            const value = minutes === null || minutes === undefined ? '—' : `${Math.floor(Math.round(minutes) / 60)}:${String(Math.round(minutes) % 60).padStart(2, '0')}`;
            const active = date === activeDate;
            return <button key={date} disabled={blocked} onClick={() => setSelectedDate(date)} aria-pressed={active} aria-label={`Сон ${date}: ${minutes === null || minutes === undefined ? 'нет данных' : duration(minutes)}`} className={`min-w-0 rounded-xl py-2.5 px-0.5 text-center border transition active:scale-95 disabled:opacity-40 ${active ? 'bg-[#a78bfa]/15 border-[#a78bfa]/50 text-[#ddd6fe]' : 'bg-[#0b101d] border-transparent text-[#64748b] hover:bg-[#192235]'}`}>
              <span className="block text-[10px]">{['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][index]}</span>
              <span className={`block text-xs font-semibold mt-1 ${active ? 'text-white' : 'text-[#94a3b8]'}`}>{Number(date.slice(8))}</span>
              <span className={`block text-[10px] tabular-nums mt-1.5 ${minutes !== null && minutes !== undefined ? 'text-[#c4b5fd]' : ''}`}>{value}</span>
            </button>;
          })}
        </div>
        {activeNight ? <NightCard key={activeNight.date} night={activeNight} expanded /> : <div className="text-center rounded-2xl bg-[#0b101d] py-6 px-4"><Moon className="w-6 h-6 mx-auto text-[#475569] mb-2" /><p className="text-sm font-medium text-[#cbd5e1]">{sleep.tracked_nights ? 'За этот день записей нет' : 'За эту неделю записей нет'}</p><p className="text-xs text-[#64748b] mt-1">Выбери другой день или обнови сон.</p></div>}
      </>}
      <div className="grid grid-cols-2 gap-2">
        <button disabled={blocked} onClick={refresh} className={secondary}><RefreshCw className={`w-4 h-4 ${busy ? 'animate-spin' : ''}`} />Обновить сон</button>
        <button disabled={blocked || !sleep?.tracked_nights} onClick={() => {
          if (!sleep) return;
          const context = [`Сон Apple Watch · время по Омску. Ночей с данными: ${sleep.tracked_nights} из 7. Среднее: ${duration(sleep.average_minutes)}.`,
            ...[...nights].reverse().map(n => `${n.date}: сон ${duration(n.sleep_minutes)}, ${clock(n.start)}–${clock(n.end)}; базовый ${duration(n.core_minutes)}, глубокий ${duration(n.deep_minutes)}, REM ${duration(n.rem_minutes)}${n.asleep_minutes ? `, без фазы ${duration(n.asleep_minutes)}` : ''}; бодрствование ${duration(n.awake_minutes)}.`),
          ].join('\n');
          onDiscuss(context);
        }} className="inline-flex items-center justify-center gap-2 min-h-11 px-3 py-2.5 rounded-xl bg-[#a78bfa]/15 border border-[#a78bfa]/30 text-[#ddd6fe] text-xs font-semibold hover:bg-[#a78bfa]/25 active:scale-[0.98] transition disabled:opacity-40"><Sparkles className="w-4 h-4" />Разобрать с ИИ</button>
      </div>
      {settingsOpen && <div className="rounded-2xl bg-[#0b101d] p-3 space-y-2" aria-label="Управление сном">
        <button disabled={blocked} onClick={disconnect} className={`${secondary} w-full justify-start`}><LogOut className="w-4 h-4" />Отключить устройство</button>
        <button disabled={blocked} onClick={() => setConfirmDelete(true)} className={`${secondary} w-full justify-start text-rose-300`}><Trash2 className="w-4 h-4" />Удалить историю сна</button>
        {confirmDelete && <div className="text-xs space-y-3 p-1"><p className="text-[#94a3b8]">Удалить все записи сна с сервера?</p><div className="grid grid-cols-2 gap-2"><button disabled={blocked} onClick={remove} className="rounded-xl bg-rose-500/15 text-rose-300 py-2.5 disabled:opacity-40">Удалить окончательно</button><button disabled={blocked} onClick={() => setConfirmDelete(false)} className={secondary}>Отмена</button></div></div>}
      </div>}
    </>}
    </div>
  </section>;
}
