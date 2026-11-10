import React, { useState, useEffect, useRef } from 'react';
import { usePushNotifications } from './usePushNotifications';
import { useServerConnection } from './useServerConnection';
import { healthHeaders, responseError } from './healthConnection';
import { readSnapshot, writeSnapshot, isHabits, isDashboard } from './snapshot';
import { Header } from './components/Header';
import { NotificationSchedule } from './components/NotificationSchedule';
import { BottomNav } from './components/BottomNav';
import type { TabType } from './components/BottomNav';
import { DashboardTab } from './components/DashboardTab';
import { CoachChatTab } from './components/CoachChatTab';
import { MediaTab } from './components/MediaTab';
import { WeeklyTab } from './components/WeeklyTab';
import { LibraryTab } from './components/LibraryTab';
import { WorkoutCheckinToast } from './components/WorkoutCheckinToast';
import type { CheckinNotificationData } from './components/WorkoutCheckinToast';
import type { DashboardData, WeeklyResponse, WeeklyAnalysisRequest, HabitItem, BookItem, BooksResponse, ChatMessage } from './types';

type AppPage = TabType | 'notifications';

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
  const [currentTab, setCurrentTab] = useState<AppPage>(() => {
    const tab = new URLSearchParams(window.location.search).get('tab');
    return ['dashboard', 'chat', 'media', 'weekly', 'library', 'notifications'].includes(tab || '') ? tab as AppPage : 'dashboard';
  });
  const [todayKey, setTodayKey] = useState<string>(initialGmt6.dayKey);
  const [selectedDay, setSelectedDay] = useState<string>(initialGmt6.dayKey);
  const [weekDates, setWeekDates] = useState<Record<string, string>>(initialGmt6.weekDates);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);

  const [dashboardData, setDashboardData] = useState<DashboardData | null>(() => readSnapshot<DashboardData>('dashboard', isDashboard));
  const [weeklyData, setWeeklyData] = useState<WeeklyResponse | null>(null);
  const [weeklyLoading, setWeeklyLoading] = useState(false);
  const [weeklyError, setWeeklyError] = useState('');
  const [selectedWeek, setSelectedWeek] = useState('');
  const weeklyRequest = useRef<AbortController | null>(null);
  const [habits, setHabits] = useState<HabitItem[]>(() => readSnapshot<HabitItem[]>('habits', isHabits) || []);
  const [booksData, setBooksData] = useState<BooksResponse | null>(null);
  const [isBooksLoading, setIsBooksLoading] = useState<boolean>(false);
  const [dashboardRefreshing, setDashboardRefreshing] = useState(true);
  const push = usePushNotifications();
  const serverStatus = useServerConnection();
  const [testDelay, setTestDelay] = useState(0);
  const [checkinToast, setCheckinToast] = useState<CheckinNotificationData | null>(null);
  const [chatInitialPrompt, setChatInitialPrompt] = useState<string | null>(null);
  const [analysisBusy, setAnalysisBusy] = useState(false);
  const [analysisError, setAnalysisError] = useState('');
  const [lastAnalysis, setLastAnalysis] = useState<WeeklyAnalysisRequest | null>(null);
  const analysisController = useRef<AbortController | null>(null);

  useEffect(() => () => analysisController.current?.abort(), []);

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

  const chatRevision = useRef(0);
  const handleClearChatHistory = () => {
    chatRevision.current += 1;
    setChatMessages([DEFAULT_COACH_GREETING]);
    try {
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify([DEFAULT_COACH_GREETING]));
      fetch('/api/chat/history', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...healthHeaders() },
        body: JSON.stringify({ messages: [DEFAULT_COACH_GREETING], clear: true }),
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

  // Receive proactive coach messages on open, foreground and while viewing chat.
  useEffect(() => {
    const controller = new AbortController();
    let pending = false;
    const refresh = async () => {
      if (pending || document.visibilityState !== 'visible') return;
      pending = true;
      const revision = chatRevision.current;
      try {
        const response = await fetch('/api/chat/history', { headers: healthHeaders(), cache: 'no-store', signal: controller.signal });
        if (!response.ok) return;
        const data = await response.json();
        if (Array.isArray(data.messages) && data.messages.length && !controller.signal.aborted && revision === chatRevision.current) {
          setChatMessages(previous => {
            const merged = new Map<string, ChatMessage>(data.messages.map((message: ChatMessage) => [message.id, message]));
            for (const message of previous) if (!merged.has(message.id)) merged.set(message.id, message);
            const next = [...merged.values()].slice(-100);
            return JSON.stringify(next) === JSON.stringify(previous) ? previous : next;
          });
        }
      } catch { /* Keep the local conversation when the server is unavailable. */ }
      finally { pending = false; }
    };
    void refresh();
    const timer = setInterval(() => { if (currentTab === 'chat') void refresh(); }, 30000);
    document.addEventListener('visibilitychange', refresh);
    window.addEventListener('fitpulse:health-changed', refresh);
    window.addEventListener('fitpulse:server-ready', refresh);
    return () => {
      controller.abort(); clearInterval(timer);
      document.removeEventListener('visibilitychange', refresh);
      window.removeEventListener('fitpulse:health-changed', refresh);
      window.removeEventListener('fitpulse:server-ready', refresh);
    };
  }, [currentTab]);

  // Debounced backup of chat history to cloud
  useEffect(() => {
    if (chatMessages.length > 1) {
      const timer = setTimeout(() => {
        fetch('/api/chat/history', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...healthHeaders() },
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
      const res = await fetch('/api/dashboard', { headers: healthHeaders() });
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

  // 3. Fetch Weekly data
  const loadWeekly = async (week = selectedWeek, refresh = false) => {
    weeklyRequest.current?.abort();
    const controller = new AbortController();
    weeklyRequest.current = controller;
    setWeeklyLoading(true);
    setWeeklyError('');
    try {
      const query = new URLSearchParams();
      if (week) query.set('week_start', week);
      if (refresh) query.set('refresh', 'true');
      const res = await fetch(`/api/weekly?${query}`, { headers: healthHeaders(), signal: controller.signal });
      if (!res.ok) throw await responseError(res);
      const data = await res.json();
      setWeeklyData(data);
    } catch (err) {
      if (!controller.signal.aborted) setWeeklyError((err as Error).message);
    } finally {
      if (!controller.signal.aborted) setWeeklyLoading(false);
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

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [currentTab]);

  // Load heavier sections only when the user opens them.
  useEffect(() => {
    if (currentTab === 'weekly') void loadWeekly();
    if (currentTab === 'library') void loadBooks();
  }, [currentTab]);

  useEffect(() => {
    const recovered = () => {
      void loadDashboard();
      void loadHabits();
      void checkWorkoutNotifications();
      if (currentTab === 'weekly') void loadWeekly();
      if (currentTab === 'library') void loadBooks();
    };
    window.addEventListener('fitpulse:server-ready', recovered);
    window.addEventListener('fitpulse:health-changed', recovered);
    return () => { window.removeEventListener('fitpulse:server-ready', recovered); window.removeEventListener('fitpulse:health-changed', recovered); };
  }, [currentTab, selectedWeek]);

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
      await Promise.all([loadDashboard(), loadWeekly(), loadHabits(), loadBooks()]);
      await checkWorkoutNotifications();
      window.dispatchEvent(new Event('fitpulse:media-refresh'));
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
        headers: { 'Content-Type': 'application/json', ...healthHeaders() },
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

  const handleWeeklyAnalysis = async (request: WeeklyAnalysisRequest, retry = false) => {
    if (analysisController.current) {
      setCurrentTab('chat');
      return;
    }
    const controller = new AbortController();
    analysisController.current = controller;
    setLastAnalysis(request);
    setAnalysisError('');
    setAnalysisBusy(true);
    setChatInitialPrompt(null);
    if (!retry) setChatMessages(prev => [...prev, {
      id: `analysis-user-${Date.now()}`, sender: 'user',
      text: `${request.focus === 'sleep' ? 'Разбери мой сон' : 'Разбери мою неделю'} за ${request.weekStart} — ${request.weekEnd}.\n\n${request.context}`,
      timestamp: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
    }]);
    setCurrentTab('chat');
    let timedOut = false;
    const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 120000);
    try {
      const query = new URLSearchParams({ week_start: request.weekStart });
      if (request.focus) query.set('focus', request.focus);
      const response = await fetch(`/api/weekly/analysis?${query}`, {
        method: 'POST', headers: healthHeaders(), signal: controller.signal,
      });
      if (!response.ok) throw await responseError(response);
      const result = await response.json();
      if (typeof result.reply !== 'string' || !result.reply.trim()) throw Error('ИИ вернул пустой ответ. Попробуй ещё раз.');
      setChatMessages(prev => [...prev, {
        id: `analysis-coach-${Date.now()}`, sender: 'coach', text: result.reply,
        timestamp: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
      }]);
    } catch (error) {
      if (!controller.signal.aborted || timedOut) setAnalysisError(timedOut
        ? 'ИИ не успел ответить. Данные остались в чате — можно повторить разбор.'
        : (error as Error).message);
    } finally {
      clearTimeout(timeout);
      analysisController.current = null;
      setAnalysisBusy(false);
    }
  };

  const isChatTab = currentTab === 'chat';

  return (
    <div
      className={`fit-app bg-[#101714] text-[#e6eee8] flex flex-col selection:bg-[#79c5a6]/20 selection:text-[#79c5a6] ${
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
        compact={isChatTab}
        selectedDay={selectedDay}
        onSelectDay={setSelectedDay}
        todayKey={todayKey}
        dateFormatted={dashboardData?.date_formatted || initialGmt6.dateFormatted}
        weekdayName={dashboardData?.weekday || initialGmt6.weekdayLong}
        weekDates={weekDates}
        habits={habits}
        notificationPermission={push.ready ? 'granted' : 'default'}
        onRequestNotificationPermission={() => setCurrentTab('notifications')}
        onTestNotification={() => setCurrentTab('notifications')}
        isSyncing={isSyncing}
        onSync={handleSync}
      />

      {serverStatus !== 'ready' && (
        <p role="status" className="mx-4 my-2 p-3 text-xs text-[#a4b8aa] rounded-xl bg-[#19221f] shrink-0">
          {serverStatus === 'offline'
            ? 'Нет подключения. Показываем сохранённые данные. Изменения будут доступны после подключения.'
            : serverStatus === 'waking'
              ? 'Сервер запускается. Показываем сохранённые данные и автоматически обновим их после подключения.'
              : 'Подключаемся к серверу…'}
        </p>
      )}

      {/* Main Content Area */}
      <main className={`w-full ${isChatTab ? 'flex-1 flex flex-col min-h-0 overflow-hidden' : 'flex-1'}`}>
        <fieldset disabled={serverStatus !== 'ready'} className="contents">
        {currentTab === 'notifications' && (
          <section className="max-w-3xl mx-auto px-4 pt-5 pb-32 text-sm text-[#e6eee8] space-y-4" aria-label="Уведомления">
            <div>
              <h2 className="text-xl font-bold">Уведомления</h2>
              <p className="mt-1 text-[#a4b8aa]">Подключение, расписание и свои напоминания. Время — по Омску.</p>
            </div>
            {serverStatus === 'ready' ? (
              <div className="p-4 rounded-2xl bg-[#19221f] border border-[#33473b] space-y-3">
                <p className="font-semibold">{push.ready ? 'Уведомления подключены' : 'Уведомления не подключены'}</p>
                <p role="status" className="text-[#a4b8aa]">{push.blocked || push.message}</p>
                <div className="flex flex-wrap gap-3">
                  <button disabled={push.busy || !!push.blocked} onClick={push.enable} className="px-3 py-2 rounded-xl bg-[#79c5a6] text-[#10261b] disabled:opacity-40">Включить</button>
                  {push.ready && <button disabled={push.busy} onClick={() => push.test(testDelay)} className="px-3 py-2 rounded-xl border border-[#79c5a6] disabled:opacity-40">Тест</button>}
                  {push.ready && <button disabled={push.busy} onClick={push.disable} className="px-3 py-2 disabled:opacity-40">Отключить</button>}
                </div>
                {push.ready && (
                  <div className="space-y-2 text-xs text-[#a4b8aa]">
                    <label className="flex items-center justify-between gap-3">
                      <span>Когда отправить тест</span>
                      <select value={testDelay} disabled={push.busy} onChange={e => setTestDelay(Number(e.target.value))} className="rounded-lg bg-[#101714] border border-[#33473b] p-2 text-[#e6eee8]">
                        <option value={0}>Сейчас</option>
                        <option value={60}>Через 1 минуту</option>
                        <option value={2100}>Через 35 минут</option>
                      </select>
                    </label>
                    <p>Отложенный тест отправляет сервер — приложение можно закрыть. Он проверяет доставку push и не означает начало тренировки в Hevy.</p>
                    {push.scheduledTest && <p>Тест запланирован на {new Date(push.scheduledTest * 1000).toLocaleTimeString('ru-RU', { timeZone: 'Asia/Omsk', hour: '2-digit', minute: '2-digit' })} по Омску.
                      <button disabled={push.busy} onClick={push.cancelTest} className="ml-2 underline disabled:opacity-40">Отменить тест</button>
                    </p>}
                  </div>
                )}
                <NotificationSchedule />
              </div>
            ) : (
              <p className="text-[#a4b8aa]">Настройки уведомлений появятся после подключения к серверу.</p>
            )}
          </section>
        )}

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
            onOpenWeekly={() => setCurrentTab('weekly')}
          />
        )}

        {currentTab === 'media' && <MediaTab />}

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
            analysisBusy={analysisBusy}
            analysisError={analysisError}
            onRetryAnalysis={() => { if (lastAnalysis) void handleWeeklyAnalysis(lastAnalysis, true); }}
          />
        )}

        {currentTab === 'weekly' && (
          <WeeklyTab
            data={weeklyData}
            selectedWeek={selectedWeek}
            isLoading={weeklyLoading}
            error={weeklyError}
            onRetry={() => void loadWeekly(selectedWeek, true)}
            onSelectWeek={week => {
              setSelectedWeek(week);
              void loadWeekly(week);
            }}
            onAnalyze={request => void handleWeeklyAnalysis(request)}
          />
        )}
        </fieldset>
      </main>

      {/* Sticky Mobile Bottom Navigation */}
      <BottomNav currentTab={currentTab === 'notifications' ? null : currentTab} onTabChange={setCurrentTab} />
    </div>
  );
};

export default App;
