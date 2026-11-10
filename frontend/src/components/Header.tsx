import React from 'react';
import { Zap, RefreshCw, Bell } from 'lucide-react';
import type { HabitItem } from '../types';

interface HeaderProps {
  compact?: boolean;
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
  compact = false,
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
    <header className={`pulse-header ${compact ? 'is-compact' : ''}`}>
      <div className="pulse-topbar">
        <div className="pulse-brand"><span className="pulse-brand-icon"><Zap size={22} fill="currentColor" /></span><div><h1>FitPulse<span>®</span></h1><p>Твой ритм. Твой прогресс.</p></div></div>
        <div className="pulse-date"><span>{weekdayName}</span><strong>{dateFormatted}</strong></div>
        <div className="pulse-header-actions">
          {onRequestNotificationPermission && <button className="pulse-icon-button" onClick={notificationPermission === 'granted' ? onTestNotification : onRequestNotificationPermission} aria-label="Настройки уведомлений" title="Настройки уведомлений"><Bell size={19} />{notificationPermission === 'granted' && <i />}</button>}
          <button className="pulse-icon-button" onClick={onSync} disabled={isSyncing} aria-label="Синхронизировать Hevy и YAZIO" title="Синхронизировать Hevy и YAZIO"><RefreshCw size={18} className={isSyncing ? 'animate-spin' : ''} /></button>
        </div>
      </div>
      {!compact && <div className="pulse-week" aria-label="Выбор дня недели">
        <span className="pulse-week-caption">ТВОЯ НЕДЕЛЯ<small>Маленькие шаги каждый день</small></span>
        <div className="pulse-days">{days.map(d => <button key={d.key} onClick={() => onSelectDay(d.key)} aria-pressed={selectedDay === d.key} title={d.isToday ? `${d.label} (Сегодня)` : d.label} className={`pulse-day ${selectedDay === d.key ? 'is-selected' : ''} ${d.isToday ? 'is-today' : ''}`}><span>{d.label}</span><strong>{weekDates?.[d.key]?.slice(-2) || '—'}</strong><i className={d.completed ? 'is-complete' : ''} /></button>)}</div>
      </div>}
    </header>
  );
};
