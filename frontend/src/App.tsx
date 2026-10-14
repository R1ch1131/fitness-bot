import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { BottomNav } from './components/BottomNav';
import type { TabType } from './components/BottomNav';
import { DashboardTab } from './components/DashboardTab';
import { CoachChatTab } from './components/CoachChatTab';
import { WorkoutsTab } from './components/WorkoutsTab';
import { WeeklyTab } from './components/WeeklyTab';
import { LibraryTab } from './components/LibraryTab';
import type { DashboardData, WorkoutsResponse, WeeklyResponse, HabitItem, BookItem, BooksResponse } from './types';

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
  const [booksData, setBooksData] = useState<BooksResponse | null>(null);
  const [isBooksLoading, setIsBooksLoading] = useState<boolean>(false);

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

  // 5. Fetch Books & Library with LocalStorage backup & auto-recovery
  const loadBooks = async () => {
    setIsBooksLoading(true);
    try {
      const res = await fetch('/api/books');
      if (res.ok) {
        const data = await res.json();
        const serverBooks = data.books || [];

        // Check if browser has local backup that survived server container restart
        const localCachedStr = localStorage.getItem('athlete_books_backup');
        if (localCachedStr) {
          try {
            const localBooks = JSON.parse(localCachedStr);
            const serverBookIds = new Set(serverBooks.map((b: any) => b.id));
            const hasCustomLocalBooks = localBooks.some((b: any) => !serverBookIds.has(b.id));

            if (hasCustomLocalBooks && localBooks.length > 0) {
              console.log('Restoring athlete library from browser storage...');
              const syncRes = await fetch('/api/books/sync_all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ books: localBooks }),
              });
              if (syncRes.ok) {
                const syncData = await syncRes.json();
                setBooksData(syncData);
                return;
              }
            }
          } catch (e) {
            console.warn('LocalStorage backup parse note', e);
          }
        }

        setBooksData(data);
        if (serverBooks.length > 0) {
          localStorage.setItem('athlete_books_backup', JSON.stringify(serverBooks));
        }
      }
    } catch (err) {
      console.warn('Books fetch note', err);
    } finally {
      setIsBooksLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
    loadWorkouts();
    loadWeekly();
    loadHabits();
    loadBooks();
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
      await Promise.all([loadDashboard(), loadWorkouts(), loadWeekly(), loadHabits(), loadBooks()]);
    } catch (err) {
      console.error('Sync failed', err);
    } finally {
      setIsSyncing(false);
    }
  };

  const updateBooksState = (data: BooksResponse) => {
    setBooksData(data);
    if (data.books) {
      localStorage.setItem('athlete_books_backup', JSON.stringify(data.books));
    }
  };

  // Book Actions
  const handleAddBook = async (book: {
    title: string;
    author: string;
    category: string;
    total_pages: number;
    current_page?: number;
    status: 'reading' | 'finished' | 'planned';
    rating?: number;
    notes?: string;
  }) => {
    try {
      const res = await fetch('/api/books', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(book),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.books) {
          updateBooksState({ books: data.books, stats: data.stats });
        }
      }
    } catch (err) {
      console.error('Failed to add book', err);
    }
  };

  const handleUpdateBook = async (bookId: string, updates: Partial<BookItem>) => {
    try {
      const res = await fetch(`/api/books/${bookId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.books) {
          updateBooksState({ books: data.books, stats: data.stats });
        }
        if (data.habits) {
          setHabits(data.habits);
        }
      }
    } catch (err) {
      console.error('Failed to update book', err);
    }
  };

  const handleRecordProgress = async (bookId: string, pagesRead: number) => {
    try {
      const res = await fetch(`/api/books/${bookId}/progress`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pages_read: pagesRead }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.books) {
          updateBooksState({ books: data.books, stats: data.stats });
        }
        if (data.habits) {
          setHabits(data.habits);
        }
      }
    } catch (err) {
      console.error('Failed to record reading progress', err);
    }
  };

  const handleDeleteBook = async (bookId: string) => {
    try {
      const res = await fetch(`/api/books/${bookId}`, { method: 'DELETE' });
      if (res.ok) {
        const data = await res.json();
        if (data.books) {
          updateBooksState({ books: data.books, stats: data.stats });
        }
      }
    } catch (err) {
      console.error('Failed to delete book', err);
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
      const errData = await res.json().catch(() => null);
      throw new Error(errData?.detail || 'Server error');
    } catch (err: any) {
      console.error('Chat error:', err);
      return '⚠️ Не удалось получить ответ от AI-тренера. Пожалуйста, попробуй задать вопрос ещё раз через пару секунд.';
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

        {currentTab === 'library' && (
          <LibraryTab
            data={booksData}
            isLoading={isBooksLoading}
            onAddBook={handleAddBook}
            onUpdateBook={handleUpdateBook}
            onRecordProgress={handleRecordProgress}
            onDeleteBook={handleDeleteBook}
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
