import { useEffect, useState } from 'react';

type ReminderData = { title: string; body: string; time: string; weekdays: number[]; enabled: boolean };
type Reminder = ReminderData & { id: string; created_at: string; next_run: string | null };
const days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
const empty: ReminderData = { title: '', body: '', time: '09:00', weekdays: [0, 1, 2, 3, 4, 5, 6], enabled: true };
const fields = (item: ReminderData): ReminderData => ({ title: item.title, body: item.body, time: item.time, weekdays: [...item.weekdays], enabled: item.enabled });
const dateLabel = (iso: string) => new Date(iso).toLocaleString('ru-RU', { timeZone: 'Asia/Omsk', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });

export function CustomReminders() {
  const [items, setItems] = useState<Reminder[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('Загружаем свои уведомления…');
  const [draft, setDraft] = useState<ReminderData | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  async function request(path = '', method = 'GET', body?: ReminderData) {
    const response = await fetch('/api/notifications/reminders' + path, {
      method, cache: 'no-store', signal: AbortSignal.timeout(15000),
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await response.json();
    if (!response.ok || data.status !== 'ok' || !Array.isArray(data.reminders)) throw new Error(data.detail || 'Не удалось обновить напоминания.');
    setItems(data.reminders);
    setLoaded(true);
  }

  async function load() {
    setBusy(true);
    try { await request(); setMessage(''); }
    catch (e) { setMessage(e instanceof Error ? e.message : 'Не удалось загрузить напоминания.'); }
    finally { setBusy(false); }
  }
  useEffect(() => { void load(); }, []);

  async function save() {
    if (!draft || busy) return;
    setBusy(true);
    try {
      await request(editing ? '/' + editing : '', editing ? 'PUT' : 'POST', draft);
      setDraft(null); setEditing(null); setMessage('Напоминание сохранено на сервере.');
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Не удалось сохранить напоминание.'); }
    finally { setBusy(false); }
  }

  async function toggle(item: Reminder) {
    setBusy(true);
    try { await request('/' + item.id, 'PUT', { ...fields(item), enabled: !item.enabled }); setMessage(item.enabled ? 'Напоминание выключено.' : 'Напоминание включено.'); }
    catch (e) { setMessage(e instanceof Error ? e.message : 'Не удалось изменить напоминание.'); }
    finally { setBusy(false); }
  }

  async function remove(id: string) {
    setBusy(true);
    try { await request('/' + id, 'DELETE'); setDeleting(null); if (editing === id) { setDraft(null); setEditing(null); } setMessage('Напоминание удалено.'); }
    catch (e) { setMessage(e instanceof Error ? e.message : 'Не удалось удалить напоминание.'); }
    finally { setBusy(false); }
  }

  const valid = draft && draft.title.trim().length > 0 && draft.title.trim().length <= 80 && draft.body.length <= 240 && draft.weekdays.length > 0 && /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(draft.time);
  const inputStyle = 'w-full rounded-xl border border-[#334155] bg-[#0b0f19] px-3 py-2 text-sm text-white disabled:opacity-40';
  return (
    <section className="border-t border-[#1e293b] pt-4 space-y-3" aria-label="Свои уведомления">
      <h3 className="font-semibold">Свои уведомления</h3>
      <p className="text-xs text-[#94a3b8]">Добавляй свои напоминания. Время по Омску, расписание общее для приложения на всех твоих устройствах. Для получения нужно разрешить push.</p>
      {items.map(item => <article key={item.id} className="rounded-xl bg-[#0b0f19] p-3 space-y-2">
        <label className="flex items-center justify-between gap-3"><span className="font-medium break-words min-w-0">{item.title}</span>
          <input type="checkbox" aria-label={`Включить: ${item.title}`} checked={item.enabled} disabled={busy || !!draft} onChange={() => void toggle(item)} className="w-5 h-5 shrink-0 accent-[#00d084]" />
        </label>
        {item.body && <p className="text-xs text-[#94a3b8] whitespace-pre-wrap break-words">{item.body}</p>}
        <p className="text-xs text-[#94a3b8]">{item.time} · {item.weekdays.map(day => days[day]).join(', ')} · {item.enabled ? 'Включено' : 'Выключено'}</p>
        {item.next_run && <p className="text-xs text-[#94a3b8]">Ближайшая отправка: {dateLabel(item.next_run)} по Омску</p>}
        <div className="flex gap-4 text-xs">
          <button disabled={busy || !!draft} onClick={() => { setEditing(item.id); setDraft(fields(item)); setMessage(''); }} className="text-[#00d084] disabled:opacity-40">Изменить</button>
          <button disabled={busy} onClick={() => setDeleting(item.id)} className="text-[#94a3b8] disabled:opacity-40">Удалить</button>
          {deleting === item.id && <><button disabled={busy} onClick={() => void remove(item.id)} className="text-red-400">Удалить окончательно</button><button disabled={busy} onClick={() => setDeleting(null)}>Отмена</button></>}
        </div>
      </article>)}
      {loaded && !items.length && <p className="text-xs text-[#94a3b8]">Своих напоминаний пока нет.</p>}
      {!draft && loaded && <button disabled={busy || items.length >= 50} onClick={() => { setEditing(null); setDraft(fields(empty)); setMessage(''); }} className="px-3 py-2 rounded-xl border border-[#00d084]/50 text-[#00d084] disabled:opacity-40">Добавить уведомление</button>}
      {!loaded && !busy && <button onClick={() => void load()} className="text-xs underline">Повторить загрузку</button>}
      {draft && <div className="space-y-3 rounded-xl border border-[#334155] p-3">
        <p className="text-sm font-medium">{editing ? 'Изменить уведомление' : 'Новое уведомление'}</p>
        <label className="block space-y-1"><span className="text-xs text-[#94a3b8]">Название</span><input value={draft.title} maxLength={80} disabled={busy} onChange={e => setDraft({ ...draft, title: e.target.value })} placeholder="Например: выпить воду" className={inputStyle} /></label>
        <label className="block space-y-1"><span className="text-xs text-[#94a3b8]">Текст уведомления</span><textarea value={draft.body} maxLength={240} disabled={busy} onChange={e => setDraft({ ...draft, body: e.target.value })} placeholder="Необязательно" rows={2} className={inputStyle} /></label>
        <label className="flex items-center justify-between text-xs text-[#94a3b8]">Время по Омску<input type="time" value={draft.time} disabled={busy} onChange={e => setDraft({ ...draft, time: e.target.value })} className="rounded-lg border border-[#334155] bg-[#0b0f19] p-2 text-white [color-scheme:dark]" /></label>
        <fieldset disabled={busy} className="space-y-2"><legend className="text-xs text-[#94a3b8]">Повторять по дням</legend><div className="flex gap-1">{days.map((day, index) => <button key={day} type="button" aria-pressed={draft.weekdays.includes(index)} onClick={() => setDraft({ ...draft, weekdays: draft.weekdays.includes(index) ? draft.weekdays.filter(value => value !== index) : [...draft.weekdays, index].sort() })} className={`flex-1 rounded-lg py-2 text-xs ${draft.weekdays.includes(index) ? 'bg-[#00d084] text-[#0b0f19]' : 'bg-[#1e293b] text-[#94a3b8]'}`}>{day}</button>)}</div></fieldset>
        {!draft.weekdays.length && <p className="text-xs text-[#94a3b8]">Выбери хотя бы один день недели.</p>}
        <div className="flex gap-3"><button disabled={busy || !valid} onClick={() => void save()} className="rounded-xl bg-[#00d084] text-[#0b0f19] px-3 py-2 text-xs font-semibold disabled:opacity-40">{busy ? 'Сохраняем…' : 'Сохранить уведомление'}</button><button disabled={busy} onClick={() => { setDraft(null); setEditing(null); }} className="text-xs text-[#94a3b8]">Отмена</button></div>
      </div>}
      {message && <p role="status" className="text-xs text-[#94a3b8]">{message}</p>}
    </section>
  );
}
