import { ChevronLeft, ChevronRight } from 'lucide-react';

const DAY = 86400000;
export const shiftWeek = (start: string, direction: number) => new Date(Date.parse(start + 'T12:00:00Z') + direction * 7 * DAY).toISOString().slice(0, 10);

export function WeekSelector({ weekStart, disabled, onChange, label = 'Неделя отчёта' }: {
  weekStart: string; disabled?: boolean; onChange: (week: string) => void; label?: string;
}) {
  const today = new Date(Date.now() + 6 * 3600000);
  const monday = new Date(today.getTime() - ((today.getUTCDay() + 6) % 7) * DAY).toISOString().slice(0, 10);
  const earliest = new Date(today.getTime() - 365 * DAY).toISOString().slice(0, 10);
  const end = new Date(Date.parse(weekStart + 'T12:00:00Z') + 6 * DAY);
  const date = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', timeZone: 'UTC' });
  const range = `${date.format(new Date(weekStart + 'T12:00:00Z'))} — ${date.format(end)}`;
  const button = 'w-10 h-10 rounded-xl bg-[#192235] border border-[#2b3850] flex items-center justify-center text-[#c4b5fd] hover:bg-[#24304a] active:scale-95 transition disabled:opacity-25 disabled:active:scale-100';
  return <div role="group" aria-label={label} className="rounded-2xl bg-[#0b0f19] border border-[#1e293b] p-2">
    <div className="flex items-center justify-between gap-2">
      <button aria-label="Предыдущая неделя" disabled={disabled || shiftWeek(weekStart, -1) < earliest} onClick={() => onChange(shiftWeek(weekStart, -1))} className={button}><ChevronLeft className="w-5 h-5" /></button>
      <div className="text-center min-w-0" aria-live="polite">
        <p className="text-xs font-semibold text-white">{range}</p>
        <p className="text-[10px] text-[#64748b] mt-0.5">{weekStart === monday ? 'Эта неделя' : weekStart.slice(0, 4)}</p>
      </div>
      <button aria-label="Следующая неделя" disabled={disabled || weekStart >= monday} onClick={() => onChange(shiftWeek(weekStart, 1))} className={button}><ChevronRight className="w-5 h-5" /></button>
    </div>
    {weekStart < monday && <button disabled={disabled} onClick={() => onChange('')} className="w-full mt-2 rounded-lg py-1.5 text-[11px] font-medium text-[#00d084] bg-[#00d084]/10 hover:bg-[#00d084]/15 disabled:opacity-40">Текущая неделя</button>}
  </div>;
}
