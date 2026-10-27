import { Target, Flag, Check, TrendingDown } from 'lucide-react';
import type { GoalForecast } from '../types';

const weight = (value: number | null | undefined) => value == null ? '—' : value.toLocaleString('ru-RU', { maximumFractionDigits: 1 });
const date = (value: string) => new Date(value + 'T12:00:00Z').toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });

export function GoalForecastCard({ data, loading }: { data?: GoalForecast; loading: boolean }) {
  const messages = {
    insufficient: 'Для прогноза нужны взвешивания хотя бы за 7 дней. Пока собираем историю.',
    stale: 'Для новой даты прогноза нужен свежий замер веса.',
    reached: 'Цель достигнута по последнему замеру!',
    projected: 'Ориентир при сохранении тренда за последние 28 дней. Даты будут меняться вместе с весом.',
    not_losing: 'По последним замерам устойчивого снижения пока нет — дату цели не прогнозируем.',
  };
  return <section aria-label="Прогноз к цели" aria-busy={loading} className="bg-[#111726] border border-[#1e293b] rounded-3xl p-5 space-y-5 h-[620px] overflow-y-auto [scrollbar-width:thin]">
    <div className="flex items-center gap-3"><div className="w-10 h-10 rounded-2xl bg-[#00d084]/10 flex items-center justify-center"><Target className="w-5 h-5 text-[#00d084]" /></div><div><h2 className="font-bold text-white">К цели {data?.goal_weight ?? 80} кг</h2><p className="text-[11px] text-[#94a3b8]">{data ? `${data.source === 'apple_health' ? 'Apple Здоровье' : 'YAZIO'} · ${date(data.as_of)}` : 'Собираем историю веса…'}</p></div></div>
    <div className="flex justify-between items-end gap-2"><div><p className="text-[10px] text-[#94a3b8] uppercase">Последний вес</p><p className="text-3xl font-bold text-white mt-1 tabular-nums">{weight(data?.current_weight)} <span className="text-sm text-[#94a3b8]">кг</span></p></div><div className="text-right text-xs text-[#94a3b8]"><p>Старт · {weight(data?.start_weight ?? 103)} кг</p><p className="mt-1 text-[#00d084]">Пройдено {weight(data?.progress_percent)}%</p></div></div>
    <div><div role="progressbar" aria-label="Прогресс до целевого веса" aria-valuemin={0} aria-valuemax={100} aria-valuenow={data?.progress_percent ?? 0} className="h-2.5 rounded-full bg-[#0b0f19] overflow-hidden"><div className="h-full bg-[#00d084] rounded-full" style={{ width: `${data?.progress_percent ?? 0}%` }} /></div><div className="flex justify-between text-[11px] text-[#94a3b8] mt-2"><span>Сброшено {weight(data?.lost_kg)} кг</span><span>Осталось {weight(data?.remaining_kg)} кг</span></div></div>
    <div className="flex items-center gap-2 rounded-xl bg-[#0b0f19] px-3 py-2.5 text-xs"><TrendingDown className="w-4 h-4 text-[#00d084] shrink-0" /><span className="text-[#94a3b8]">Тренд веса</span><strong className="ml-auto text-white tabular-nums">{data?.rate_kg_week == null ? 'Мало замеров' : `${data.rate_kg_week > 0 ? '−' : '+'}${weight(Math.abs(data.rate_kg_week))} кг / нед.`}</strong></div>
    <div className="space-y-2" aria-label="Рубежи веса">
      {(data?.milestones ?? [95, 90, 85, 80].map(w => ({ weight: w, reached: false, eta: null, weeks: null }))).map(m => <div key={m.weight} className="flex items-center gap-3 rounded-xl bg-[#0b0f19] px-3 py-3 text-xs">
        <span className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${m.reached ? 'bg-[#00d084]/15 text-[#00d084]' : 'bg-[#a78bfa]/10 text-[#c4b5fd]'}`}>{m.reached ? <Check className="w-4 h-4" /> : <Flag className="w-3.5 h-3.5" />}</span><strong className="text-white">{m.weight} кг</strong><div className="ml-auto text-right"><p className={m.reached ? 'text-[#00d084]' : 'text-[#cbd5e1]'}>{m.reached ? 'Достигнут' : m.eta ? `≈ ${date(m.eta)}` : 'Пока без даты'}</p>{m.weeks != null && <p className="text-[10px] text-[#64748b] mt-0.5">Около {weight(m.weeks)} нед. от замера</p>}</div>
      </div>)}
    </div>
    <p className="text-[11px] text-[#94a3b8] leading-relaxed">{data ? messages[data.status] : loading ? 'Загружаем замеры…' : 'История веса пока недоступна.'}{data?.measured_on && ` Последний замер: ${date(data.measured_on)}.`}</p>
  </section>;
}
