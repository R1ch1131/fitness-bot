import React, { useState } from 'react';
import { CheckCircle2, Flame, Plus, Trash2, ArrowUpRight } from 'lucide-react';
import type { DashboardData, HabitItem } from '../types';

interface DashboardTabProps {
  data: DashboardData | null;
  refreshing?: boolean;
  selectedDay: string;
  todayKey?: string;
  habits: HabitItem[];
  weekDates: Record<string, string>;
  onToggleHabit: (habitId: string, dateStr: string) => void;
  onAddHabit: (title: string, category: string) => void;
  onDeleteHabit: (habitId: string) => void;
  onOpenChat: (query?: string) => void;
  onOpenWeekly: () => void;
}

export const DashboardTab: React.FC<DashboardTabProps> = ({
  data,
  refreshing = false,
  selectedDay,
  todayKey = 'Чт',
  habits,
  weekDates,
  onToggleHabit,
  onAddHabit,
  onDeleteHabit,
  onOpenChat,
  onOpenWeekly,
}) => {
  const [newHabitTitle, setNewHabitTitle] = useState('');
  const [newHabitCategory, setNewHabitCategory] = useState('Спорт');

  const selectedDateStr = weekDates[selectedDay] || '';

  // 1. Calculate today's / selected day's habit metrics
  const totalHabits = habits.length;
  const completedToday = habits.filter(h => !!h.history[selectedDateStr]).length;
  const todayPercent = totalHabits > 0 ? Math.round((completedToday / totalHabits) * 100) : 0;

  // 2. Calculate Weekly Execution % across all habits
  let totalOpportunities = 0;
  let totalDoneThisWeek = 0;
  Object.values(weekDates).forEach(dStr => {
    habits.forEach(h => {
      totalOpportunities += 1;
      if (h.history[dStr]) {
        totalDoneThisWeek += 1;
      }
    });
  });
  const weeklyExecutionPercent = totalOpportunities > 0
    ? Math.round((totalDoneThisWeek / totalOpportunities) * 100)
    : 0;

  const handleAddHabitSubmit = () => {
    if (!newHabitTitle.trim()) return;
    onAddHabit(newHabitTitle.trim(), newHabitCategory);
    setNewHabitTitle('');
  };

  const allDays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

  return (
    <div className="pulse-dashboard habits-dashboard">
      <div className="habits-heading"><div><h2>Мои привычки</h2><p>Отмечай сделанное — вся неделя перед тобой.</p></div><button onClick={() => onOpenChat()} aria-label="Обсудить привычки с тренером">AI-тренер <ArrowUpRight size={15} /></button></div>
      {/* 4. REAL DYNAMIC HABIT MATRIX */}
      <div className="pulse-panel pulse-habits bg-[#19221f] border border-[#33473b] rounded-3xl p-5 space-y-4">
        <div className="habits-summary" aria-label="Сводка привычек"><div><h3>{selectedDay === todayKey ? 'Сегодня' : selectedDay} <span>{selectedDateStr.slice(8)}.{selectedDateStr.slice(5,7)}</span></h3><strong>{completedToday}<small> / {totalHabits} выполнено</small></strong></div><div className="habits-summary-week"><span>За неделю</span><strong>{totalDoneThisWeek}<small> / {totalOpportunities} отметок · {weeklyExecutionPercent}%</small></strong></div><div className="habits-summary-bar" role="progressbar" aria-label="Выполнение привычек выбранного дня" aria-valuemin={0} aria-valuemax={100} aria-valuenow={todayPercent}><i style={{width: `${todayPercent}%`}} /></div></div>
        {/* Habits List */}
        <div className="pulse-habit-list space-y-3 pt-2">
          {!habits.length && <p className="text-sm text-[#a4b8aa]">Пока нет привычек. Добавь первую ниже.</p>}
          {habits.map((habit) => {
            const isCheckedForSelectedDay = !!habit.history[selectedDateStr];

            return (
              <div
                key={habit.id}
                className="bg-[#1d2822] border border-[#33473b] rounded-2xl p-3.5 space-y-3 transition-all hover:border-[#33473b]"
              >
                {/* Habit Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <button
                      aria-label={`Отметить привычку: ${habit.title}`}
                      aria-pressed={isCheckedForSelectedDay}
                      onClick={() => onToggleHabit(habit.id, selectedDateStr)}
                      className={`w-7 h-7 rounded-xl flex items-center justify-center transition-all ${
                        isCheckedForSelectedDay
                          ? 'bg-[#79c5a6] text-[#10261b] shadow-md shadow-[#218d79]/30'
                          : 'bg-[#2a3b30] text-zinc-500 hover:text-[#e6eee8]'
                      }`}
                    >
                      <CheckCircle2 className="w-4 h-4" />
                    </button>
                    <div>
                      <h3 className="text-sm font-bold text-[#e6eee8] tracking-tight">{habit.title}</h3>
                      <div className="flex items-center space-x-2 text-[11px] text-[#a4b8aa] mt-0.5">
                        <span className="bg-[#33473b] text-zinc-300 px-2 py-0.5 rounded-md font-medium">
                          {habit.category}
                        </span>
                        <span>План: {habit.target_days || 7} дн./нед</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-1.5 text-zinc-500">
                    <button
                      onClick={() => onDeleteHabit(habit.id)}
                      className="p-1 hover:text-[#e1949c] transition-colors"
                      title="Удалить"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Day Buttons Grid (7 Days) */}
                <div className="grid grid-cols-7 gap-1.5">
                  {allDays.map((d) => {
                    const dateForDay = weekDates[d];
                    const isChecked = !!habit.history[dateForDay];
                    const isSelectedDay = selectedDay === d;
                    const isToday = d === todayKey;

                    return (
                      <button
                        key={d}
                        aria-label={`${habit.title}: ${d}`}
                        aria-pressed={isChecked}
                        onClick={() => onToggleHabit(habit.id, dateForDay)}
                        title={isToday ? `${d} (Сегодня)` : d}
                        className={`relative h-9 rounded-xl flex flex-col items-center justify-center text-xs font-bold transition-all ${
                          isChecked && isSelectedDay
                            ? 'bg-[#79c5a6] text-[#10261b] shadow-md shadow-[#218d79]/25 scale-[1.02]'
                            : isChecked
                            ? 'bg-[#3c3027] text-[#dcaf89] border border-[#4338ca]/40'
                            : isSelectedDay
                            ? 'bg-[#2a3b30] text-[#e6eee8] border border-[#79c5a6]/40'
                            : 'bg-[#19221f] text-[#91a797] hover:text-[#e6eee8] hover:bg-[#2a3b30]'
                        } ${isToday && !isSelectedDay ? 'ring-1 ring-[#218d79]/40' : ''}`}
                      >
                        <span className="text-[10px] opacity-75">{d}</span>
                        {isChecked ? (
                          <span className="text-xs">✓</span>
                        ) : (
                          <span className="text-[10px] opacity-30">•</span>
                        )}
                        {isToday && (
                          <span
                            className={`absolute bottom-0.5 w-1 h-1 rounded-full ${
                              isChecked && isSelectedDay ? 'bg-[#101714]' : 'bg-[#79c5a6]'
                            }`}
                          />
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* Streak Pill */}
                <div className="flex items-center justify-between text-xs pt-1">
                  <div className="flex items-center space-x-1.5 bg-[#b57935]/10 text-[#d7ad76] border border-[#d7ad76]/30 px-2.5 py-1 rounded-xl font-bold">
                    <Flame className="w-3.5 h-3.5 fill-[#d7ad76]" />
                    <span>
                      {habit.current_streak > 0 ? `${habit.current_streak} дней` : '0 дней (старт)'}
                    </span>
                  </div>
                  <span className="text-[11px] text-[#91a797]">
                    Рекорд: {habit.record_streak || 0} дн.
                  </span>
                </div>
              </div>
            );
          })}
        </div>
        <details className="habit-add"><summary><Plus size={16} /> Добавить привычку</summary>
        {/* Input Add Habit Bar */}
        <div className="flex flex-col sm:flex-row gap-2 pt-1">
          <input
            type="text"
            placeholder="Новая цель / тренировка (напр. Растяжка 15 мин)"
            value={newHabitTitle}
            onChange={(e) => setNewHabitTitle(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAddHabitSubmit()}
            className="flex-1 bg-[#101714] border border-[#33473b] rounded-2xl px-3.5 py-2 text-xs text-[#e6eee8] placeholder-[#91a797] focus:outline-none focus:border-[#79c5a6]"
          />
          <select
            value={newHabitCategory}
            onChange={(e) => setNewHabitCategory(e.target.value)}
            className="bg-[#101714] border border-[#33473b] rounded-2xl px-3 py-2 text-xs text-[#e6eee8] focus:outline-none focus:border-[#79c5a6]"
          >
            <option value="Спорт">Спорт</option>
            <option value="Питание">Питание</option>
            <option value="Учеба / Код">Учеба / Код</option>
            <option value="Чтение">Чтение</option>
            <option value="Режим">Режим</option>
          </select>
          <button
            onClick={handleAddHabitSubmit}
            className="bg-[#79c5a6] hover:bg-[#90d4b8] active:scale-95 text-[#10261b] font-bold text-xs px-4 py-2 rounded-2xl transition-all flex items-center justify-center space-x-1.5 shadow-md shadow-[#218d79]/20"
          >
            <Plus className="w-4 h-4" />
            <span>Добавить</span>
          </button>
        </div>

        </details>

      </div>
      <div className="habits-footer"><span>{data ? `Данные на ${data.time || '—'}${refreshing ? ' · Обновляем…' : ''}` : 'Загружаем данные…'}</span><button onClick={onOpenWeekly}>Итоги недели <ArrowUpRight size={14} /></button></div>
    </div>
  );
};
