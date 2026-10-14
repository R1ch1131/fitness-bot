import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { BottomNav } from './components/BottomNav';
import type { TabType } from './components/BottomNav';
import { DashboardTab } from './components/DashboardTab';
import { CoachChatTab } from './components/CoachChatTab';
import { WorkoutsTab } from './components/WorkoutsTab';
import { WeeklyTab } from './components/WeeklyTab';
import type { DashboardData, WorkoutsResponse, WeeklyResponse } from './types';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<TabType>('dashboard');
  const [selectedDay, setSelectedDay] = useState<string>('Ср');
  const [isSyncing, setIsSyncing] = useState<boolean>(false);

  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [workoutsData, setWorkoutsData] = useState<WorkoutsResponse | null>(null);
  const [weeklyData, setWeeklyData] = useState<WeeklyResponse | null>(null);

  // Fetch Dashboard data
  const loadDashboard = async () => {
    try {
      const res = await fetch('/api/dashboard');
      if (res.ok) {
        const data = await res.json();
        setDashboardData(data);
      }
    } catch (err) {
      console.warn('Dashboard fetch offline or failed, using demo/cached data', err);
      // Fallback demo data matching athlete specs
      setDashboardData({
        date: '2026-10-14',
        weekday: 'Среда',
        time: '18:30',
        nutrition: {
          calories: 1950,
          calories_goal: 2000,
          protein: 168,
          protein_goal: 160,
          fat: 55,
          carbs: 185,
          water_ml: 2200,
          meals: {
            breakfast: {
              title: 'Завтрак',
              calories: 450,
              products: [
                { name: 'Овсяноблин (2 яйца + овсянка)', amount: 180, calories: 350 },
                { name: 'Сыр легкий 15%', amount: 30, calories: 100 },
              ],
            },
            lunch: {
              title: 'Обед',
              calories: 680,
              products: [
                { name: 'Вареная куриная грудка', amount: 150, calories: 247 },
                { name: 'Пропаренный белый рис', amount: 200, calories: 246 },
                { name: 'Соевый соус', amount: 16, calories: 8 },
              ],
            },
            dinner: {
              title: 'Ужин',
              calories: 480,
              products: [
                { name: 'Творог 5% + греческий йогурт', amount: 200, calories: 220 },
                { name: 'Киви (2 шт)', amount: 140, calories: 90 },
              ],
            },
          },
        },
        workout: {
          today_completed: false,
          next_routine: {
            routine_title: 'Среда: Ноги + Спина',
            exercises: [
              { title: 'Становая тяга со штангой', target_sets: 4, target_reps: '6-8', last_weight: '70 кг' },
              { title: 'Приседания со штангой', target_sets: 4, target_reps: '8-10', last_weight: '60 кг' },
              { title: 'Тяга верхнего блока к груди', target_sets: 3, target_reps: '10-12', last_weight: '55 кг' },
              { title: 'Подъем ног в висе на пресс', target_sets: 3, target_reps: '12-15', last_weight: 'Свой вес' },
            ],
          },
        },
        profile: {
          current_weight: 96.0,
          start_weight: 103.0,
          goal_weight: 80.0,
          weight_history: [
            { date: '2026-10-10', weight: 95.3 },
            { date: '2026-10-11', weight: 95.5 },
            { date: '2026-10-12', weight: 95.8 },
            { date: '2026-10-13', weight: 96.0 },
            { date: '2026-10-14', weight: 96.0 },
          ],
        },
      });
    }
  };

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

  useEffect(() => {
    loadDashboard();
    loadWorkouts();
    loadWeekly();
  }, []);

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      await fetch('/api/sync', { method: 'POST' });
      await Promise.all([loadDashboard(), loadWorkouts(), loadWeekly()]);
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
      // Fallback response if offline
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
            onOpenChat={() => {
              setCurrentTab('chat');
            }}
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
