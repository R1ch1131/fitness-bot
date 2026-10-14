import React, { useState } from 'react';
import { 
  BookOpen, Plus, CheckCircle2, Star, Trash2, 
  Sparkles, X, BookMarked, Award, Loader2
} from 'lucide-react';
import type { BookItem, BooksResponse } from '../types';

interface LibraryTabProps {
  data: BooksResponse | null;
  isLoading: boolean;
  onAddBook: (book: {
    title: string;
    author: string;
    category: string;
    total_pages: number;
    status: 'reading' | 'finished' | 'planned';
    notes?: string;
  }) => Promise<void>;
  onUpdateBook: (bookId: string, updates: Partial<BookItem>) => Promise<void>;
  onRecordProgress: (bookId: string, pagesRead: number) => Promise<void>;
  onDeleteBook: (bookId: string) => Promise<void>;
}

export const LibraryTab: React.FC<LibraryTabProps> = ({
  data,
  isLoading,
  onAddBook,
  onUpdateBook,
  onRecordProgress,
  onDeleteBook,
}) => {
  const [filter, setFilter] = useState<'all' | 'reading' | 'finished' | 'planned'>('all');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [finishingBook, setFinishingBook] = useState<BookItem | null>(null);
  const [rating, setRating] = useState<number>(5);
  const [insightNote, setInsightNote] = useState<string>('');
  const [justMarkedHabit, setJustMarkedHabit] = useState(false);

  // New book form state
  const [newTitle, setNewTitle] = useState('');
  const [newAuthor, setNewAuthor] = useState('');
  const [newCategory, setNewCategory] = useState('Саморазвитие');
  const [newTotalPages, setNewTotalPages] = useState('300');
  const [newStatus, setNewStatus] = useState<'reading' | 'finished' | 'planned'>('reading');
  const [newNotes, setNewNotes] = useState('');

  const books = data?.books || [];
  const stats = data?.stats || { total: 0, finished: 0, reading: 0, planned: 0, total_pages_read: 0 };

  const filteredBooks = books.filter((b) => {
    if (filter === 'all') return true;
    return b.status === filter;
  });

  const categories = [
    'Саморазвитие',
    'Продуктивность',
    'Спорт / Биохакинг',
    'IT / Код',
    'Психология',
    'Бизнес / Финансы',
    'Художественная',
  ];

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newAuthor.trim()) return;

    await onAddBook({
      title: newTitle.trim(),
      author: newAuthor.trim(),
      category: newCategory,
      total_pages: parseInt(newTotalPages, 10) || 300,
      status: newStatus,
      notes: newNotes.trim() || undefined,
    });

    setNewTitle('');
    setNewAuthor('');
    setNewNotes('');
    setIsAddModalOpen(false);
  };

  const handleFinishSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!finishingBook) return;

    await onUpdateBook(finishingBook.id, {
      status: 'finished',
      rating,
      notes: insightNote.trim() || finishingBook.notes,
      current_page: finishingBook.total_pages || 300,
      finished_date: new Date().toISOString().slice(0, 10),
    });

    setFinishingBook(null);
    setInsightNote('');
  };

  const handleQuickAddPages = async (bookId: string, pages: number) => {
    await onRecordProgress(bookId, pages);
    if (pages >= 10) {
      setJustMarkedHabit(true);
      setTimeout(() => setJustMarkedHabit(false), 4000);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-4 space-y-6 pb-28">
      {/* Toast Alert when habit is auto-marked */}
      {justMarkedHabit && (
        <div className="fixed top-20 left-1/2 -translate-x-1/2 z-50 bg-[#00d084] text-[#0b0f19] px-4 py-2.5 rounded-2xl shadow-xl shadow-[#00d084]/20 flex items-center space-x-2 text-xs font-bold animate-bounce">
          <CheckCircle2 className="w-4 h-4 fill-[#0b0f19] text-[#00d084]" />
          <span>+10 страниц записано! Привычка чтения на сегодня закрыта! 🎉</span>
        </div>
      )}

      {/* Top Header Card */}
      <div className="bg-gradient-to-r from-[#111726] via-[#161f36] to-[#111726] border border-[#1e293b] rounded-3xl p-5 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-48 h-48 bg-[#38bdf8]/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center space-x-2">
              <BookOpen className="w-5 h-5 text-[#38bdf8]" />
              <h2 className="text-lg font-bold text-white tracking-tight">Библиотека Атлета</h2>
              <span className="text-[10px] font-bold bg-[#38bdf8]/20 border border-[#38bdf8]/30 text-[#38bdf8] px-2 py-0.5 rounded-full">
                Книги & Инсайты
              </span>
            </div>
            <p className="text-xs text-[#94a3b8] mt-1">
              Отслеживай прочитанные книги, сохраняй ключевые мысли и закрывай норму от 10 стр./день.
            </p>
          </div>

          <button
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center justify-center space-x-2 bg-[#00d084] hover:bg-[#00b573] active:scale-95 text-[#0b0f19] font-bold text-xs px-4 py-2.5 rounded-2xl shadow-lg shadow-[#00d084]/20 transition-all shrink-0"
          >
            <Plus className="w-4 h-4" />
            <span>Добавить книгу</span>
          </button>
        </div>

        {/* KPI Counter Pills */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mt-5">
          <div className="bg-[#0b0f19]/70 border border-[#1e293b] rounded-2xl p-3 flex flex-col items-center text-center">
            <span className="text-[11px] text-[#94a3b8] font-medium">Всего в базе</span>
            <span className="text-xl font-bold text-white mt-0.5">{stats.total}</span>
          </div>

          <div className="bg-[#0b0f19]/70 border border-[#00d084]/30 rounded-2xl p-3 flex flex-col items-center text-center">
            <span className="text-[11px] text-[#00d084] font-medium flex items-center space-x-1">
              <Award className="w-3 h-3" />
              <span>Прочитано</span>
            </span>
            <span className="text-xl font-bold text-[#00d084] mt-0.5">{stats.finished}</span>
          </div>

          <div className="bg-[#0b0f19]/70 border border-[#38bdf8]/30 rounded-2xl p-3 flex flex-col items-center text-center">
            <span className="text-[11px] text-[#38bdf8] font-medium flex items-center space-x-1">
              <BookMarked className="w-3 h-3" />
              <span>Читаю сейчас</span>
            </span>
            <span className="text-xl font-bold text-[#38bdf8] mt-0.5">{stats.reading}</span>
          </div>

          <div className="bg-[#0b0f19]/70 border border-[#6366f1]/30 rounded-2xl p-3 flex flex-col items-center text-center">
            <span className="text-[11px] text-[#a5b4fc] font-medium">Прочитано страниц</span>
            <span className="text-xl font-bold text-white mt-0.5">{stats.total_pages_read}</span>
          </div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center space-x-2 overflow-x-auto pb-1 no-scrollbar">
        {[
          { id: 'all', label: `Все (${stats.total})` },
          { id: 'reading', label: `Читаю (${stats.reading})` },
          { id: 'finished', label: `Прочитано (${stats.finished})` },
          { id: 'planned', label: `В планах (${stats.planned})` },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setFilter(t.id as any)}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold shrink-0 transition-all ${
              filter === t.id
                ? 'bg-[#00d084] text-[#0b0f19] shadow-md shadow-[#00d084]/20'
                : 'bg-[#111726] border border-[#1e293b] text-[#94a3b8] hover:text-white'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Book Cards Grid */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="bg-[#111726] border border-[#1e293b] rounded-3xl p-10 flex flex-col items-center justify-center space-y-3">
            <Loader2 className="w-8 h-8 text-[#38bdf8] animate-spin" />
            <p className="text-xs text-[#94a3b8]">Загрузка библиотеки...</p>
          </div>
        ) : filteredBooks.length === 0 ? (
          <div className="bg-[#111726] border border-[#1e293b] rounded-3xl p-10 text-center space-y-3">
            <BookOpen className="w-10 h-10 text-[#64748b] mx-auto" />
            <p className="text-sm font-semibold text-white">В этой категории пока нет книг</p>
            <p className="text-xs text-[#94a3b8] max-w-sm mx-auto">
              Нажми «Добавить книгу», чтобы записать то, что читаешь сейчас или книги, которые уже прочитал!
            </p>
          </div>
        ) : (
          filteredBooks.map((book) => {
            const isReading = book.status === 'reading';
            const isFinished = book.status === 'finished';
            const curPage = book.current_page || 0;
            const totPage = book.total_pages || 1;
            const progressPct = Math.min(100, Math.round((curPage / totPage) * 100));

            return (
              <div
                key={book.id}
                className={`bg-[#111726] border rounded-3xl p-5 space-y-3.5 transition-all shadow-lg ${
                  isReading
                    ? 'border-[#38bdf8]/40 shadow-[#38bdf8]/5'
                    : isFinished
                    ? 'border-[#00d084]/30 shadow-[#00d084]/5'
                    : 'border-[#1e293b]'
                }`}
              >
                {/* Header Row */}
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                          isReading
                            ? 'bg-[#38bdf8]/20 text-[#38bdf8] border border-[#38bdf8]/30'
                            : isFinished
                            ? 'bg-[#00d084]/20 text-[#00d084] border border-[#00d084]/30'
                            : 'bg-zinc-800 text-zinc-300'
                        }`}
                      >
                        {isReading ? 'Читаю сейчас' : isFinished ? 'Прочитано' : 'В планах'}
                      </span>
                      <span className="text-[10px] text-[#94a3b8] bg-[#0b0f19] px-2 py-0.5 rounded-full border border-[#1e293b]">
                        {book.category}
                      </span>
                      {book.finished_date && (
                        <span className="text-[10px] text-[#64748b]">
                          Завершено: {book.finished_date}
                        </span>
                      )}
                    </div>

                    <h3 className="text-base font-bold text-white tracking-tight">{book.title}</h3>
                    <p className="text-xs text-[#94a3b8] font-medium">{book.author}</p>
                  </div>

                  {/* Rating Stars for finished books or Delete */}
                  <div className="flex items-center space-x-1 shrink-0">
                    {isFinished && book.rating && (
                      <div className="flex items-center space-x-0.5 mr-2 bg-[#f59e0b]/10 border border-[#f59e0b]/20 px-2 py-1 rounded-xl">
                        {[...Array(book.rating)].map((_, i) => (
                          <Star key={i} className="w-3.5 h-3.5 fill-[#f59e0b] text-[#f59e0b]" />
                        ))}
                      </div>
                    )}

                    <button
                      onClick={() => onDeleteBook(book.id)}
                      className="w-8 h-8 rounded-xl bg-[#0b0f19] hover:bg-rose-500/20 text-[#64748b] hover:text-rose-400 border border-[#1e293b] flex items-center justify-center transition-all"
                      title="Удалить книгу"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Progress Bar for Currently Reading */}
                {isReading && (
                  <div className="space-y-2 pt-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-[#94a3b8]">
                        Прогресс: <span className="text-white font-bold">{curPage}</span> из{' '}
                        <span className="text-white font-bold">{totPage}</span> стр.
                      </span>
                      <span className="text-[#38bdf8] font-bold">{progressPct}%</span>
                    </div>

                    <div className="w-full h-2.5 bg-[#0b0f19] border border-[#1e293b] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-[#38bdf8] to-[#00d084] rounded-full transition-all duration-500"
                        style={{ width: `${progressPct}%` }}
                      />
                    </div>

                    {/* Quick Reading Actions */}
                    <div className="flex flex-wrap items-center gap-2 pt-1.5">
                      <button
                        onClick={() => handleQuickAddPages(book.id, 10)}
                        className="flex items-center space-x-1.5 bg-[#00d084]/15 hover:bg-[#00d084]/25 border border-[#00d084]/30 text-[#00d084] px-3 py-1.5 rounded-xl text-xs font-bold transition-all active:scale-95"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>+10 стр (закрыть цель)</span>
                      </button>

                      <button
                        onClick={() => handleQuickAddPages(book.id, 25)}
                        className="bg-[#111726] hover:bg-[#1e293b] border border-[#1e293b] text-[#94a3b8] hover:text-white px-3 py-1.5 rounded-xl text-xs font-medium transition-all active:scale-95"
                      >
                        +25 стр
                      </button>

                      <button
                        onClick={() => {
                          setFinishingBook(book);
                          setRating(5);
                          setInsightNote(book.notes || '');
                        }}
                        className="flex items-center space-x-1.5 bg-[#6366f1]/20 hover:bg-[#6366f1]/30 border border-[#6366f1]/40 text-[#a5b4fc] px-3 py-1.5 rounded-xl text-xs font-bold transition-all ml-auto active:scale-95"
                      >
                        <Award className="w-3.5 h-3.5" />
                        <span>Завершить 🏆</span>
                      </button>
                    </div>
                  </div>
                )}

                {/* Key Insight Quote Block */}
                {book.notes && (
                  <div className="bg-[#0b0f19]/80 border-l-2 border-[#00d084] p-3 rounded-r-2xl space-y-1">
                    <span className="text-[10px] uppercase font-bold text-[#00d084] tracking-wider block">
                      💡 Главный инсайт:
                    </span>
                    <p className="text-xs text-[#cbd5e1] leading-relaxed italic">
                      «{book.notes}»
                    </p>
                  </div>
                )}

                {/* Start Reading Action for Planned */}
                {book.status === 'planned' && (
                  <div className="pt-1">
                    <button
                      onClick={() => onUpdateBook(book.id, { status: 'reading' })}
                      className="flex items-center space-x-1.5 bg-[#38bdf8]/20 hover:bg-[#38bdf8]/30 border border-[#38bdf8]/40 text-[#38bdf8] px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all active:scale-95"
                    >
                      <BookOpen className="w-3.5 h-3.5" />
                      <span>Начать читать</span>
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* MODAL: Add New Book */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="bg-[#111726] border border-[#1e293b] w-full max-w-md rounded-3xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#1e293b] pb-3">
              <div className="flex items-center space-x-2">
                <BookOpen className="w-5 h-5 text-[#00d084]" />
                <h3 className="text-base font-bold text-white">Добавить книгу</h3>
              </div>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="w-8 h-8 rounded-xl bg-[#0b0f19] text-[#94a3b8] hover:text-white flex items-center justify-center"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="space-y-3.5">
              <div>
                <label className="block text-[11px] font-semibold text-[#94a3b8] mb-1">
                  Название книги *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Например: Атомные привычки"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="w-full bg-[#0b0f19] border border-[#1e293b] rounded-2xl px-3.5 py-2.5 text-xs text-white placeholder-[#475569] focus:outline-none focus:border-[#00d084]"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-[#94a3b8] mb-1">
                  Автор *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Например: Джеймс Клир"
                  value={newAuthor}
                  onChange={(e) => setNewAuthor(e.target.value)}
                  className="w-full bg-[#0b0f19] border border-[#1e293b] rounded-2xl px-3.5 py-2.5 text-xs text-white placeholder-[#475569] focus:outline-none focus:border-[#00d084]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-[#94a3b8] mb-1">
                    Категория
                  </label>
                  <select
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    className="w-full bg-[#0b0f19] border border-[#1e293b] rounded-2xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#00d084]"
                  >
                    {categories.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-[#94a3b8] mb-1">
                    Всего страниц
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={newTotalPages}
                    onChange={(e) => setNewTotalPages(e.target.value)}
                    className="w-full bg-[#0b0f19] border border-[#1e293b] rounded-2xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#00d084]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-[#94a3b8] mb-1">
                  Статус
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { id: 'reading', label: 'Читаю' },
                    { id: 'finished', label: 'Прочитал' },
                    { id: 'planned', label: 'В планах' },
                  ].map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => setNewStatus(s.id as any)}
                      className={`py-2 rounded-xl text-xs font-semibold border transition-all ${
                        newStatus === s.id
                          ? 'bg-[#00d084]/20 border-[#00d084] text-[#00d084]'
                          : 'bg-[#0b0f19] border-[#1e293b] text-[#94a3b8]'
                      }`}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-[#94a3b8] mb-1">
                  Ключевая мысль / Инсайт (по желанию)
                </label>
                <textarea
                  rows={2}
                  placeholder="Главная цитата или идея, которую вынес из книги..."
                  value={newNotes}
                  onChange={(e) => setNewNotes(e.target.value)}
                  className="w-full bg-[#0b0f19] border border-[#1e293b] rounded-2xl p-3 text-xs text-white placeholder-[#475569] focus:outline-none focus:border-[#00d084] resize-none"
                />
              </div>

              <div className="pt-2 flex items-center space-x-3">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="w-1/2 py-2.5 rounded-2xl bg-[#0b0f19] text-[#94a3b8] font-semibold text-xs border border-[#1e293b]"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  className="w-1/2 py-2.5 rounded-2xl bg-[#00d084] hover:bg-[#00b573] text-[#0b0f19] font-bold text-xs shadow-lg shadow-[#00d084]/20"
                >
                  Сохранить
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Finish Book with Rating and Insight */}
      {finishingBook && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="bg-[#111726] border border-[#1e293b] w-full max-w-md rounded-3xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#1e293b] pb-3">
              <div className="flex items-center space-x-2">
                <Award className="w-5 h-5 text-[#f59e0b]" />
                <h3 className="text-base font-bold text-white">Книга прочитана! 🏆</h3>
              </div>
              <button
                onClick={() => setFinishingBook(null)}
                className="w-8 h-8 rounded-xl bg-[#0b0f19] text-[#94a3b8] hover:text-white flex items-center justify-center"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-[#94a3b8]">
              Поздравляем с завершением книги <strong className="text-white">«{finishingBook.title}»</strong>! Поставь оценку и зафиксируй главный инсайт.
            </p>

            <form onSubmit={handleFinishSubmit} className="space-y-4">
              <div>
                <label className="block text-[11px] font-semibold text-[#94a3b8] mb-1.5">
                  Твоя оценка
                </label>
                <div className="flex items-center space-x-2">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      type="button"
                      onClick={() => setRating(star)}
                      className="p-1.5 rounded-xl hover:scale-110 transition-transform"
                    >
                      <Star
                        className={`w-6 h-6 ${
                          star <= rating
                            ? 'fill-[#f59e0b] text-[#f59e0b]'
                            : 'text-zinc-600'
                        }`}
                      />
                    </button>
                  ))}
                  <span className="text-xs font-bold text-[#f59e0b] ml-2">{rating} из 5</span>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-[#94a3b8] mb-1">
                  Главный инсайт / Ключевой урок
                </label>
                <textarea
                  rows={3}
                  required
                  placeholder="Что самое ценное ты вынес из этой книги?"
                  value={insightNote}
                  onChange={(e) => setInsightNote(e.target.value)}
                  className="w-full bg-[#0b0f19] border border-[#1e293b] rounded-2xl p-3 text-xs text-white placeholder-[#475569] focus:outline-none focus:border-[#00d084] resize-none"
                />
              </div>

              <div className="pt-2 flex items-center space-x-3">
                <button
                  type="button"
                  onClick={() => setFinishingBook(null)}
                  className="w-1/2 py-2.5 rounded-2xl bg-[#0b0f19] text-[#94a3b8] font-semibold text-xs border border-[#1e293b]"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  className="w-1/2 py-2.5 rounded-2xl bg-[#00d084] hover:bg-[#00b573] text-[#0b0f19] font-bold text-xs shadow-lg shadow-[#00d084]/20"
                >
                  Зафиксировать в библиотеке
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
