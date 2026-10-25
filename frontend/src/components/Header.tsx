import React from 'react';
import { Zap, RefreshCw, Bell, BellRing } from 'lucide-react';
import type { HabitItem } from '../types';

interface HeaderProps {
  selectedDay: string;
  onSelectDay: (day: string) => void;
  todayKey?: string;
  dateFormatted?: string;
  weekdayName?: string;
  weekDates?: Record<string, string>;
  habits?: HabitItem[];
  notificationPermission?: NotificationPermission;
  onRequestNotificationPermission?: () => void;
  onTestNotification?: () => void;
  isSyncing: boolean;
  onSync: () => void;
  weightInfo?: { current: number; lost: number };
}

export const Header: React.FC<HeaderProps> = ({
  selectedDay,
  onSelectDay,
  todayKey = 'Чт',
  dateFormatted,
  weekdayName,
  weekDates,
  habits,
  notificationPermission,
  onRequestNotificationPermission,
  onTestNotification,
  isSyncing,
  onSync,
}) => {
  const dayKeys = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
  const days = dayKeys.map((key) => {
    const isToday = key === todayKey;
    const dateStr = weekDates?.[key];
    const isCompleted = habits && habits.length > 0 && dateStr
      ? habits.some(h => !!h.history[dateStr])
      : false;

    return {
      key,
      label: key,
      completed: isCompleted,
      isToday,
    };
  });

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
            <p className="text-xs text-[#94a3b8] font-normal flex flex-wrap items-center gap-x-1.5">
              <span>Система спортивного прогресса</span>
              {weekdayName && (
                <>
                  <span className="text-[#64748b]">•</span>
                  <span className="text-[#00d084] font-semibold">{weekdayName}</span>
                </>
              )}
              {dateFormatted && (
                <span className="text-zinc-400 font-medium">({dateFormatted})</span>
              )}
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
                title={d.isToday ? `${d.label} (Сегодня)` : d.label}
                className={`relative w-7 h-7 rounded-xl text-xs font-bold transition-all flex flex-col items-center justify-center ${
                  isSelected
                    ? 'bg-[#00d084] text-[#0b0f19] shadow-md shadow-[#00d084]/20 scale-105'
                    : d.completed
                    ? 'bg-[#25224d] text-[#a5b4fc] hover:bg-[#312e81]'
                    : 'text-[#64748b] hover:text-[#94a3b8] hover:bg-[#131b2e]'
                } ${d.isToday && !isSelected ? 'ring-1 ring-[#00d084]/60 text-white' : ''}`}
              >
                <span>{d.label}</span>
                {d.isToday && (
                  <span
                    className={`absolute bottom-0.5 w-1 h-1 rounded-full ${
                      isSelected ? 'bg-[#0b0f19]' : 'bg-[#00d084]'
                    }`}
                  />
                )}
              </button>
            );
          })}
        </div>

        {/* Action Buttons: Notification Bell + Sync Button */}
        <div className="flex items-center space-x-1.5">
          {onRequestNotificationPermission && (
            <button
              onClick={notificationPermission === 'granted' ? onTestNotification : onRequestNotificationPermission}
              aria-label="Настройки уведомлений"
              title={
                notificationPermission === 'granted'
                  ? 'Уведомления подключены — настройки и тест'
                  : 'Включить уведомления о тренировках'
              }
              className={`w-9 h-9 rounded-2xl bg-[#111726] border flex items-center justify-center active:scale-95 transition-all relative ${
                notificationPermission === 'granted'
                  ? 'border-[#00d084]/40 text-[#00d084] hover:bg-[#00d084]/10'
                  : 'border-[#f59e0b]/40 text-[#f59e0b] hover:bg-[#f59e0b]/10'
              }`}
            >
              {notificationPermission === 'granted' ? (
                <Bell className="w-4 h-4 fill-[#00d084]/20" />
              ) : (
                <>
                  <BellRing className="w-4 h-4 animate-bounce" />
                  <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[#f59e0b] animate-ping" />
                </>
              )}
            </button>
          )}

          <button
            onClick={onSync}
            disabled={isSyncing}
            className="w-9 h-9 rounded-2xl bg-[#111726] border border-[#1e293b] flex items-center justify-center text-[#94a3b8] hover:text-white hover:border-[#00d084]/50 active:scale-95 transition-all"
            title="Синхронизировать Hevy и YAZIO"
          >
            <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin text-[#00d084]' : ''}`} />
          </button>
        </div>
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
                title={d.isToday ? `${d.label} (Сегодня)` : d.label}
                className={`relative w-7 h-7 rounded-xl text-xs font-bold transition-all flex flex-col items-center justify-center ${
                  isSelected
                    ? 'bg-[#00d084] text-[#0b0f19] shadow-md shadow-[#00d084]/20 scale-105'
                    : d.completed
                    ? 'bg-[#25224d] text-[#a5b4fc]'
                    : 'text-[#64748b] hover:text-[#94a3b8]'
                } ${d.isToday && !isSelected ? 'ring-1 ring-[#00d084]/60 text-white' : ''}`}
              >
                <span>{d.label}</span>
                {d.isToday && (
                  <span
                    className={`absolute bottom-0.5 w-1 h-1 rounded-full ${
                      isSelected ? 'bg-[#0b0f19]' : 'bg-[#00d084]'
                    }`}
                  />
                )}
              </button>
            );
          })}
        </div>
      </div>
    </header>
  );
};
