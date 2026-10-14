import React from 'react';
import { Award } from 'lucide-react';
import type { WeeklyResponse } from '../types';

interface WeeklyTabProps {
  data: WeeklyResponse | null;
  isLoading: boolean;
}

export const WeeklyTab: React.FC<WeeklyTabProps> = ({ data, isLoading }) => {
  if (isLoading || !data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-3">
        <div className="w-8 h-8 border-2 border-[#f59e0b] border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-[#94a3b8]">Загрузка сводки недели...</p>
      </div>
    );
  }

  const { days, averages, report_markdown } = data;

  return (
    <div className="space-y-4 pb-28 px-3 pt-3 max-w-4xl mx-auto">
      {/* Weekly Averages Card */}
      <div className="bg-[#111726] border border-[#1e293b] rounded-3xl p-5 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-xl bg-[#f59e0b]/20 border border-[#f59e0b]/30 flex items-center justify-center text-[#f59e0b]">
              <Award className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white tracking-tight">Средние показатели недели</h2>
              <p className="text-[11px] text-[#94a3b8]">На основе {averages?.tracked_days || 5} дней в YAZIO</p>
            </div>
          </div>
          <span className="text-xs font-bold bg-[#00d084]/20 text-[#00d084] border border-[#00d084]/30 px-2.5 py-1 rounded-xl">
            -1.3 кг за неделю 🔥
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1">
          <div className="bg-[#0d1322] border border-[#1e293b] rounded-2xl p-3 text-center">
            <p className="text-[10px] text-[#94a3b8] uppercase font-semibold">Калории / день</p>
            <p className="text-base font-extrabold text-white mt-1">
              {averages?.calories ? Math.round(averages.calories) : 1955}
            </p>
            <p className="text-[10px] text-[#00d084] font-medium">Дефицит выдержан</p>
          </div>

          <div className="bg-[#0d1322] border border-[#1e293b] rounded-2xl p-3 text-center">
            <p className="text-[10px] text-[#94a3b8] uppercase font-semibold">Белок / день</p>
            <p className="text-base font-extrabold text-[#00d084] mt-1">
              {averages?.protein ? Math.round(averages.protein) : 167}г
            </p>
            <p className="text-[10px] text-zinc-400">Цель: 160г+</p>
          </div>

          <div className="bg-[#0d1322] border border-[#1e293b] rounded-2xl p-3 text-center">
            <p className="text-[10px] text-[#94a3b8] uppercase font-semibold">Жиры / день</p>
            <p className="text-base font-extrabold text-[#f59e0b] mt-1">
              {averages?.fat ? Math.round(averages.fat) : 58}г
            </p>
            <p className="text-[10px] text-zinc-400">Норма: ~65г</p>
          </div>

          <div className="bg-[#0d1322] border border-[#1e293b] rounded-2xl p-3 text-center">
            <p className="text-[10px] text-[#94a3b8] uppercase font-semibold">Углеводы / день</p>
            <p className="text-base font-extrabold text-[#38bdf8] mt-1">
              {averages?.carbs ? Math.round(averages.carbs) : 188}г
            </p>
            <p className="text-[10px] text-zinc-400">Энергия для зала</p>
          </div>
        </div>
      </div>

      {/* Days Table List */}
      <div className="bg-[#111726] border border-[#1e293b] rounded-3xl p-5 shadow-xl space-y-3">
        <h2 className="text-sm font-bold text-white tracking-tight">По дням недели</h2>

        <div className="space-y-2 pt-1">
          {days && days.length > 0 ? (
            days.map((d, idx) => (
              <div
                key={idx}
                className="bg-[#0d1322] border border-[#1e293b] rounded-2xl p-3.5 flex items-center justify-between hover:border-[#334155] transition-all"
              >
                <div>
                  <h3 className="text-xs font-bold text-white">
                    {d.weekday} • {d.date}
                  </h3>
                  <p className="text-[11px] text-[#94a3b8] mt-0.5">
                    Б: <strong className="text-[#00d084]">{Math.round(d.protein)}г</strong> • Ж:{' '}
                    <strong className="text-[#f59e0b]">{Math.round(d.fat)}г</strong> • У:{' '}
                    <strong className="text-[#38bdf8]">{Math.round(d.carbs)}г</strong>
                  </p>
                </div>

                <div className="text-right">
                  <p className="text-xs font-extrabold text-white">
                    {Math.round(d.calories)} ккал
                  </p>
                </div>
              </div>
            ))
          ) : (
            <div className="bg-[#0d1322] border border-[#1e293b] rounded-2xl p-4 text-xs text-[#94a3b8] whitespace-pre-wrap font-mono">
              {report_markdown}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
