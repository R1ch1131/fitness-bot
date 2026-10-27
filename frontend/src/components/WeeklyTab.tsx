import { useEffect, useState } from 'react';
import { Award, Download, MessageSquare } from 'lucide-react';
import type { WeeklyResponse, WeeklyAnalysisRequest } from '../types';
import { healthHeaders, responseError } from '../healthConnection';
import { SleepCard } from './SleepCard';
import { WeekSelector } from './WeekSelector';
import { GoalForecastCard } from './GoalForecastCard';

interface WeeklyTabProps {
  data: WeeklyResponse | null;
  selectedWeek?: string;
  isLoading: boolean;
  error?: string;
  onRetry: () => void;
  onSelectWeek: (week: string) => void;
  onAnalyze: (request: WeeklyAnalysisRequest) => void;
}

export function WeeklyTab({ data, selectedWeek, isLoading, error, onRetry, onSelectWeek, onAnalyze }: WeeklyTabProps) {
  const [image, setImage] = useState('');
  const [imageError, setImageError] = useState('');
  const [imageRevision, setImageRevision] = useState(0);
  const start = data?.period_start;

  useEffect(() => {
    const changed = () => setImageRevision(r => r + 1);
    window.addEventListener('fitpulse:health-changed', changed);
    return () => window.removeEventListener('fitpulse:health-changed', changed);
  }, []);

  useEffect(() => {
    if (!start) return;
    const controller = new AbortController();
    let objectUrl = '';
    setImage(''); setImageError('');
    fetch(`/api/weekly/image?week_start=${start}`, { headers: healthHeaders(), cache: 'no-store', signal: controller.signal })
      .then(async r => { if (!r.ok) throw await responseError(r); if (!r.headers.get('Content-Type')?.includes('image/png')) throw Error('Сервер ещё запускается. Повтори загрузку картинки.'); return r.blob(); })
      .then(blob => { if (!controller.signal.aborted) { objectUrl = URL.createObjectURL(blob); setImage(objectUrl); } })
      .catch(e => { if (!controller.signal.aborted) setImageError(e.message); });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [start, data?.as_of, imageRevision]);

  const analyze = (focus?: 'sleep', context?: string) => {
    if (!data || isLoading) return;
    const average = (value: number | null, unit: string) => value === null ? 'нет данных' : `${Math.round(value)} ${unit}`;
    onAnalyze({ weekStart: data.period_start, weekEnd: data.period_end, focus,
      context: context || `Тренировки: ${data.workout_count}. Тоннаж: ${data.tonnage_kg} кг.\nПитание записано за ${data.averages.tracked_days} дней. Среднее: ${average(data.averages.calories, 'ккал')}, белок ${average(data.averages.protein, 'г')}.\nИзменение веса: ${data.weight_change === null ? 'мало замеров' : `${data.weight_change} кг`}.`,
    });
  };

  const today = new Date(Date.now() + 6 * 3600000);
  const monday = new Date(today.getTime() - ((today.getUTCDay() + 6) % 7) * 86400000).toISOString().slice(0, 10);
  const week = data?.period_start || selectedWeek || monday;
  const end = data?.period_end || new Date(Date.parse(week + 'T12:00:00Z') + 6 * 86400000).toISOString().slice(0, 10);
  return <div className="space-y-4 pb-32 px-3 pt-3 max-w-4xl mx-auto">
    <WeekSelector weekStart={week} onChange={onSelectWeek} disabled={isLoading || !data} />
    <section aria-label="Итоги недели" className="bg-[#111726] border border-[#1e293b] rounded-3xl p-5 space-y-4">
      <div className="flex items-center gap-3"><Award className="w-6 h-6 text-[#f59e0b] shrink-0" /><div>
        <h2 className="font-bold text-white">Твоя неделя</h2>
        <p className="text-xs text-[#94a3b8]">{week} — {end} · по Омску</p>
      </div></div>
      <p className="text-xs text-[#94a3b8]">Картинка формируется по твоим записям. Текущая неделя обновляется по мере появления данных.</p>
      <button onClick={onRetry} disabled={isLoading} className="px-3 py-2 rounded-xl text-xs text-[#00d084] bg-[#00d084]/10 border border-[#00d084]/20 hover:bg-[#00d084]/15 disabled:opacity-40">{isLoading ? 'Обновляем неделю…' : 'Обновить неделю'}</button>
      <div className="aspect-[1080/1560] w-full rounded-2xl border border-[#1e293b] bg-[#0b0f19] overflow-hidden relative" aria-busy={!image && !imageError}>
        {image ? <a className="block w-full h-full" href={image} target="_blank" rel="noreferrer" aria-label="Открыть картинку итогов недели"><img width={1080} height={1560} src={image} alt={`Итоги недели ${week} — ${end}: тренировки, питание и динамика веса`} className="w-full h-full object-contain" /></a>
          : <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 px-6 text-center"><Award className={`w-9 h-9 text-[#00d084]/50 ${imageError ? '' : 'animate-pulse'}`} /><p role={imageError ? 'alert' : 'status'} className="text-xs text-[#94a3b8]">{imageError || 'Собираем картинку недели…'}</p></div>}
      </div>
      <div className="flex flex-wrap gap-3 min-h-11">
        <a aria-disabled={!image} tabIndex={image ? 0 : -1} href={image || undefined} download={`fitpulse-${start}.png`} className={`inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-[#334155] text-xs ${image ? '' : 'opacity-40 pointer-events-none'}`}><Download className="w-4 h-4" />Сохранить картинку</a>
        {imageError && <button onClick={() => setImageRevision(r => r + 1)} className="text-xs underline">Повторить картинку</button>}
        <button onClick={() => analyze()} disabled={isLoading || !data} className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-[#00d084] text-[#0b0f19] text-xs font-semibold disabled:opacity-40"><MessageSquare className="w-4 h-4" />Обсудить с ИИ</button>
      </div>
      {!!data?.warnings?.length && <p className="text-xs text-amber-300">{data?.warnings.join('. ')}</p>}
      {error && <p role="alert" className="text-xs text-rose-300">{error}</p>}
    </section>
    <GoalForecastCard data={data?.goal_forecast} loading={isLoading} />
    <SleepCard weekStart={week} disabled={isLoading || !data} onDiscuss={context => analyze('sleep', context)} />
    <div className="sr-only" aria-label="Данные недельной картинки">
      <h2>По дням недели</h2>
      {data?.days.map(day => <p key={day.date}>{day.weekday} {day.date}: {day.is_logged ? `${day.calories} ккал; белок ${day.protein} г; жиры ${day.fat} г; углеводы ${day.carbs} г` : day.is_future ? 'Впереди' : 'Питание не записано'}. {day.workout_titles.join(', ')}{day.workout_count ? `; тоннаж ${day.tonnage_kg} кг` : ''}</p>)}
    </div>
  </div>;
}
