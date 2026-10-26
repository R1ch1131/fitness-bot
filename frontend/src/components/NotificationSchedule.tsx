import { useEffect, useState } from 'react';
import { CustomReminders } from './CustomReminders';

type Kind = 'gym' | 'laundry' | 'nutrition' | 'weekly' | 'checkin';
type Preferences = Record<Kind, { enabled: boolean; time?: string; delay_minutes?: number }>;
type Schedule = { server_time: string; last_checked_at?: string | null; items: Partial<Record<Kind, { next_run: string | null; last_accepted_at: string | null }>> };
const formatDate = (value: string) => new Date(value).toLocaleString('ru-RU', { timeZone: 'Asia/Omsk', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
const reminders: { key: Kind; title: string; description: string }[] = [
  { key: 'gym', title: 'Взять вещи в зал', description: 'Понедельник — пятница' },
  { key: 'laundry', title: 'Постирать вещи', description: 'Каждый день' },
  { key: 'nutrition', title: 'Проверить питание', description: 'Каждый день' },
  { key: 'weekly', title: 'Недельные итоги', description: 'Воскресенье' },
  { key: 'checkin', title: 'Самочувствие после тренировки', description: 'После окончания тренировки в Hevy' },
];

export function NotificationSchedule() {
  const [settings, setSettings] = useState<Preferences | null>(null);
  const [saved, setSaved] = useState('');
  const [busy, setBusy] = useState(true);
  const [message, setMessage] = useState('Загружаем расписание…');
  const [schedule, setSchedule] = useState<Schedule | null>(null);

  async function load() {
    try {
      const response = await fetch('/api/notifications/settings', { signal: AbortSignal.timeout(15000), cache: 'no-store' });
      if (!response.ok) throw new Error('Не удалось загрузить расписание. Повторите попытку.');
      const data = await response.json();
      if (!reminders.every(({ key }) => typeof data.settings?.[key]?.enabled === 'boolean')) throw new Error('Сервер вернул некорректное расписание.');
      setSettings(data.settings);
      setSaved(JSON.stringify(data.settings));
      setSchedule(data.schedule || null);
      setMessage('');
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Не удалось загрузить расписание.');
    } finally { setBusy(false); }
  }

  useEffect(() => {
    void load();
  }, []);

  const update = (key: Kind, field: string, value: boolean | string | number) => {
    setSettings(previous => previous && ({ ...previous, [key]: { ...previous[key], [field]: value } }));
    setMessage('Изменения ещё не сохранены');
  };

  async function save() {
    if (!settings || busy) return;
    setBusy(true);
    try {
      const response = await fetch('/api/notifications/settings', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings), signal: AbortSignal.timeout(15000),
      });
      const data = await response.json();
      if (!response.ok || data.status !== 'ok') throw new Error(data.detail || 'Не удалось сохранить расписание.');
      setSettings(data.settings);
      setSaved(JSON.stringify(data.settings));
      setSchedule(data.schedule || null);
      setMessage('Расписание сохранено. Оно действует для уведомлений приложения.');
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Не удалось сохранить расписание.'); }
    finally { setBusy(false); }
  }

  const valid = settings && reminders.every(({ key }) => key === 'checkin'
    ? Number.isInteger(settings[key].delay_minutes) && settings[key].delay_minutes! >= 5 && settings[key].delay_minutes! <= 120
    : /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(settings[key].time || ''));
  const dirty = settings && JSON.stringify(settings) !== saved;

  async function checkStatus() {
    setBusy(true);
    try {
      const response = await fetch('/api/notifications/settings', { cache: 'no-store', signal: AbortSignal.timeout(15000) });
      if (!response.ok) throw new Error('Не удалось проверить расписание.');
      const data = await response.json();
      setSchedule(data.schedule || null);
      setMessage('Статус расписания обновлён.');
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Не удалось проверить расписание.'); }
    finally { setBusy(false); }
  }

  return (
    <div className="border-t border-[#1e293b] pt-4 space-y-4">
      <div>
        <h3 className="font-semibold">Расписание уведомлений</h3>
        <p className="text-xs text-[#94a3b8] mt-1">Время по Омску (UTC+6). Общее для приложения на всех твоих устройствах. Telegram работает по прежнему расписанию.</p>
        <p className="text-xs text-[#94a3b8] mt-1">24-часовой формат: 01:00 — час ночи, 13:00 — час дня.</p>
        {schedule && <p className="text-xs text-[#94a3b8] mt-1">Время сервера при проверке: {formatDate(schedule.server_time)}. {schedule.last_checked_at ? `Планировщик проверял расписание: ${formatDate(schedule.last_checked_at)}.` : 'Проверка планировщика ещё не зарегистрирована.'}</p>}
      </div>
      {settings && reminders.map(({ key, title, description }) => (
        <div key={key} className="rounded-xl bg-[#0b0f19] p-3 space-y-2">
          <label className="flex items-center justify-between gap-3 cursor-pointer">
            <span><span className="block text-sm font-medium">{title}</span><span className="block text-xs text-[#94a3b8]">{description}</span></span>
            <input type="checkbox" checked={settings[key].enabled} disabled={busy} onChange={e => update(key, 'enabled', e.target.checked)} className="w-5 h-5 accent-[#00d084]" />
          </label>
          {key !== 'checkin' && !dirty && schedule?.items[key] && <p className="text-xs text-[#94a3b8]">
            {!settings[key].enabled ? 'Выключено' : schedule.items[key]!.next_run
              ? `${new Date(schedule.items[key]!.next_run!).getTime() < new Date(schedule.server_time).getTime() ? 'Ожидает отправки с' : 'Следующая отправка:'} ${formatDate(schedule.items[key]!.next_run!)} по Омску`
              : 'Следующая отправка не определена'}
            {schedule.items[key]!.last_accepted_at && <span className="block mt-1">Последний приём push-сервисом: {formatDate(schedule.items[key]!.last_accepted_at!)}.</span>}
          </p>}
          <label className="flex items-center justify-between gap-3 text-xs text-[#94a3b8]">
            <span>{key === 'checkin' ? 'Через сколько минут' : 'Время напоминания'}</span>
            {key === 'checkin' ? (
              <input aria-label="Задержка опроса в минутах" type="number" min="5" max="120" step="1" value={settings[key].delay_minutes ?? ''} disabled={busy || !settings[key].enabled} onChange={e => update(key, 'delay_minutes', e.target.value === '' ? NaN : Number(e.target.value))} className="w-24 rounded-lg bg-[#111726] border border-[#334155] p-2 text-white disabled:opacity-40" />
            ) : (
              <input aria-label={`Время: ${title}`} type="time" required value={settings[key].time || ''} disabled={busy || !settings[key].enabled} onChange={e => update(key, 'time', e.target.value)} className="rounded-lg bg-[#111726] border border-[#334155] p-2 text-white disabled:opacity-40 [color-scheme:dark]" />
            )}
          </label>
        </div>
      ))}
      {settings ? <button onClick={save} disabled={busy || !valid || JSON.stringify(settings) === saved} className="px-4 py-2 rounded-xl bg-[#00d084] text-[#0b0f19] font-semibold disabled:opacity-40">{busy ? 'Сохраняем…' : 'Сохранить расписание'}</button>
        : <button onClick={() => { setBusy(true); void load(); }} disabled={busy} className="px-3 py-2 rounded-xl border border-[#334155] disabled:opacity-40">Загрузить расписание</button>}
      {settings && <button disabled={busy || !!dirty} onClick={checkStatus} className="ml-3 text-xs text-[#94a3b8] underline disabled:opacity-40">Проверить расписание</button>}
      {message && <p role="status" className="text-xs text-[#94a3b8]">{message}</p>}
      <CustomReminders />
    </div>
  );
}
