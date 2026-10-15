import React, { useState } from 'react';
import { 
  CheckCircle2, 
  TrendingUp, 
  Flame, 
  Layers, 
  Dumbbell, 
  Utensils, 
  Code, 
  BookOpen, 
  Moon, 
  Plus, 
  Trash2
} from 'lucide-react';
import type { DashboardData, HabitItem } from '../types';

interface DashboardTabProps {
  data: DashboardData | null;
  selectedDay: string;
  todayKey?: string;
  habits: HabitItem[];
  weekDates: Record<string, string>;
  onToggleHabit: (habitId: string, dateStr: string) => void;
  onAddHabit: (title: string, category: string) => void;
  onDeleteHabit: (habitId: string) => void;
  onOpenChat: (query?: string) => void;
  onOpenWorkouts: () => void;
}

export const DashboardTab: React.FC<DashboardTabProps> = ({
  data,
  selectedDay,
  todayKey = 'Чт',
  habits,
  weekDates,
  onToggleHabit,
  onAddHabit,
  onDeleteHabit,
  onOpenChat,
  onOpenWorkouts,
}) => {
  const [chartMode, setChartMode] = useState<'combo' | 'curve' | 'bars'>('combo');
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

  // 3. Find highest active streak habit
  const topStreakHabit = habits.reduce((top, h) => {
    return h.current_streak > (top?.current_streak || 0) ? h : top;
  }, habits[0] || null);

  // 4. Calculate balance by spheres for this week
  const spheres = [
    { key: 'Спорт', label: 'Спорт', icon: Dumbbell, color: '#00d084' },
    { key: 'Питание', label: 'Питание', icon: Utensils, color: '#f59e0b' },
    { key: 'Учеба / Код', label: 'Учеба / Код', icon: Code, color: '#a855f7' },
    { key: 'Чтение', label: 'Чтение', icon: BookOpen, color: '#06b6d4' },
    { key: 'Режим', label: 'Режим', icon: Moon, color: '#f43f5e' },
  ];

  const sphereStats = spheres.map(sph => {
    const sphHabits = habits.filter(h => h.category === sph.key);
    let done = 0;
    let total = sphHabits.length * 7;
    Object.values(weekDates).forEach(dStr => {
      sphHabits.forEach(h => {
        if (h.history[dStr]) done += 1;
      });
    });
    const percent = total > 0 ? Math.round((done / total) * 100) : 0;
    return { ...sph, done, total: total || 7, percent };
  });

  const handleAddHabitSubmit = () => {
    if (!newHabitTitle.trim()) return;
    onAddHabit(newHabitTitle.trim(), newHabitCategory);
    setNewHabitTitle('');
  };

  const allDays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

  // Days completion counts for the chart
  const dayStats = allDays.map(dKey => {
    const dStr = weekDates[dKey];
    const done = habits.filter(h => !!h.history[dStr]).length;
    const pct = totalHabits > 0 ? Math.round((done / totalHabits) * 100) : 0;
    return { day: dKey, date: dStr, done, pct };
  });

  const bestDay = dayStats.reduce((best, cur) => cur.pct > best.pct ? cur : best, dayStats[0]);

  return (
    <div className="space-y-4 pb-28 px-3 pt-3 max-w-5xl mx-auto">
      {/* 1. TOP 4 KPI METRIC CARDS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Card 1: Сегодня / Фокус дня */}
        <div 
          onClick={() => onOpenChat(selectedDay === todayKey ? `Как успехи по целям на сегодня (${todayKey})?` : `Как успехи по целям на день (${selectedDay})?`)}
          className="bg-[#111726] border border-[#1e293b] hover:border-[#00d084]/40 cursor-pointer rounded-3xl p-4 flex flex-col justify-between shadow-lg relative overflow-hidden transition-all"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-[#94a3b8] uppercase tracking-wider flex items-center space-x-1.5">
              <span>📅 {selectedDay === todayKey ? `Сегодня (${todayKey})` : `Фокус: ${selectedDay}`}</span>
              {selectedDay !== todayKey && (
                <span className="text-[9px] bg-[#1e293b] text-[#00d084] border border-[#00d084]/30 px-1.5 py-0.5 rounded font-bold">
                  (Сегодня: {todayKey})
                </span>
              )}
            </span>
            <div className="w-8 h-8 rounded-xl bg-[#00d084]/10 border border-[#00d084]/20 flex items-center justify-center text-[#00d084]">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="my-3">
            <div className="flex items-baseline space-x-2">
              <span className="text-3xl font-extrabold text-white tracking-tight">{todayPercent}%</span>
              <span className="text-xs text-[#94a3b8] font-medium">
                ({completedToday} из {totalHabits})
              </span>
            </div>
            <div className="h-2 w-full bg-[#1b2338] rounded-full mt-2.5 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-[#00d084] to-[#06b6d4] rounded-full transition-all duration-500"
                style={{ width: `${todayPercent}%` }}
              />
            </div>
          </div>
        </div>

        {/* Card 2: Weekly Execution */}
        <div className="bg-[#111726] border border-[#1e293b] rounded-3xl p-4 flex flex-col justify-between shadow-lg relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-[#94a3b8] uppercase tracking-wider">
              🎯 Weekly Execution
            </span>
            <div className="w-8 h-8 rounded-xl bg-[#6366f1]/10 border border-[#6366f1]/20 flex items-center justify-center text-[#6366f1]">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div className="my-3">
            <div className="flex items-center space-x-2">
              <span className="text-3xl font-extrabold text-white tracking-tight">
                {weeklyExecutionPercent}%
              </span>
              <span className="text-[11px] font-bold bg-[#f59e0b]/20 text-[#f59e0b] border border-[#f59e0b]/30 px-2 py-0.5 rounded-lg">
                {weeklyExecutionPercent >= 80 ? 'В топе! 🔥' : 'Поднажать до 85%'}
              </span>
            </div>
            <div className="h-2 w-full bg-[#1b2338] rounded-full mt-2.5 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-[#6366f1] to-[#a855f7] rounded-full transition-all duration-500"
                style={{ width: `${weeklyExecutionPercent}%` }}
              />
            </div>
          </div>
        </div>

        {/* Card 3: Активный стрик */}
        <div 
          onClick={() => onOpenChat()}
          className="bg-[#111726] border border-[#1e293b] hover:border-[#f59e0b]/40 cursor-pointer rounded-3xl p-4 flex flex-col justify-between shadow-lg relative overflow-hidden transition-all"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-[#94a3b8] uppercase tracking-wider">
              🔥 Активный стрик
            </span>
            <div className="w-8 h-8 rounded-xl bg-[#f59e0b]/10 border border-[#f59e0b]/20 flex items-center justify-center text-[#f59e0b]">
              <Flame className="w-4 h-4 fill-[#f59e0b]" />
            </div>
          </div>
          <div className="my-3">
            <div className="flex items-baseline space-x-2">
              <span className="text-3xl font-extrabold text-white tracking-tight">
                {topStreakHabit ? `${topStreakHabit.current_streak} дн.` : '0 дней'}
              </span>
              <span className="text-xs text-[#94a3b8] font-medium">
                Рекорд: {topStreakHabit?.record_streak || 0} дн.
              </span>
            </div>
            <p className="text-[11px] text-[#94a3b8] mt-1 truncate">
              Лидер: <strong className="text-zinc-200">{topStreakHabit?.title || 'Привычки'}</strong>
            </p>
          </div>
        </div>

        {/* Card 4: Объем за неделю */}
        <div 
          onClick={() => onOpenWorkouts()}
          className="bg-[#111726] border border-[#1e293b] hover:border-[#06b6d4]/40 cursor-pointer rounded-3xl p-4 flex flex-col justify-between shadow-lg relative overflow-hidden transition-all"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-[#94a3b8] uppercase tracking-wider">
              🏋️ Объем в Hevy
            </span>
            <div className="w-8 h-8 rounded-xl bg-[#06b6d4]/10 border border-[#06b6d4]/20 flex items-center justify-center text-[#06b6d4]">
              <Layers className="w-4 h-4" />
            </div>
          </div>
          <div className="my-3">
            <div className="flex items-baseline space-x-2">
              <span className="text-3xl font-extrabold text-white tracking-tight">
                {data?.workout?.today_workout ? (data.workout.today_workout.total_tonnage_kg / 1000).toFixed(1) : '14.0'} т
              </span>
              <span className="text-xs text-[#94a3b8] font-medium">за 2 дня</span>
            </div>
            <p className="text-[11px] text-[#94a3b8] mt-1">
              Активных тренировок в сплите: <strong className="text-zinc-200">5</strong>
            </p>
          </div>
        </div>
      </div>

      {/* 2. DYNAMIC TREND CHART */}
      <div className="bg-[#111726] border border-[#1e293b] rounded-3xl p-5 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-base font-bold text-white tracking-tight">
                Динамика серий и целей за неделю
              </h2>
              <span className="text-[10px] font-bold bg-[#00d084]/20 text-[#00d084] border border-[#00d084]/30 px-2 py-0.5 rounded-full uppercase tracking-wider">
                Live
              </span>
            </div>
            <p className="text-xs text-[#94a3b8] mt-0.5">
              Процент выполнения по дням с целевым ориентиром 85% (метод 12-Week Year)
            </p>
          </div>

          <div className="flex items-center space-x-1 bg-[#0b0f19] border border-[#1e293b] p-1 rounded-2xl self-start sm:self-auto">
            <button
              onClick={() => setChartMode('combo')}
              className={`px-3 py-1 rounded-xl text-xs font-semibold transition-all ${
                chartMode === 'combo' ? 'bg-[#6366f1] text-white shadow-md' : 'text-[#94a3b8] hover:text-white'
              }`}
            >
              Комбо
            </button>
            <button
              onClick={() => setChartMode('curve')}
              className={`px-3 py-1 rounded-xl text-xs font-semibold transition-all ${
                chartMode === 'curve' ? 'bg-[#6366f1] text-white shadow-md' : 'text-[#94a3b8] hover:text-white'
              }`}
            >
              Кривая
            </button>
            <button
              onClick={() => setChartMode('bars')}
              className={`px-3 py-1 rounded-xl text-xs font-semibold transition-all ${
                chartMode === 'bars' ? 'bg-[#6366f1] text-white shadow-md' : 'text-[#94a3b8] hover:text-white'
              }`}
            >
              Столбцы
            </button>
          </div>
        </div>

        <div className="relative pt-6 pb-2">
          {/* Target line: 85% */}
          <div className="absolute top-[32%] left-0 right-0 flex items-center">
            <div className="w-full border-b border-dashed border-[#6366f1]/40" />
            <span className="bg-[#1e1b4b] text-[#c7d2fe] border border-[#6366f1]/40 text-[10px] font-bold px-2 py-0.5 rounded-md ml-2 shrink-0">
              Цель 85%
            </span>
          </div>

          <svg viewBox="0 0 700 200" className="w-full h-44 overflow-visible">
            <defs>
              <linearGradient id="purpleBar" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#6366f1" stopOpacity="0.8" />
                <stop offset="100%" stopColor="#6366f1" stopOpacity="0.1" />
              </linearGradient>
              <linearGradient id="mintBar" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#00d084" stopOpacity="0.8" />
                <stop offset="100%" stopColor="#00d084" stopOpacity="0.1" />
              </linearGradient>
            </defs>

            {/* Dynamic Bars for all 7 days */}
            {dayStats.map((st, idx) => {
              const x = 50 + idx * 95;
              const barHeight = Math.max(6, (st.pct / 100) * 160);
              const y = 195 - barHeight;
              const isSelected = selectedDay === st.day;

              return (
                <g key={st.day}>
                  {chartMode !== 'curve' && (
                    <rect
                      x={x}
                      y={y}
                      width="38"
                      height={barHeight}
                      rx="8"
                      fill={isSelected ? 'url(#mintBar)' : 'url(#purpleBar)'}
                      className="transition-all duration-300"
                    />
                  )}
                  {chartMode !== 'bars' && (
                    <>
                      <circle
                        cx={x + 19}
                        cy={y}
                        r={isSelected ? 7 : 5}
                        fill={isSelected ? '#00d084' : '#818cf8'}
                        stroke="#0b0f19"
                        strokeWidth="2"
                      />
                      <text
                        x={x + 19}
                        y={Math.max(14, y - 8)}
                        fill={isSelected ? '#00d084' : '#ffffff'}
                        fontSize="11"
                        fontWeight="bold"
                        textAnchor="middle"
                      >
                        {st.pct}%
                      </text>
                    </>
                  )}
                </g>
              );
            })}
          </svg>

          {/* Days axis labels */}
          <div className="flex justify-between px-6 text-xs text-[#94a3b8] font-bold pt-2">
            {dayStats.map((st) => (
              <span
                key={st.day}
                className={selectedDay === st.day ? 'text-[#00d084]' : 'text-zinc-300'}
              >
                {st.day} ({st.done}/{totalHabits})
              </span>
            ))}
          </div>
        </div>

        {/* Legend Footer */}
        <div className="flex flex-wrap items-center justify-between text-[11px] text-[#94a3b8] border-t border-[#1e293b] pt-3">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#00d084]" />
              <span>Выбранный фокус-день</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#818cf8]" />
              <span>Дни недели</span>
            </div>
          </div>
          <div>
            <span>Пик продуктивности: </span>
            <strong className="text-[#00d084]">
              {bestDay?.day || 'Пн'} ({bestDay?.pct || 0}%)
            </strong>
          </div>
        </div>
      </div>

      {/* 3. CIRCULAR RING & SPHERES BALANCE */}
      <div className="bg-[#111726] border border-[#1e293b] rounded-3xl p-5 shadow-xl space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-white tracking-tight flex items-center space-x-2">
              <span>Фокус: {selectedDay}</span>
              <span className="text-xs text-[#94a3b8] font-normal">({selectedDateStr})</span>
              {selectedDay === todayKey && (
                <span className="text-[10px] font-bold bg-[#00d084]/20 text-[#00d084] border border-[#00d084]/30 px-2 py-0.5 rounded-full uppercase tracking-wider">
                  Сегодня
                </span>
              )}
            </h2>
            <p className="text-xs text-[#94a3b8]">Кольцо закрытия дня и баланс сфер</p>
          </div>
          <span className="text-xs font-bold bg-[#1e293b] text-white px-3 py-1 rounded-xl">
            {completedToday}/{totalHabits} целей
          </span>
        </div>

        <div className="flex justify-center py-2">
          <div className="relative w-44 h-44 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 160 160">
              <circle
                cx="80"
                cy="80"
                r="64"
                stroke="#1b2338"
                strokeWidth="12"
                fill="transparent"
              />
              <circle
                cx="80"
                cy="80"
                r="64"
                stroke="url(#ringGradientDynamic)"
                strokeWidth="12"
                strokeDasharray={402}
                strokeDashoffset={402 * (1 - todayPercent / 100)}
                strokeLinecap="round"
                fill="transparent"
                className="transition-all duration-700 ease-out"
              />
              <defs>
                <linearGradient id="ringGradientDynamic" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#00d084" />
                  <stop offset="50%" stopColor="#06b6d4" />
                  <stop offset="100%" stopColor="#818cf8" />
                </linearGradient>
              </defs>
            </svg>
            <div className="absolute flex flex-col items-center justify-center text-center">
              <span className="text-3xl font-black text-white tracking-tight">{todayPercent}%</span>
              <span className="text-[11px] text-[#94a3b8] font-semibold uppercase tracking-wider">
                Выполнено
              </span>
            </div>
          </div>
        </div>

        {/* Dynamic Balance by Spheres */}
        <div className="space-y-3 pt-2">
          <span className="text-[11px] font-bold text-[#94a3b8] uppercase tracking-wider block">
            БАЛАНС ПО СФЕРАМ ЗА НЕДЕЛЮ
          </span>

          {sphereStats.map(sph => {
            const Icon = sph.icon;
            return (
              <div key={sph.key} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center space-x-2 text-zinc-200 font-semibold">
                    <Icon className="w-4 h-4" style={{ color: sph.color }} />
                    <span>{sph.label}</span>
                  </div>
                  <span className="text-zinc-400 font-medium text-xs">
                    {sph.done}/{sph.total} ({sph.percent}%)
                  </span>
                </div>
                <div className="h-2 w-full bg-[#1b2338] rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${sph.percent}%`, backgroundColor: sph.color }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 4. REAL DYNAMIC HABIT MATRIX */}
      <div className="bg-[#111726] border border-[#1e293b] rounded-3xl p-5 shadow-xl space-y-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-[#00d084] font-bold text-lg">✨</span>
            <h2 className="text-base font-bold text-white tracking-tight">
              Матрица привычек и целей на неделю
            </h2>
          </div>
          <p className="text-xs text-[#94a3b8] mt-0.5">
            Отмечайте выполнение на выбранный день или кликайте по ячейкам Пн — Вс
          </p>
        </div>

        {/* Input Add Habit Bar */}
        <div className="flex flex-col sm:flex-row gap-2 pt-1">
          <input
            type="text"
            placeholder="Новая цель / тренировка (напр. Растяжка 15 мин)"
            value={newHabitTitle}
            onChange={(e) => setNewHabitTitle(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAddHabitSubmit()}
            className="flex-1 bg-[#0b0f19] border border-[#1e293b] rounded-2xl px-3.5 py-2 text-xs text-white placeholder-[#64748b] focus:outline-none focus:border-[#00d084]"
          />
          <select
            value={newHabitCategory}
            onChange={(e) => setNewHabitCategory(e.target.value)}
            className="bg-[#0b0f19] border border-[#1e293b] rounded-2xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#00d084]"
          >
            <option value="Спорт">Спорт</option>
            <option value="Питание">Питание</option>
            <option value="Учеба / Код">Учеба / Код</option>
            <option value="Чтение">Чтение</option>
            <option value="Режим">Режим</option>
          </select>
          <button
            onClick={handleAddHabitSubmit}
            className="bg-[#00d084] hover:bg-[#00b572] active:scale-95 text-[#0b0f19] font-bold text-xs px-4 py-2 rounded-2xl transition-all flex items-center justify-center space-x-1.5 shadow-md shadow-[#00d084]/20"
          >
            <Plus className="w-4 h-4" />
            <span>Добавить</span>
          </button>
        </div>

        {/* Habits List */}
        <div className="space-y-3 pt-2">
          {habits.map((habit) => {
            const isCheckedForSelectedDay = !!habit.history[selectedDateStr];

            return (
              <div
                key={habit.id}
                className="bg-[#0d1322] border border-[#1e293b] rounded-2xl p-3.5 space-y-3 transition-all hover:border-[#334155]"
              >
                {/* Habit Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <button
                      onClick={() => onToggleHabit(habit.id, selectedDateStr)}
                      className={`w-7 h-7 rounded-xl flex items-center justify-center transition-all ${
                        isCheckedForSelectedDay
                          ? 'bg-[#00d084] text-[#0b0f19] shadow-md shadow-[#00d084]/30'
                          : 'bg-[#1b2338] text-zinc-500 hover:text-white'
                      }`}
                    >
                      <CheckCircle2 className="w-4 h-4" />
                    </button>
                    <div>
                      <h3 className="text-sm font-bold text-white tracking-tight">{habit.title}</h3>
                      <div className="flex items-center space-x-2 text-[11px] text-[#94a3b8] mt-0.5">
                        <span className="bg-[#1e293b] text-zinc-300 px-2 py-0.5 rounded-md font-medium">
                          {habit.category}
                        </span>
                        <span>План: {habit.target_days || 7} дн./нед</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-1.5 text-zinc-500">
                    <button
                      onClick={() => onDeleteHabit(habit.id)}
                      className="p-1 hover:text-[#f43f5e] transition-colors"
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
                        onClick={() => onToggleHabit(habit.id, dateForDay)}
                        title={isToday ? `${d} (Сегодня)` : d}
                        className={`relative h-9 rounded-xl flex flex-col items-center justify-center text-xs font-bold transition-all ${
                          isChecked && isSelectedDay
                            ? 'bg-[#00d084] text-[#0b0f19] shadow-md shadow-[#00d084]/25 scale-[1.02]'
                            : isChecked
                            ? 'bg-[#25224d] text-[#c7d2fe] border border-[#4338ca]/40'
                            : isSelectedDay
                            ? 'bg-[#1b2338] text-white border border-[#00d084]/40'
                            : 'bg-[#111726] text-[#64748b] hover:text-white hover:bg-[#1b2338]'
                        } ${isToday && !isSelectedDay ? 'ring-1 ring-[#00d084]/40' : ''}`}
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
                              isChecked && isSelectedDay ? 'bg-[#0b0f19]' : 'bg-[#00d084]'
                            }`}
                          />
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* Streak Pill */}
                <div className="flex items-center justify-between text-xs pt-1">
                  <div className="flex items-center space-x-1.5 bg-[#f59e0b]/10 text-[#f59e0b] border border-[#f59e0b]/30 px-2.5 py-1 rounded-xl font-bold">
                    <Flame className="w-3.5 h-3.5 fill-[#f59e0b]" />
                    <span>
                      {habit.current_streak > 0 ? `${habit.current_streak} дней` : '0 дней (старт)'}
                    </span>
                  </div>
                  <span className="text-[11px] text-[#64748b]">
                    Рекорд: {habit.record_streak || 0} дн.
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
