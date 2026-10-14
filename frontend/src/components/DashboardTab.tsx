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
  Edit3, 
  Trash2
} from 'lucide-react';
import type { DashboardData } from '../types';

interface DashboardTabProps {
  data: DashboardData | null;
  selectedDay: string;
  onOpenChat: (query?: string) => void;
  onOpenWorkouts: () => void;
}

export const DashboardTab: React.FC<DashboardTabProps> = ({
  data,
  selectedDay,
  onOpenChat,
  onOpenWorkouts,
}) => {
  const [chartMode, setChartMode] = useState<'combo' | 'curve' | 'bars'>('combo');
  const [newHabitTitle, setNewHabitTitle] = useState('');
  const [newHabitCategory, setNewHabitCategory] = useState('Спорт');

  // Interactive habit matrix state
  const [habits, setHabits] = useState([
    {
      id: '1',
      title: 'Силовая тренировка (Hevy сплит)',
      category: 'Спорт',
      plan: '3/5 дн.',
      streak: 9,
      record: 14,
      days: { Пн: true, Вт: true, Ср: true, Чт: false, Пт: false, Сб: false, Вс: false },
    },
    {
      id: '2',
      title: 'Контроль КБЖУ и норма белка (160г+)',
      category: 'Питание',
      plan: '3/7 дн.',
      streak: 15,
      record: 21,
      days: { Пн: true, Вт: true, Ср: true, Чт: false, Пт: false, Сб: false, Вс: false },
    },
    {
      id: '3',
      title: 'Овсяноблин & Клетчатка (ЖКТ баланс)',
      category: 'Питание',
      plan: '3/6 дн.',
      streak: 7,
      record: 10,
      days: { Пн: true, Вт: true, Ср: true, Чт: false, Пт: false, Сб: false, Вс: false },
    },
    {
      id: '4',
      title: 'Креатин + Водный баланс (2.5л+)',
      category: 'Режим',
      plan: '2/7 дн.',
      streak: 6,
      record: 12,
      days: { Пн: true, Вт: true, Ср: false, Чт: false, Пт: false, Сб: false, Вс: false },
    },
  ]);

  const toggleHabitDay = (habitId: string, dayKey: string) => {
    setHabits(prev =>
      prev.map(h => {
        if (h.id === habitId) {
          const newDays = { ...h.days, [dayKey]: !h.days[dayKey as keyof typeof h.days] };
          return { ...h, days: newDays };
        }
        return h;
      })
    );
  };

  const handleAddHabit = () => {
    if (!newHabitTitle.trim()) return;
    setHabits(prev => [
      ...prev,
      {
        id: Date.now().toString(),
        title: newHabitTitle.trim(),
        category: newHabitCategory,
        plan: '0/7 дн.',
        streak: 1,
        record: 1,
        days: { Пн: false, Вт: false, Ср: false, Чт: false, Пт: false, Сб: false, Вс: false },
      },
    ]);
    setNewHabitTitle('');
  };

  const nutrition = data?.nutrition || {
    calories: 1950,
    calories_goal: 2000,
    protein: 168,
    protein_goal: 160,
    fat: 55,
    carbs: 185,
    water_ml: 2200,
    meals: {},
  };

  const calPercent = Math.min(100, Math.round((nutrition.calories / nutrition.calories_goal) * 100));

  return (
    <div className="space-y-4 pb-28 px-3 pt-3 max-w-5xl mx-auto">
      {/* 1. TOP 4 KPI CARDS (Matches Screenshot 2) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Card 1: Сегодня */}
        <div 
          onClick={() => onOpenChat("Разбери мой рацион за сегодня")}
          className="bg-[#111726] border border-[#1e293b] hover:border-[#00d084]/40 cursor-pointer rounded-3xl p-4 flex flex-col justify-between shadow-lg relative overflow-hidden transition-all"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-[#94a3b8] uppercase tracking-wider">
              📅 Сегодня ({selectedDay})
            </span>
            <div className="w-8 h-8 rounded-xl bg-[#00d084]/10 border border-[#00d084]/20 flex items-center justify-center text-[#00d084]">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="my-3">
            <div className="flex items-baseline space-x-2">
              <span className="text-3xl font-extrabold text-white tracking-tight">{calPercent}%</span>
              <span className="text-xs text-[#94a3b8] font-medium">
                ({Math.round(nutrition.calories)} / {nutrition.calories_goal} ккал)
              </span>
            </div>
            <div className="h-2 w-full bg-[#1b2338] rounded-full mt-2.5 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-[#00d084] to-[#06b6d4] rounded-full transition-all duration-500"
                style={{ width: `${calPercent}%` }}
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
              <span className="text-3xl font-extrabold text-white tracking-tight">88%</span>
              <span className="text-[11px] font-bold bg-[#f59e0b]/20 text-[#f59e0b] border border-[#f59e0b]/30 px-2 py-0.5 rounded-lg">
                В дефиците!
              </span>
            </div>
            <div className="h-2 w-full bg-[#1b2338] rounded-full mt-2.5 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-[#6366f1] to-[#a855f7] rounded-full transition-all duration-500"
                style={{ width: `88%` }}
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
              <span className="text-3xl font-extrabold text-white tracking-tight">15 дней</span>
              <span className="text-xs text-[#94a3b8] font-medium">Рекорд: 21 дн.</span>
            </div>
            <p className="text-[11px] text-[#94a3b8] mt-1 truncate">
              Лидер: <strong className="text-zinc-200">Контроль КБЖУ и норма белка</strong>
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
              🏋️ Объем за неделю
            </span>
            <div className="w-8 h-8 rounded-xl bg-[#06b6d4]/10 border border-[#06b6d4]/20 flex items-center justify-center text-[#06b6d4]">
              <Layers className="w-4 h-4" />
            </div>
          </div>
          <div className="my-3">
            <div className="flex items-baseline space-x-2">
              <span className="text-3xl font-extrabold text-white tracking-tight">14.0 т</span>
              <span className="text-xs text-[#94a3b8] font-medium">из 45т по плану</span>
            </div>
            <p className="text-[11px] text-[#94a3b8] mt-1">
              Активных тренировок в сплите: <strong className="text-zinc-200">5</strong>
            </p>
          </div>
        </div>
      </div>

      {/* 2. DYNAMIC TREND CHART (Matches Screenshot 2) */}
      <div className="bg-[#111726] border border-[#1e293b] rounded-3xl p-5 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-base font-bold text-white tracking-tight">
                Динамика серий и калорий за неделю
              </h2>
              <span className="text-[10px] font-bold bg-[#00d084]/20 text-[#00d084] border border-[#00d084]/30 px-2 py-0.5 rounded-full uppercase tracking-wider">
                Live
              </span>
            </div>
            <p className="text-xs text-[#94a3b8] mt-0.5">
              Процент выполнения по дням с целевым ориентиром 85% (калории & тренировки)
            </p>
          </div>

          {/* Toggle buttons */}
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

        {/* SVG Chart Visualization */}
        <div className="relative pt-6 pb-2">
          {/* Target line: 85% */}
          <div className="absolute top-[35%] left-0 right-0 flex items-center">
            <div className="w-full border-b border-dashed border-[#6366f1]/40" />
            <span className="bg-[#1e1b4b] text-[#c7d2fe] border border-[#6366f1]/40 text-[10px] font-bold px-2 py-0.5 rounded-md ml-2 shrink-0">
              Цель 85%
            </span>
          </div>

          <svg viewBox="0 0 700 200" className="w-full h-44 overflow-visible">
            <defs>
              <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#6366f1" stopOpacity="0.4" />
                <stop offset="100%" stopColor="#6366f1" stopOpacity="0.0" />
              </linearGradient>
              <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#00d084" stopOpacity="0.8" />
                <stop offset="100%" stopColor="#00d084" stopOpacity="0.1" />
              </linearGradient>
              <linearGradient id="purpleBarGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#6366f1" stopOpacity="0.8" />
                <stop offset="100%" stopColor="#6366f1" stopOpacity="0.1" />
              </linearGradient>
            </defs>

            {/* Bars */}
            {chartMode !== 'curve' && (
              <>
                <rect x="50" y="30" width="36" height="170" rx="8" fill="url(#purpleBarGradient)" />
                <rect x="150" y="60" width="36" height="140" rx="8" fill="url(#purpleBarGradient)" />
                <rect x="250" y="90" width="36" height="110" rx="8" fill="url(#barGradient)" />
                <rect x="350" y="195" width="36" height="5" rx="2" fill="#1e293b" />
                <rect x="450" y="195" width="36" height="5" rx="2" fill="#1e293b" />
                <rect x="550" y="195" width="36" height="5" rx="2" fill="#1e293b" />
                <rect x="650" y="195" width="36" height="5" rx="2" fill="#1e293b" />
              </>
            )}

            {/* Curve path */}
            {chartMode !== 'bars' && (
              <>
                <path
                  d="M 68 30 C 110 30, 130 60, 168 60 C 210 60, 230 95, 268 95 C 310 95, 330 195, 368 195 L 668 195"
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth="3.5"
                  strokeLinecap="round"
                />
                {/* Dots with labels */}
                {/* Day 1: 100% */}
                <circle cx="68" cy="30" r="6" fill="#00d084" stroke="#0b0f19" strokeWidth="2.5" />
                <text x="68" y="16" fill="#ffffff" fontSize="11" fontWeight="bold" textAnchor="middle">
                  100%
                </text>

                {/* Day 2: 80% */}
                <circle cx="168" cy="60" r="6" fill="#818cf8" stroke="#0b0f19" strokeWidth="2.5" />
                <text x="168" y="46" fill="#ffffff" fontSize="11" fontWeight="bold" textAnchor="middle">
                  80%
                </text>

                {/* Day 3 (Selected today): 60% */}
                <circle cx="268" cy="95" r="7" fill="#00d084" stroke="#ffffff" strokeWidth="2.5" />
                <text x="268" y="80" fill="#00d084" fontSize="11" fontWeight="bold" textAnchor="middle">
                  60%
                </text>
              </>
            )}
          </svg>

          {/* Days axis labels */}
          <div className="flex justify-between px-6 text-xs text-[#94a3b8] font-bold pt-2">
            <span className="text-zinc-200">Пн (5/5)</span>
            <span className="text-zinc-200">Вт (4/5)</span>
            <span className="text-[#00d084]">Ср (3/5)</span>
            <span>Чт (0/5)</span>
            <span>Пт (0/5)</span>
            <span>Сб (0/5)</span>
            <span>Вс (0/5)</span>
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
            <strong className="text-[#00d084]">Понедельник (100%)</strong>
          </div>
        </div>
      </div>

      {/* 3. CIRCULAR RING & SPHERES BALANCE (Matches Screenshot 1 & 4) */}
      <div className="bg-[#111726] border border-[#1e293b] rounded-3xl p-5 shadow-xl space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-white tracking-tight">
              Фокус: Среда
            </h2>
            <p className="text-xs text-[#94a3b8]">Кольцо закрытия дня и баланс сфер</p>
          </div>
          <span className="text-xs font-bold bg-[#1e293b] text-white px-3 py-1 rounded-xl">
            3/5 целей
          </span>
        </div>

        {/* Big Circular Progress Ring */}
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
                stroke="url(#ringGradient)"
                strokeWidth="12"
                strokeDasharray={402}
                strokeDashoffset={402 * (1 - 0.6)}
                strokeLinecap="round"
                fill="transparent"
                className="transition-all duration-1000 ease-out"
              />
              <defs>
                <linearGradient id="ringGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#00d084" />
                  <stop offset="50%" stopColor="#06b6d4" />
                  <stop offset="100%" stopColor="#818cf8" />
                </linearGradient>
              </defs>
            </svg>
            <div className="absolute flex flex-col items-center justify-center text-center">
              <span className="text-3xl font-black text-white tracking-tight">60%</span>
              <span className="text-[11px] text-[#94a3b8] font-semibold uppercase tracking-wider">
                Выполнено
              </span>
            </div>
          </div>
        </div>

        {/* Balance by Spheres */}
        <div className="space-y-3 pt-2">
          <span className="text-[11px] font-bold text-[#94a3b8] uppercase tracking-wider block">
            БАЛАНС ПО СФЕРАМ ЗА НЕДЕЛЮ
          </span>

          {/* 1. Спорт */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center space-x-2 text-zinc-200 font-semibold">
                <Dumbbell className="w-4 h-4 text-[#00d084]" />
                <span>Спорт</span>
              </div>
              <span className="text-zinc-400 font-medium text-xs">3/5 (60%)</span>
            </div>
            <div className="h-2 w-full bg-[#1b2338] rounded-full overflow-hidden">
              <div className="h-full bg-[#00d084] rounded-full w-[60%]" />
            </div>
          </div>

          {/* 2. Питание */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center space-x-2 text-zinc-200 font-semibold">
                <Utensils className="w-4 h-4 text-[#f59e0b]" />
                <span>Питание</span>
              </div>
              <span className="text-zinc-400 font-medium text-xs">3/7 (43%)</span>
            </div>
            <div className="h-2 w-full bg-[#1b2338] rounded-full overflow-hidden">
              <div className="h-full bg-[#f59e0b] rounded-full w-[43%]" />
            </div>
          </div>

          {/* 3. Учеба / Код */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center space-x-2 text-zinc-200 font-semibold">
                <Code className="w-4 h-4 text-[#a855f7]" />
                <span>Учеба / Код</span>
              </div>
              <span className="text-zinc-400 font-medium text-xs">3/6 (50%)</span>
            </div>
            <div className="h-2 w-full bg-[#1b2338] rounded-full overflow-hidden">
              <div className="h-full bg-[#a855f7] rounded-full w-[50%]" />
            </div>
          </div>

          {/* 4. Чтение */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center space-x-2 text-zinc-200 font-semibold">
                <BookOpen className="w-4 h-4 text-[#06b6d4]" />
                <span>Чтение</span>
              </div>
              <span className="text-zinc-400 font-medium text-xs">1/7 (14%)</span>
            </div>
            <div className="h-2 w-full bg-[#1b2338] rounded-full overflow-hidden">
              <div className="h-full bg-[#06b6d4] rounded-full w-[14%]" />
            </div>
          </div>

          {/* 5. Режим */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center space-x-2 text-zinc-200 font-semibold">
                <Moon className="w-4 h-4 text-[#f43f5e]" />
                <span>Режим</span>
              </div>
              <span className="text-zinc-400 font-medium text-xs">2/7 (29%)</span>
            </div>
            <div className="h-2 w-full bg-[#1b2338] rounded-full overflow-hidden">
              <div className="h-full bg-[#f43f5e] rounded-full w-[29%]" />
            </div>
          </div>
        </div>
      </div>

      {/* 4. HABIT & TARGET MATRIX (Matches Screenshot 3) */}
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
            onKeyDown={(e) => e.key === 'Enter' && handleAddHabit()}
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
            onClick={handleAddHabit}
            className="bg-[#00d084] hover:bg-[#00b572] active:scale-95 text-[#0b0f19] font-bold text-xs px-4 py-2 rounded-2xl transition-all flex items-center justify-center space-x-1.5 shadow-md shadow-[#00d084]/20"
          >
            <Plus className="w-4 h-4" />
            <span>Добавить</span>
          </button>
        </div>

        {/* Habits List (Matches Screenshot 3) */}
        <div className="space-y-3 pt-2">
          {habits.map((habit) => {
            const allDays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

            return (
              <div
                key={habit.id}
                className="bg-[#0d1322] border border-[#1e293b] rounded-2xl p-3.5 space-y-3 transition-all hover:border-[#334155]"
              >
                {/* Habit Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <button
                      onClick={() => toggleHabitDay(habit.id, selectedDay)}
                      className={`w-7 h-7 rounded-xl flex items-center justify-center transition-all ${
                        habit.days[selectedDay as keyof typeof habit.days]
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
                        <span>План: {habit.plan}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-1.5 text-zinc-500">
                    <button className="p-1 hover:text-white transition-colors">
                      <Edit3 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => setHabits(prev => prev.filter(h => h.id !== habit.id))}
                      className="p-1 hover:text-[#f43f5e] transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Day Buttons Grid (7 Days) */}
                <div className="grid grid-cols-7 gap-1.5">
                  {allDays.map((d) => {
                    const isChecked = !!habit.days[d as keyof typeof habit.days];
                    const isSelectedDay = selectedDay === d;

                    return (
                      <button
                        key={d}
                        onClick={() => toggleHabitDay(habit.id, d)}
                        className={`h-9 rounded-xl flex flex-col items-center justify-center text-xs font-bold transition-all ${
                          isChecked && isSelectedDay
                            ? 'bg-[#00d084] text-[#0b0f19] shadow-md shadow-[#00d084]/25 scale-[1.02]'
                            : isChecked
                            ? 'bg-[#25224d] text-[#c7d2fe] border border-[#4338ca]/40'
                            : 'bg-[#111726] text-[#64748b] hover:text-white hover:bg-[#1b2338]'
                        }`}
                      >
                        <span className="text-[10px] opacity-75">{d}</span>
                        {isChecked ? (
                          <span className="text-xs">✓</span>
                        ) : (
                          <span className="text-[10px] opacity-30">•</span>
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* Streak Pill */}
                <div className="flex items-center justify-between text-xs pt-1">
                  <div className="flex items-center space-x-1.5 bg-[#f59e0b]/10 text-[#f59e0b] border border-[#f59e0b]/30 px-2.5 py-1 rounded-xl font-bold">
                    <Flame className="w-3.5 h-3.5 fill-[#f59e0b]" />
                    <span>{habit.streak} дней</span>
                  </div>
                  <span className="text-[11px] text-[#64748b]">Рекорд: {habit.record} дн.</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
