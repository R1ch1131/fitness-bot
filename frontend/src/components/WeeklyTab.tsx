import { useEffect, useRef, useState } from 'react';
import { Award, Download, MessageSquare } from 'lucide-react';
import type { WeeklyResponse } from '../types';
import { healthHeaders, responseError } from '../healthConnection';
import { SleepCard } from './SleepCard';

interface WeeklyTabProps {
  data: WeeklyResponse | null;
  isLoading: boolean;
  error?: string;
  onRetry: () => void;
  onSelectWeek: (week: string) => void;
  onOpenChat: (reply?: string, prompt?: string) => void;
}

export function WeeklyTab({ data, isLoading, error, onRetry, onSelectWeek, onOpenChat }: WeeklyTabProps) {
  const [image, setImage] = useState('');
  const [imageError, setImageError] = useState('');
  const [imageRevision, setImageRevision] = useState(0);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState('');
  const analysisRequest = useRef<AbortController | null>(null);
  const start = data?.period_start;

  useEffect(() => () => analysisRequest.current?.abort(), []);

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

  const analyze = async (focus?: 'sleep') => {
    if (!start || analyzing) return;
    const controller = new AbortController();
    analysisRequest.current = controller;
    setAnalyzing(true); setAnalysisError('');
    try {
      const response = await fetch(`/api/weekly/analysis?week_start=${start}${focus ? '&focus=sleep' : ''}`, { method: 'POST', headers: healthHeaders(), signal: controller.signal });
      if (!response.ok) throw await responseError(response);
      const result = await response.json();
      onOpenChat(`Итоги недели ${data?.period_start} — ${data?.period_end}\n\n${result.reply}`);
    } catch (e) { if (!controller.signal.aborted) setAnalysisError((e as Error).message); }
    finally { if (!controller.signal.aborted) setAnalyzing(false); }
  };

  if (!data) return <div className="min-h-[50vh] flex flex-col items-center justify-center px-6 space-y-3 text-sm text-[#94a3b8]">
    <p role={error ? 'alert' : 'status'}>{error || 'Загрузка сводки недели…'}</p>
    {error && <button onClick={onRetry} className="text-[#00d084] underline">Повторить загрузку</button>}
  </div>;

  const { days, averages } = data;
  const shiftWeek = (days: number) => new Date(Date.parse(data.period_start + 'T12:00:00Z') + days * 86400000).toISOString().slice(0, 10);
  const omskToday = new Date(Date.now() + 6 * 3600000);
  const currentMonday = new Date(omskToday.getTime() - ((omskToday.getUTCDay() + 6) % 7) * 86400000).toISOString().slice(0, 10);
  const number = (value: number | null, unit = '') => value === null || value === undefined ? '—' : `${Math.round(value)}${unit}`;
  return <div className="space-y-4 pb-32 px-3 pt-3 max-w-4xl mx-auto">
    <section aria-label="Итоги недели" className="bg-[#111726] border border-[#1e293b] rounded-3xl p-5 space-y-4">
      <div className="flex items-center gap-3"><Award className="w-6 h-6 text-[#f59e0b] shrink-0" /><div>
        <h2 className="font-bold text-white">Твоя неделя</h2>
        <p className="text-xs text-[#94a3b8]">{data.period_start} — {data.period_end} · по Омску</p>
      </div></div>
      <div className="flex flex-wrap gap-3 text-xs">
        <button onClick={() => onSelectWeek(shiftWeek(-7))} disabled={isLoading || analyzing || data.period_start <= new Date(Date.now() - 358 * 86400000).toISOString().slice(0, 10)} className="underline disabled:opacity-40">Предыдущая неделя</button>
        <button onClick={() => onSelectWeek(shiftWeek(7))} disabled={isLoading || analyzing || data.period_start >= currentMonday} className="underline disabled:opacity-40">Следующая неделя</button>
        {data.period_start < currentMonday && <button onClick={() => onSelectWeek('')} disabled={isLoading || analyzing} className="text-[#00d084] underline disabled:opacity-40">Текущая неделя</button>}
      </div>
      <p className="text-xs text-[#94a3b8]">Картинка формируется по твоим записям. Текущая неделя обновляется по мере появления данных.</p>
      <button onClick={onRetry} disabled={isLoading} className="text-xs text-[#00d084] underline disabled:opacity-40">{isLoading ? 'Обновляем неделю…' : 'Обновить неделю'}</button>
      {image ? <a href={image} target="_blank" rel="noreferrer" aria-label="Открыть картинку итогов недели"><img src={image} alt={`Итоги недели ${data.period_start} — ${data.period_end}: тренировки, питание и динамика веса`} className="w-full rounded-2xl border border-[#1e293b]" /></a>
        : <p role={imageError ? 'alert' : 'status'} className="text-xs text-[#94a3b8]">{imageError || 'Собираем картинку недели…'}</p>}
      <div className="flex flex-wrap gap-3">
        {image && <a href={image} download={`fitpulse-${start}.png`} className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-[#334155] text-xs"><Download className="w-4 h-4" />Сохранить картинку</a>}
        {imageError && <button onClick={() => setImageRevision(r => r + 1)} className="text-xs underline">Повторить картинку</button>}
        <button onClick={() => void analyze()} disabled={analyzing || isLoading} className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-[#00d084] text-[#0b0f19] text-xs font-semibold disabled:opacity-40"><MessageSquare className="w-4 h-4" />{analyzing ? 'ИИ разбирает неделю…' : 'Обсудить с ИИ'}</button>
      </div>
      {analysisError && <p role="alert" className="text-xs text-rose-300">{analysisError}</p>}
      {!!data.warnings?.length && <p className="text-xs text-amber-300">{data.warnings.join('. ')}</p>}
      {error && <p role="alert" className="text-xs text-rose-300">{error}</p>}
    </section>
    <section aria-label="Показатели недели" className="bg-[#111726] border border-[#1e293b] rounded-3xl p-5 space-y-3">
      <h2 className="text-sm font-bold text-white">Показатели недели</h2>
      <p className="text-xs text-[#94a3b8]">Питание записано за {averages.tracked_days} из 7 дней. Пропуски не считаются нулями.</p>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {[['Ккал / день', number(averages.calories)], ['Белок / день', number(averages.protein, ' г')], ['Тренировки', data.workout_count], ['Вес за неделю', data.weight_change === null ? 'Мало замеров' : `${data.weight_change > 0 ? '+' : ''}${data.weight_change} кг`]].map(([label, value]) => <div key={label} className="bg-[#0b0f19] rounded-2xl p-3"><p className="text-xs text-[#94a3b8]">{label}</p><p className="text-lg font-bold text-[#00d084] mt-1">{value}</p></div>)}
      </div>
    </section>
    <SleepCard weekStart={data.period_start} onDiscuss={() => void analyze('sleep')} />
    <section className="bg-[#111726] border border-[#1e293b] rounded-3xl p-5 space-y-3">
      <h2 className="text-sm font-bold">По дням недели</h2>
      {days.map(day => <div key={day.date} className="bg-[#0b0f19] rounded-2xl p-3 text-xs space-y-1">
        <div className="flex justify-between gap-2"><strong>{day.weekday} · {day.date}</strong><span>{day.is_logged ? `${Math.round(day.calories)} ккал` : '—'}</span></div>
        <p className="text-[#94a3b8]">{day.is_logged ? `Б: ${Math.round(day.protein)} г · Ж: ${Math.round(day.fat)} г · У: ${Math.round(day.carbs)} г` : day.is_future ? 'Этот день впереди' : 'Питание не записано'}</p>
        {!!day.workout_count && <p className="text-[#c4b5fd]">{day.workout_titles.join(', ')} · {day.tonnage_kg} кг</p>}
      </div>)}
    </section>
  </div>;
}
