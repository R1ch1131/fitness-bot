import React, { useState } from 'react';
import { Dumbbell, Calendar, ChevronDown, ChevronRight, CheckCircle2, Layers } from 'lucide-react';
import type { WorkoutsResponse } from '../types';

interface WorkoutsTabProps {
  data: WorkoutsResponse | null;
  isLoading: boolean;
}

export const WorkoutsTab: React.FC<WorkoutsTabProps> = ({ data, isLoading }) => {
  const [expandedRoutine, setExpandedRoutine] = useState<string | null>(null);

  if (isLoading || !data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-3">
        <div className="w-8 h-8 border-2 border-[#6366f1] border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-[#94a3b8]">Загрузка тренировок из Hevy...</p>
      </div>
    );
  }

  const { workouts, routines } = data;

  return (
    <div className="space-y-4 pb-28 px-3 pt-3 max-w-4xl mx-auto">
      {/* Split Routines Section */}
      <div className="bg-[#111726] border border-[#1e293b] rounded-3xl p-5 shadow-xl space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-xl bg-[#6366f1]/20 border border-[#6366f1]/30 flex items-center justify-center text-[#818cf8]">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white tracking-tight">Твой 5-дневный сплит Hevy</h2>
              <p className="text-[11px] text-[#94a3b8]">Программы тренировок с прогрессией нагрузки</p>
            </div>
          </div>
          <span className="text-xs font-bold bg-[#1e293b] text-[#c7d2fe] px-2.5 py-1 rounded-xl">
            {routines.length} программ
          </span>
        </div>

        <div className="space-y-2 pt-1">
          {routines.map((routine) => {
            const isExpanded = expandedRoutine === routine.id;

            return (
              <div
                key={routine.id}
                className="bg-[#0d1322] border border-[#1e293b] rounded-2xl overflow-hidden transition-all hover:border-[#334155]"
              >
                <button
                  onClick={() => setExpandedRoutine(isExpanded ? null : routine.id)}
                  className="w-full flex items-center justify-between p-3.5 text-left active:bg-[#111726]"
                >
                  <div className="flex items-center space-x-2.5">
                    <div className="w-7 h-7 rounded-lg bg-[#25224d] flex items-center justify-center text-[#a5b4fc]">
                      <Dumbbell className="w-3.5 h-3.5" />
                    </div>
                    <div>
                      <h3 className="text-xs font-bold text-white">{routine.title}</h3>
                      <p className="text-[10px] text-[#94a3b8]">
                        Упражнений: {routine.exercises.length}
                      </p>
                    </div>
                  </div>
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-zinc-400" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-zinc-400" />
                  )}
                </button>

                {isExpanded && (
                  <div className="px-3.5 pb-3.5 pt-1 space-y-1.5 border-t border-[#1e293b]">
                    {routine.exercises.map((ex, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between text-xs py-1 border-b border-[#1b2338] last:border-none"
                      >
                        <span className="text-zinc-200 font-medium text-xs leading-snug flex-1 pr-3">
                          {ex.title}
                        </span>
                        <span className="text-[#a5b4fc] font-mono text-[11px] shrink-0 bg-[#161f36] px-2 py-0.5 rounded-lg border border-[#1e293b]">
                          {ex.sets_count} подходов
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Completed Workouts History */}
      <div className="bg-[#111726] border border-[#1e293b] rounded-3xl p-5 shadow-xl space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-xl bg-[#00d084]/20 border border-[#00d084]/30 flex items-center justify-center text-[#00d084]">
              <CheckCircle2 className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white tracking-tight">История тренировок</h2>
              <p className="text-[11px] text-[#94a3b8]">Последние завершенные сессии из Hevy</p>
            </div>
          </div>
        </div>

        <div className="space-y-2 pt-1">
          {workouts.slice(0, 10).map((w, idx) => (
            <div
              key={idx}
              className="bg-[#0d1322] border border-[#1e293b] rounded-2xl p-3.5 flex items-center justify-between hover:border-[#334155] transition-all"
            >
              <div className="space-y-0.5">
                <h3 className="text-xs font-bold text-white">{w.title}</h3>
                <p className="text-[10px] text-[#94a3b8] flex items-center space-x-1">
                  <Calendar className="w-3 h-3 inline mr-1" />
                  <span>{w.date}</span>
                </p>
              </div>

              <div className="text-right">
                <p className="text-xs font-bold text-[#00d084]">
                  {(w.total_tonnage_kg / 1000).toFixed(1)} т
                </p>
                <p className="text-[10px] text-[#94a3b8]">{w.total_working_sets} подходов</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
