import React, { useState, useEffect } from 'react';
import { usePushNotifications } from './usePushNotifications';
import { readSnapshot, writeSnapshot, isHabits, isDashboard } from './snapshot';
import { Header } from './components/Header';
import { BottomNav } from './components/BottomNav';
import type { TabType } from './components/BottomNav';
import { DashboardTab } from './components/DashboardTab';
import { CoachChatTab } from './components/CoachChatTab';
import { WorkoutsTab } from './components/WorkoutsTab';
import { WeeklyTab } from './components/WeeklyTab';
import { LibraryTab } from './components/LibraryTab';
import { WorkoutCheckinToast } from './components/WorkoutCheckinToast';
import type { CheckinNotificationData } from './components/WorkoutCheckinToast';
import type { DashboardData, WorkoutsResponse, WeeklyResponse, HabitItem, BookItem, BooksResponse, ChatMessage } from './types';

// Compute accurate GMT+6 (UTC+6) date, day of week key ('Пн'..'Вс'), and Monday-Sunday week dates
function getGMT6Info(): { dateStr: string; dateFormatted: string; dayKey: string; weekdayLong: string; weekDates: Record<string, string> } {
  const now = new Date();
  // Timezone offset is in minutes. Convert client device time to UTC, then shift by +6 hours for GMT+6
  const utcMs = now.getTime() + (now.getTimezoneOffset() * 60000);
  const gmt6 = new Date(utcMs + (6 * 3600000));

  const day = gmt6.getDay(); // 0 is Sunday, 1 is Monday...
  const diffToMonday = day === 0 ? -6 : 1 - day;
  const monday = new Date(gmt6);
  monday.setDate(gmt6.getDate() + diffToMonday);

  const daysMap: Record<string, string> = {};
  const dayKeys = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
  const dayNamesLong = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'];
  dayKeys.forEach((key, idx) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + idx);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const dateStr = String(d.getDate()).padStart(2, '0');
    daysMap[key] = `${year}-${month}-${dateStr}`;
  });

  const dayIndex = day === 0 ? 6 : day - 1;
  const dayKey = dayKeys[dayIndex] || 'Чт';
  const weekdayLong = dayNamesLong[dayIndex] || 'Четверг';
  const year = gmt6.getFullYear();
  const month = String(gmt6.getMonth() + 1).padStart(2, '0');
  const dateStr = String(gmt6.getDate()).padStart(2, '0');

  return {
    dateStr: `${year}-${month}-${dateStr}`,
    dateFormatted: `${dateStr}.${month}.${year}`,
    dayKey,
    weekdayLong,
    weekDates: daysMap
  };
}

export const App: React.FC = () => {
  const initialGmt6 = getGMT6Info();
  const [currentTab, setCurrentTab] = useState<TabType>(() => {
    const tab = new URLSearchParams(window.location.search).get('tab');
    return ['dashboard', 'chat', 'workouts', 'weekly', 'library'].includes(tab || '') ? tab as TabType : 'dashboard';
  });
  const [todayKey, setTodayKey] = useState<string>(initialGmt6.dayKey);
  const [selectedDay, setSelectedDay] = useState<string>(initialGmt6.dayKey);
  const [weekDates, setWeekDates] = useState<Record<string, string>>(initialGmt6.weekDates);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);

  const [dashboardData, setDashboardData] = useState<DashboardData | null>(() => readSnapshot<DashboardData>('dashboard', isDashboard));
  const [workoutsData, setWorkoutsData] = useState<WorkoutsResponse | null>(null);
  const [weeklyData, setWeeklyData] = useState<WeeklyResponse | null>(null);
  const [habits, setHabits] = useState<HabitItem[]>(() => readSnapshot<HabitItem[]>('habits', isHabits) || []);
  const [booksData, setBooksData] = useState<BooksResponse | null>(null);
  const [isBooksLoading, setIsBooksLoading] = useState<boolean>(false);
  const [dashboardRefreshing, setDashboardRefreshing] = useState(true);
  const push = usePushNotifications();
  const [showPushSettings, setShowPushSettings] = useState(false);
  const [checkinToast, setCheckinToast] = useState<CheckinNotificationData | null>(null);
  const [chatInitialPrompt, setChatInitialPrompt] = useState<string | null>(null);

  const DEFAULT_COACH_GREETING: ChatMessage = {
    id: '1',
    sender: 'coach',
    text: 'Привет, бро! 💪 Я твой персональный AI-тренер и нутрициолог. Вижу все твои подходы в Hevy и каждый грамм в YAZIO. Спрашивай что угодно: разбор рациона, технику упражнений, восстановление или рецепты!',
    timestamp: 'Сейчас',
  };
  const CHAT_STORAGE_KEY = 'fitpulse_coach_chat_history_v1';

  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(() => {
    if (typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem(CHAT_STORAGE_KEY);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed) && parsed.length > 0) return parsed;
        }
      } catch (e) {
        console.warn('Load chat history error:', e);
      }
    }
    return [DEFAULT_COACH_GREETING];
  });

  const handleOpenCheckinChat = () => {
    setCheckinToast(null);
    setChatInitialPrompt(null);
    setCurrentTab('chat');
  };

  const handleClearChatHistory = () => {
    setChatMessages([DEFAULT_COACH_GREETING]);
    try {
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify([DEFAULT_COACH_GREETING]));
      fetch('/api/chat/history', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: [DEFAULT_COACH_GREETING] }),
      }).catch(() => {});
    } catch (e) {}
  };

  // Sync chat messages to localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(chatMessages));
      } catch (e) {
        console.warn('Save chat history error:', e);
      }
    }
  }, [chatMessages]);

  // Load chat history from cloud/backend if local only has default greeting
  useEffect(() => {
    fetch('/api/chat/history')
      .then((res) => res.json())
      .then((data) => {
        if (data.messages && Array.isArray(data.messages) && data.messages.length > 0) {
          setChatMessages((prev) => (prev.length <= 1 ? data.messages : prev));
        }
      })
      .catch(() => {});
  }, []);

  // Debounced backup of chat history to cloud
  useEffect(() => {
    if (chatMessages.length > 1) {
      const timer = setTimeout(() => {
        fetch('/api/chat/history', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ messages: chatMessages }),
        }).catch(() => {});
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [chatMessages]);

  // 1. Fetch Dashboard data
  const loadDashboard = async () => {
    setDashboardRefreshing(true);
    try {
      const res = await fetch('/api/dashboard');
      if (res.ok) {
        const data: DashboardData = await res.json();
        writeSnapshot('dashboard', data);
        setDashboardData(data);
        // Dashboard finishes the Hevy/YAZIO auto-sync. Read its updated marks.
        await loadHabits();
        if (data.weekday_short) {
          setTodayKey(data.weekday_short);
          // If selectedDay is currently pointing to initial day or default 'Ср', align to today
          setSelectedDay((prev) => (prev === 'Ср' || prev === initialGmt6.dayKey ? data.weekday_short! : prev));
        }
        if (data.week_dates) {
          setWeekDates(data.week_dates);
        }
      }
    } catch (err) {
      console.warn('Dashboard fetch offline', err);
    } finally {
      setDashboardRefreshing(false);
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
          writeSnapshot('habits', data.habits);
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
    const onMessage = (event: MessageEvent) => {
      if (event.data?.type === 'OPEN_CHAT_CHECKIN') handleOpenCheckinChat();
    };
    navigator.serviceWorker?.addEventListener('message', onMessage);
    return () => navigator.serviceWorker?.removeEventListener('message', onMessage);
  }, []);

  const checkWorkoutNotifications = async () => {
    try {
      const res = await fetch('/api/notifications/checkin');
      if (res.ok) {
        const data = await res.json();
        if (data.should_notify && data.notification) {
          // Display sleek in-app banner under Dynamic Island
          setCheckinToast(data.notification);
          await fetch('/api/notifications/ack', { method: 'POST' });
        } else if (data.pending && !data.is_due && data.seconds_left > 0) {
          if (data.seconds_left <= 1800) {
            window.clearTimeout((window as any)._checkinTimer);
            (window as any)._checkinTimer = window.setTimeout(() => {
              checkWorkoutNotifications();
            }, data.seconds_left * 1000 + 500);
          }
        }
      }
    } catch (err) {
      console.warn('Checkin notification check note', err);
    }
  };

  useEffect(() => {
    loadDashboard();
    loadHabits();
    checkWorkoutNotifications();

    // Check for day rollover and notifications every 30-60s
    const checkDayRollover = () => {
      const latest = getGMT6Info();
      setTodayKey(latest.dayKey);
      checkWorkoutNotifications();
    };

    const interval = setInterval(checkDayRollover, 30000);
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        checkDayRollover();
        loadDashboard();
        loadHabits();
        checkWorkoutNotifications();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, []);

  // Load heavier sections only when the user opens them.
  useEffect(() => {
    if (currentTab === 'workouts') void loadWorkouts();
    if (currentTab === 'weekly') void loadWeekly();
    if (currentTab === 'library') void loadBooks();
  }, [currentTab]);

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
          writeSnapshot('habits', data.habits);
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
          writeSnapshot('habits', data.habits);
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
          writeSnapshot('habits', data.habits);
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
      await checkWorkoutNotifications();
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
          writeSnapshot('habits', data.habits);
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
          writeSnapshot('habits', data.habits);
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
      const historyContext = chatMessages.slice(-6).map((m) => ({
        role: m.sender === 'user' ? 'user' : 'model',
        text: m.text,
      }));

      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, history: historyContext }),
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

  const isChatTab = currentTab === 'chat';

  return (
    <div
      className={`bg-[#0b0f19] text-[#f8fafc] flex flex-col selection:bg-[#00d084]/20 selection:text-[#00d084] ${
        isChatTab ? 'h-[100dvh] overflow-hidden' : 'min-h-[100dvh]'
      }`}
    >
      {/* 20-min Post-Workout Checkin In-App Banner */}
      <WorkoutCheckinToast
        notification={checkinToast}
        onOpenChat={handleOpenCheckinChat}
        onDismiss={() => setCheckinToast(null)}
      />

      {/* Top Header */}
      <Header
        selectedDay={selectedDay}
        onSelectDay={setSelectedDay}
        todayKey={todayKey}
        dateFormatted={dashboardData?.date_formatted || initialGmt6.dateFormatted}
        weekdayName={dashboardData?.weekday || initialGmt6.weekdayLong}
        weekDates={weekDates}
        habits={habits}
        notificationPermission={push.ready ? 'granted' : 'default'}
        onRequestNotificationPermission={() => setShowPushSettings(v => !v)}
        onTestNotification={() => setShowPushSettings(v => !v)}
        isSyncing={isSyncing}
        onSync={handleSync}
      />

      {showPushSettings && (
        <section className="mx-4 my-3 p-4 rounded-2xl bg-[#111726] border border-[#1e293b] text-sm text-white space-y-3" aria-label="Уведомления">
          <p className="font-semibold">{push.ready ? 'Уведомления подключены' : 'Уведомления не подключены'}</p>
          <p role="status" className="text-[#94a3b8]">{push.blocked || push.message}</p>
          <div className="flex flex-wrap gap-3">
            <button disabled={push.busy || !!push.blocked} onClick={push.enable} className="px-3 py-2 rounded-xl bg-[#00d084] text-[#0b0f19] disabled:opacity-40">Включить</button>
            {push.ready && <button disabled={push.busy} onClick={push.test} className="px-3 py-2 rounded-xl border border-[#00d084] disabled:opacity-40">Тест</button>}
            {push.ready && <button disabled={push.busy} onClick={push.disable} className="px-3 py-2 disabled:opacity-40">Отключить</button>}
          </div>
        </section>
      )}

      {/* Main Content Area */}
      <main className={`w-full ${isChatTab ? 'flex-1 flex flex-col min-h-0 overflow-hidden' : 'flex-1'}`}>
        {currentTab === 'dashboard' && (
          <DashboardTab
            data={dashboardData}
            refreshing={dashboardRefreshing}
            selectedDay={selectedDay}
            todayKey={todayKey}
            habits={habits}
            weekDates={weekDates}
            onToggleHabit={handleToggleHabit}
            onAddHabit={handleAddHabit}
            onDeleteHabit={handleDeleteHabit}
            onOpenChat={(prompt) => {
              if (prompt) setChatInitialPrompt(prompt);
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
          <CoachChatTab
            messages={chatMessages}
            setMessages={setChatMessages}
            onSendMessage={handleSendMessage}
            onClearHistory={handleClearChatHistory}
            initialPrompt={chatInitialPrompt}
            onClearInitialPrompt={() => setChatInitialPrompt(null)}
          />
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
