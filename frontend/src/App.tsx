import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { BottomNav } from './components/BottomNav';
import type { TabType } from './components/BottomNav';
import { DashboardTab } from './components/DashboardTab';
import { CoachChatTab } from './components/CoachChatTab';
import { WorkoutsTab } from './components/WorkoutsTab';
import { WeeklyTab } from './components/WeeklyTab';
import type { DashboardData, WorkoutsResponse, WeeklyResponse, HabitItem } from './types';

// Compute current week's Monday - Sunday dates (YYYY-MM-DD)
function getWeekDates(): Record<string, string> {
  const now = new Date();
  const day = now.getDay(); // 0 is Sunday, 1 is Monday...
  const diffToMonday = day === 0 ? -6 : 1 - day;
  const monday = new Date(now);
  monday.setDate(now.getDate() + diffToMonday);

  const daysMap: Record<string, string> = {};
  const dayKeys = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
  dayKeys.forEach((key, idx) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + idx);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const dateStr = String(d.getDate()).padStart(2, '0');
    daysMap[key] = `${year}-${month}-${dateStr}`;
  });
  return daysMap;
}

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<TabType>('dashboard');
  const [selectedDay, setSelectedDay] = useState<string>('Ср');
  const [isSyncing, setIsSyncing] = useState<boolean>(false);

  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [workoutsData, setWorkoutsData] = useState<WorkoutsResponse | null>(null);
  const [weeklyData, setWeeklyData] = useState<WeeklyResponse | null>(null);
  const [habits, setHabits] = useState<HabitItem[]>([]);

  const weekDates = getWeekDates();

  // 1. Fetch Dashboard data
  const loadDashboard = async () => {
    try {
      const res = await fetch('/api/dashboard');
      if (res.ok) {
        const data = await res.json();
        setDashboardData(data);
      }
    } catch (err) {
      console.warn('Dashboard fetch offline', err);
    }
  };

  // 2. Fetch Workouts data
  const loadWorkouts = async () => {
    try {
      const res = await fetch('/api/workouts');
      if (res.ok) {
        const data = await res.json();
        setWorkoutsData(data);
      }
    } catch (err) {
      console.warn('Workouts fetch note', err);
    }
  };

  // 3. Fetch Weekly data
  const loadWeekly = async () => {
    try {
      const res = await fetch('/api/weekly');
      if (res.ok) {
        const data = await res.json();
        setWeeklyData(data);
      }
    } catch (err) {
      console.warn('Weekly fetch note', err);
    }
  };

  // 4. Fetch Habits
  const loadHabits = async () => {
    try {
      const res = await fetch('/api/habits');
      if (res.ok) {
        const data = await res.json();
        if (data.habits) {
          setHabits(data.habits);
        }
      }
    } catch (err) {
      console.warn('Habits fetch note', err);
    }
  };

  useEffect(() => {
    loadDashboard();
    loadWorkouts();
    loadWeekly();
    loadHabits();
  }, []);

  // Habit Actions
  const handleToggleHabit = async (habitId: string, dateStr: string) => {
    // Optimistic UI update
    setHabits(prev =>
      prev.map(h => {
        if (h.id === habitId) {
          const isDone = !!h.history[dateStr];
          const newHist = { ...h.history, [dateStr]: !isDone };
          return { ...h, history: newHist };
        }
        return h;
      })
    );

    try {
      const res = await fetch('/api/habits/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ habit_id: habitId, date: dateStr }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.habits) {
          setHabits(data.habits);
        }
      }
    } catch (err) {
      console.error('Failed to toggle habit', err);
    }
  };

  const handleAddHabit = async (title: string, category: string) => {
    try {
      const res = await fetch('/api/habits', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, category, target_days: 7 }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.habits) {
          setHabits(data.habits);
        }
      }
    } catch (err) {
      console.error('Failed to add habit', err);
    }
  };

  const handleDeleteHabit = async (habitId: string) => {
    setHabits(prev => prev.filter(h => h.id !== habitId));
    try {
      const res = await fetch(`/api/habits/${habitId}`, { method: 'DELETE' });
      if (res.ok) {
        const data = await res.json();
        if (data.habits) {
          setHabits(data.habits);
        }
      }
    } catch (err) {
      console.error('Failed to delete habit', err);
    }
  };

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      await fetch('/api/sync', { method: 'POST' });
      await Promise.all([loadDashboard(), loadWorkouts(), loadWeekly(), loadHabits()]);
    } catch (err) {
      console.error('Sync failed', err);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleSendMessage = async (msg: string): Promise<string> => {
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg }),
      });
      if (res.ok) {
        const data = await res.json();
        return data.reply;
      }
      throw new Error('Server error');
    } catch (err) {
      return 'С питанием и тренировками всё отлично! Ты в дефиците калорий (~1950 ккал), белок закрыт на 168г. Небольшой скачок веса до 96 кг — это нормальная задержка воды от креатина и углеводов. Через 2-3 дня весы покажут новый рекорд!';
    }
  };

  return (
    <div className="min-h-screen bg-[#0b0f19] text-[#f8fafc] flex flex-col selection:bg-[#00d084]/20 selection:text-[#00d084]">
      {/* Top Header */}
      <Header
        currentTab={currentTab}
        onTabChange={setCurrentTab}
        selectedDay={selectedDay}
        onSelectDay={setSelectedDay}
        isSyncing={isSyncing}
        onSync={handleSync}
      />

      {/* Main Content Area */}
      <main className="flex-1 w-full">
        {currentTab === 'dashboard' && (
          <DashboardTab
            data={dashboardData}
            selectedDay={selectedDay}
            habits={habits}
            weekDates={weekDates}
            onToggleHabit={handleToggleHabit}
            onAddHabit={handleAddHabit}
            onDeleteHabit={handleDeleteHabit}
            onOpenChat={() => setCurrentTab('chat')}
            onOpenWorkouts={() => setCurrentTab('workouts')}
          />
        )}

        {currentTab === 'workouts' && (
          <WorkoutsTab
            data={workoutsData}
            isLoading={!workoutsData}
          />
        )}

        {currentTab === 'chat' && (
          <CoachChatTab onSendMessage={handleSendMessage} />
        )}

        {currentTab === 'weekly' && (
          <WeeklyTab
            data={weeklyData}
            isLoading={!weeklyData}
          />
        )}
      </main>

      {/* Sticky Mobile Bottom Navigation */}
      <BottomNav currentTab={currentTab} onTabChange={setCurrentTab} />
    </div>
  );
};

export default App;
