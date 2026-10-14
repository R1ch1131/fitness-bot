import React from 'react';
import { Zap, RefreshCw, LayoutDashboard, Dumbbell, MessageSquare, Calendar } from 'lucide-react';
import type { TabType } from './BottomNav';

interface HeaderProps {
  currentTab: TabType;
  onTabChange: (tab: TabType) => void;
  selectedDay: string;
  onSelectDay: (day: string) => void;
  isSyncing: boolean;
  onSync: () => void;
  weightInfo?: { current: number; lost: number };
}

export const Header: React.FC<HeaderProps> = ({
  currentTab,
  onTabChange,
  selectedDay,
  onSelectDay,
  isSyncing,
  onSync,
}) => {
  const days = [
    { key: 'Пн', label: 'Пн', completed: true },
    { key: 'Вт', label: 'Вт', completed: true },
    { key: 'Ср', label: 'Ср', completed: false, isToday: true },
    { key: 'Чт', label: 'Чт', completed: false },
    { key: 'Пт', label: 'Пт', completed: false },
    { key: 'Сб', label: 'Сб', completed: false },
    { key: 'Вс', label: 'Вс', completed: false },
  ];

  return (
    <header className="sticky top-0 z-40 bg-[#0b0f19]/90 backdrop-blur-xl border-b border-[#1e293b] pt-safe px-4 pb-3 space-y-3">
      {/* Top Branding Row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-2xl bg-[#111726] border border-[#00d084]/40 flex items-center justify-center text-[#00d084] shadow-lg shadow-[#00d084]/15">
            <Zap className="w-5 h-5 fill-[#00d084]" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold text-white tracking-tight">FitPulse</h1>
              <span className="text-[10px] font-bold bg-[#00d084] text-[#0b0f19] px-2 py-0.5 rounded-full uppercase tracking-wider">
                HEVY • YAZIO
              </span>
            </div>
            <p className="text-xs text-[#94a3b8] font-normal">
              Система спортивного прогресса и питания
            </p>
          </div>
        </div>

        {/* Focus Day Selector Pills */}
        <div className="hidden sm:flex items-center space-x-1.5 bg-[#111726] border border-[#1e293b] px-2.5 py-1 rounded-2xl">
          <span className="text-[11px] text-[#94a3b8] font-medium mr-1">Фокус дня:</span>
          {days.map((d) => {
            const isSelected = selectedDay === d.key;
            return (
              <button
                key={d.key}
                onClick={() => onSelectDay(d.key)}
                className={`w-7 h-7 rounded-xl text-xs font-bold transition-all flex items-center justify-center ${
                  isSelected
                    ? 'bg-[#00d084] text-[#0b0f19] shadow-md shadow-[#00d084]/20 scale-105'
                    : d.completed
                    ? 'bg-[#25224d] text-[#a5b4fc] hover:bg-[#312e81]'
                    : 'text-[#64748b] hover:text-[#94a3b8] hover:bg-[#131b2e]'
                }`}
              >
                {d.label}
              </button>
            );
          })}
        </div>

        {/* Sync Button */}
        <button
          onClick={onSync}
          disabled={isSyncing}
          className="w-9 h-9 rounded-2xl bg-[#111726] border border-[#1e293b] flex items-center justify-center text-[#94a3b8] hover:text-white hover:border-[#00d084]/50 active:scale-95 transition-all"
        >
          <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin text-[#00d084]' : ''}`} />
        </button>
      </div>

      {/* Mobile Day Selector Row (Visible on phones) */}
      <div className="flex sm:hidden items-center justify-between bg-[#111726] border border-[#1e293b] px-3 py-1.5 rounded-2xl">
        <span className="text-[11px] text-[#94a3b8] font-medium">Фокус дня:</span>
        <div className="flex items-center space-x-1">
          {days.map((d) => {
            const isSelected = selectedDay === d.key;
            return (
              <button
                key={d.key}
                onClick={() => onSelectDay(d.key)}
                className={`w-7 h-7 rounded-xl text-xs font-bold transition-all flex items-center justify-center ${
                  isSelected
                    ? 'bg-[#00d084] text-[#0b0f19] shadow-md shadow-[#00d084]/20 scale-105'
                    : d.completed
                    ? 'bg-[#25224d] text-[#a5b4fc]'
                    : 'text-[#64748b] hover:text-[#94a3b8]'
                }`}
              >
                {d.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Top Nav Pills */}
      <div className="flex items-center space-x-2 overflow-x-auto pb-0.5 no-scrollbar">
        <button
          onClick={() => onTabChange('dashboard')}
          className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all ${
            currentTab === 'dashboard'
              ? 'bg-[#1e293b] text-white border border-[#334155]'
              : 'text-[#94a3b8] hover:text-white hover:bg-[#111726]'
          }`}
        >
          <LayoutDashboard className="w-3.5 h-3.5" />
          <span>Дашборд</span>
        </button>

        <button
          onClick={() => onTabChange('chat')}
          className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all ${
            currentTab === 'chat'
              ? 'bg-[#1e293b] text-white border border-[#334155]'
              : 'text-[#94a3b8] hover:text-white hover:bg-[#111726]'
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5 text-[#00d084]" />
          <span>AI Тренер</span>
        </button>

        <button
          onClick={() => onTabChange('workouts')}
          className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all ${
            currentTab === 'workouts'
              ? 'bg-[#1e293b] text-white border border-[#334155]'
              : 'text-[#94a3b8] hover:text-white hover:bg-[#111726]'
          }`}
        >
          <Dumbbell className="w-3.5 h-3.5 text-[#6366f1]" />
          <span>Hevy Сплит</span>
        </button>

        <button
          onClick={() => onTabChange('weekly')}
          className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all ${
            currentTab === 'weekly'
              ? 'bg-[#1e293b] text-white border border-[#334155]'
              : 'text-[#94a3b8] hover:text-white hover:bg-[#111726]'
          }`}
        >
          <Calendar className="w-3.5 h-3.5 text-[#f59e0b]" />
          <span>Сводка Недели</span>
        </button>
      </div>
    </header>
  );
};
