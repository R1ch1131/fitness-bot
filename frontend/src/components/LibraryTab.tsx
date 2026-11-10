import { DarkSelect } from './DarkSelect';
import { CatalogPicker, CatalogFacts, Poster } from './CatalogPicker';
import type { CatalogInfo } from './CatalogPicker';
import React, { useState } from 'react';
import { 
  BookOpen, Plus, CheckCircle2, Star, Trash2, 
  Sparkles, X, BookMarked, Award, Loader2,
  Pencil, Hash, Check, Download, Upload
} from 'lucide-react';
import type { BookItem, BooksResponse } from '../types';

interface LibraryTabProps {
  data: BooksResponse | null;
  isLoading: boolean;
  onAddBook: (book: {
    catalog?: CatalogInfo | null;
    cover_image?: string | null;
    title: string;
    author: string;
    category: string;
    total_pages: number;
    current_page?: number;
    status: 'reading' | 'finished' | 'planned';
    rating?: number;
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
  const [editingBook, setEditingBook] = useState<BookItem | null>(null);
  const [justMarkedHabit, setJustMarkedHabit] = useState(false);

  // Inline custom progress logging state
  const [inlineAdderBookId, setInlineAdderBookId] = useState<string | null>(null);
  const [inlinePagesInput, setInlinePagesInput] = useState<string>('15');
  const [inlineDirectPageBookId, setInlineDirectPageBookId] = useState<string | null>(null);
  const [inlineDirectPageInput, setInlineDirectPageInput] = useState<string>('');

  // New book form state
  const [newCatalog, setNewCatalog] = useState<CatalogInfo | null>(null);
  const [newCover, setNewCover] = useState('');
  const [editCatalog, setEditCatalog] = useState<CatalogInfo | null>(null);
  const [editCover, setEditCover] = useState('');
  const [catalogBusy, setCatalogBusy] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newAuthor, setNewAuthor] = useState('');
  const [newCategory, setNewCategory] = useState('Саморазвитие');
  const [newTotalPages, setNewTotalPages] = useState('300');
  const [newCurrentPage, setNewCurrentPage] = useState('0');
  const [newStatus, setNewStatus] = useState<'reading' | 'finished' | 'planned'>('reading');
  const [newRating, setNewRating] = useState<number>(8.5);
  const [newNotes, setNewNotes] = useState('');

  // Edit book form state
  const [editTitle, setEditTitle] = useState('');
  const [editAuthor, setEditAuthor] = useState('');
  const [editCategory, setEditCategory] = useState('Саморазвитие');
  const [editTotalPages, setEditTotalPages] = useState('300');
  const [editCurrentPage, setEditCurrentPage] = useState('0');
  const [editStatus, setEditStatus] = useState<'reading' | 'finished' | 'planned'>('reading');
  const [editRating, setEditRating] = useState<number>(8.5);
  const [editNotes, setEditNotes] = useState('');

  const books = data?.books || [];
  const stats = data?.stats || { total: 0, finished: 0, reading: 0, planned: 0, total_pages_read: 0, library_total_pages: 0 };

  // Always prioritize currently reading books at the top of the list
  const sortedBooks = [...books].sort((a, b) => {
    const priority: Record<string, number> = { reading: 0, finished: 1, planned: 2 };
    const pA = priority[a.status] ?? 99;
    const pB = priority[b.status] ?? 99;
    if (pA !== pB) return pA - pB;
    const dateA = a.finished_date || a.created_at || '';
    const dateB = b.finished_date || b.created_at || '';
    return dateB.localeCompare(dateA);
  });

  const filteredBooks = sortedBooks.filter((b) => {
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

  const handleOpenAddModal = () => {
    setNewCatalog(null); setNewCover('');
    setNewTitle('');
    setNewAuthor('');
    setNewCategory('Саморазвитие');
    setNewTotalPages('300');
    setNewCurrentPage('0');
    setNewStatus('reading');
    setNewRating(5);
    setNewNotes('');
    setIsAddModalOpen(true);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newAuthor.trim()) return;

    const tot = parseInt(newTotalPages, 10) || 300;
    const cur = newStatus === 'finished' ? tot : (parseInt(newCurrentPage, 10) || 0);

    await onAddBook({
      catalog: newCatalog, cover_image: newCover,
      title: newTitle.trim(),
      author: newAuthor.trim(),
      category: newCategory,
      total_pages: tot,
      current_page: cur,
      status: newStatus,
      rating: newStatus === 'finished' ? newRating : undefined,
      notes: newNotes.trim() || undefined,
    });

    setIsAddModalOpen(false);
  };

  const handleOpenEditModal = (book: BookItem) => {
    setEditingBook(book);
    setEditCatalog(book.catalog || null); setEditCover(book.cover_image || '');
    setEditTitle(book.title);
    setEditAuthor(book.author);
    setEditCategory(book.category || 'Саморазвитие');
    setEditTotalPages(String(book.total_pages || 300));
    setEditCurrentPage(String(book.current_page || 0));
    setEditStatus(book.status);
    setEditRating(book.rating || 5);
    setEditNotes(book.notes || '');
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingBook || !editTitle.trim() || !editAuthor.trim()) return;

    const tot = parseInt(editTotalPages, 10) || 300;
    const cur = editStatus === 'finished' ? tot : (parseInt(editCurrentPage, 10) || 0);

    await onUpdateBook(editingBook.id, {
      catalog: editCatalog, cover_image: editCover,
      title: editTitle.trim(),
      author: editAuthor.trim(),
      category: editCategory,
      total_pages: tot,
      current_page: cur,
      status: editStatus,
      rating: editStatus === 'finished' ? editRating : undefined,
      notes: editNotes.trim() || undefined,
    });

    setEditingBook(null);
  };

  const handleQuickAddPages = async (bookId: string, pages: number) => {
    await onRecordProgress(bookId, pages);
    if (pages >= 10) {
      setJustMarkedHabit(true);
      setTimeout(() => setJustMarkedHabit(false), 4000);
    }
  };

  const handleCustomPagesSubmit = async (bookId: string) => {
    const pages = parseInt(inlinePagesInput, 10);
    if (isNaN(pages) || pages <= 0) return;
    await handleQuickAddPages(bookId, pages);
    setInlineAdderBookId(null);
  };

  const handleDirectPageSubmit = async (book: BookItem) => {
    const targetPage = parseInt(inlineDirectPageInput, 10);
    if (isNaN(targetPage) || targetPage < 0) return;
    const oldPage = book.current_page || 0;
    const diff = targetPage - oldPage;

    await onUpdateBook(book.id, {
      current_page: targetPage
    });

    if (diff >= 10) {
      setJustMarkedHabit(true);
      setTimeout(() => setJustMarkedHabit(false), 4000);
    }
    setInlineDirectPageBookId(null);
  };

  const handleExportBackup = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(books, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `athlete_books_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleImportBackup = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileReader = new FileReader();
    if (e.target.files && e.target.files[0]) {
      fileReader.readAsText(e.target.files[0], "UTF-8");
      fileReader.onload = async (event) => {
        try {
          const parsed = JSON.parse(event.target?.result as string);
          const booksToRestore = Array.isArray(parsed) ? parsed : (parsed.books || []);
          if (booksToRestore.length > 0) {
            const res = await fetch('/api/books/sync_all', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ books: booksToRestore }),
            });
            if (res.ok) {
              window.location.reload();
            }
          }
        } catch (err) {
          alert('Ошибка чтения файла резервной копии');
        }
      };
    }
  };

  const libTotalPages = stats.library_total_pages || 0;
  const pagesReadPct = libTotalPages > 0 ? Math.min(100, Math.round((stats.total_pages_read / libTotalPages) * 100)) : 0;

  return (
    <div className="pulse-library max-w-4xl mx-auto px-4 py-4 space-y-6 pb-28">
      {/* Toast Alert when habit is auto-marked */}
      {justMarkedHabit && (
        <div className="fixed top-20 left-1/2 -translate-x-1/2 z-50 bg-[#79c5a6] text-[#10261b] px-4 py-2.5 rounded-2xl shadow-xl shadow-[#218d79]/20 flex items-center space-x-2 text-xs font-bold animate-bounce">
          <CheckCircle2 className="w-4 h-4 fill-[#fffdf5] text-[#79c5a6]" />
          <span>+10 страниц записано! Привычка чтения на сегодня закрыта! 🎉</span>
        </div>
      )}

      {/* Top Header Card */}
      <div className="pulse-library-header bg-[#19221f] border border-[#33473b] rounded-3xl p-5 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-48 h-48 bg-[#288f97]/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center space-x-2">
              <BookOpen className="w-5 h-5 text-[#81c6ca]" />
              <h2 className="text-lg font-bold text-[#e6eee8] tracking-tight">Между страницами</h2>
              <span className="text-[10px] font-bold bg-[#288f97]/20 border border-[#81c6ca]/30 text-[#81c6ca] px-2 py-0.5 rounded-full">
                Книги & Инсайты
              </span>
            </div>
            <p className="text-xs text-[#a4b8aa] mt-1">
              Отслеживай прочитанные книги, сохраняй ключевые мысли и закрывай ежедневную норму чтения от 10 стр./день.
            </p>
          </div>

          <div className="flex items-center space-x-2 shrink-0">
            <button
              onClick={handleExportBackup}
              className="w-9 h-9 rounded-2xl bg-[#101714] hover:bg-[#33473b] text-[#a4b8aa] hover:text-[#e6eee8] border border-[#33473b] flex items-center justify-center transition-all"
              title="Скачать резервную копию библиотеки (.json)"
            >
              <Download className="w-4 h-4" />
            </button>

            <label
              className="w-9 h-9 rounded-2xl bg-[#101714] hover:bg-[#33473b] text-[#a4b8aa] hover:text-[#e6eee8] border border-[#33473b] flex items-center justify-center cursor-pointer transition-all"
              title="Восстановить библиотеку из файла (.json)"
            >
              <Upload className="w-4 h-4" />
              <input type="file" accept=".json" onChange={handleImportBackup} className="hidden" />
            </label>

            <button
              onClick={handleOpenAddModal}
              className="flex items-center justify-center space-x-2 bg-[#79c5a6] hover:bg-[#90d4b8] active:scale-95 text-[#10261b] font-bold text-xs px-4 py-2.5 rounded-2xl shadow-lg shadow-[#218d79]/20 transition-all shrink-0"
            >
              <Plus className="w-4 h-4" />
              <span>Добавить книгу</span>
            </button>
          </div>
        </div>

        {/* KPI Counter Pills */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mt-5">
          <div className="bg-[#101714]/70 border border-[#33473b] rounded-2xl p-3 flex flex-col items-center text-center">
            <span className="text-[11px] text-[#a4b8aa] font-medium">Всего в базе</span>
            <span className="text-xl font-bold text-[#e6eee8] mt-0.5">{stats.total}</span>
            <span className="text-[10px] text-[#91a797] mt-0.5">книг</span>
          </div>

          <div className="bg-[#101714]/70 border border-[#79c5a6]/30 rounded-2xl p-3 flex flex-col items-center text-center">
            <span className="text-[11px] text-[#79c5a6] font-medium flex items-center space-x-1">
              <Award className="w-3 h-3" />
              <span>Прочитано</span>
            </span>
            <span className="text-xl font-bold text-[#79c5a6] mt-0.5">{stats.finished}</span>
            <span className="text-[10px] text-[#79c5a6]/70 mt-0.5">завершено</span>
          </div>

          <div className="bg-[#101714]/70 border border-[#81c6ca]/30 rounded-2xl p-3 flex flex-col items-center text-center">
            <span className="text-[11px] text-[#81c6ca] font-medium flex items-center space-x-1">
              <BookMarked className="w-3 h-3" />
              <span>Читаю сейчас</span>
            </span>
            <span className="text-xl font-bold text-[#81c6ca] mt-0.5">{stats.reading}</span>
            <span className="text-[10px] text-[#81c6ca]/70 mt-0.5">в процессе</span>
          </div>

          <div className="bg-[#101714]/70 border border-[#e7a27d]/30 rounded-2xl p-3 flex flex-col items-center text-center">
            <span className="text-[11px] text-[#dcaf89] font-medium">Прочитано страниц</span>
            <span className="text-xl font-bold text-[#e6eee8] mt-0.5">{stats.total_pages_read}</span>
            <span className="text-[10px] text-[#a4b8aa] mt-0.5">
              {libTotalPages > 0 ? `из ${libTotalPages} стр. (${pagesReadPct}%)` : 'всего'}
            </span>
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
                ? 'bg-[#79c5a6] text-[#10261b] shadow-md shadow-[#218d79]/20'
                : 'bg-[#19221f] border border-[#33473b] text-[#a4b8aa] hover:text-[#e6eee8]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Book Cards Grid */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="bg-[#19221f] border border-[#33473b] rounded-3xl p-10 flex flex-col items-center justify-center space-y-3">
            <Loader2 className="w-8 h-8 text-[#81c6ca] animate-spin" />
            <p className="text-xs text-[#a4b8aa]">Загрузка библиотеки...</p>
          </div>
        ) : filteredBooks.length === 0 ? (
          <div className="bg-[#19221f] border border-[#33473b] rounded-3xl p-10 text-center space-y-3">
            <BookOpen className="w-10 h-10 text-[#91a797] mx-auto" />
            <p className="text-sm font-semibold text-[#e6eee8]">В этой категории пока нет книг</p>
            <p className="text-xs text-[#a4b8aa] max-w-sm mx-auto">
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
                className={`bg-[#19221f] border rounded-3xl p-5 space-y-3.5 transition-all shadow-lg ${
                  isReading
                    ? 'border-[#81c6ca]/40 shadow-[#288f97]/5'
                    : isFinished
                    ? 'border-[#79c5a6]/30 shadow-[#218d79]/5'
                    : 'border-[#33473b]'
                }`}
              >
                <div className="book-cover-row"><Poster image={book.cover_image} title={book.title} /><div><span className="catalog-eyebrow">{book.status === 'reading' ? 'Между страницами' : 'На моей полке'}</span><CatalogFacts info={book.catalog} /></div></div>
                {/* Header Row */}
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                          isReading
                            ? 'bg-[#288f97]/20 text-[#81c6ca] border border-[#81c6ca]/30'
                            : isFinished
                            ? 'bg-[#79c5a6]/20 text-[#79c5a6] border border-[#79c5a6]/30'
                            : 'bg-zinc-800 text-zinc-300'
                        }`}
                      >
                        {isReading ? 'Читаю сейчас' : isFinished ? 'Прочитано' : 'В планах'}
                      </span>
                      <span className="text-[10px] text-[#a4b8aa] bg-[#101714] px-2 py-0.5 rounded-full border border-[#33473b]">
                        {book.category}
                      </span>
                      {isFinished && book.finished_date && (
                        <span className="text-[10px] text-[#91a797]">
                          Завершено: {book.finished_date}
                        </span>
                      )}
                    </div>

                    <h3 className="text-base font-bold text-[#e6eee8] tracking-tight">{book.title}</h3>
                    <p className="text-xs text-[#a4b8aa] font-medium">{book.author}</p>
                  </div>

                  {/* Actions & Rating */}
                  <div className="flex items-center space-x-1.5 shrink-0">
                    {book.rating !== undefined && book.rating !== null && (
                      <div className="flex items-center space-x-1.5 mr-1 bg-[#b57935]/15 border border-[#d7ad76]/30 px-2.5 py-1 rounded-xl text-xs font-bold text-[#d7ad76]">
                        <Star className="w-3.5 h-3.5 fill-[#d7ad76] text-[#d7ad76]" />
                        <span>{book.rating} / 10</span>
                      </div>
                    )}

                    {/* Edit Book Button */}
                    <button
                      onClick={() => handleOpenEditModal(book)}
                      className="w-8 h-8 rounded-xl bg-[#101714] hover:bg-[#33473b] text-[#a4b8aa] hover:text-[#e6eee8] border border-[#33473b] flex items-center justify-center transition-all"
                      title="Редактировать книгу"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>

                    {/* Delete Book Button */}
                    <button
                      onClick={() => onDeleteBook(book.id)}
                      className="w-8 h-8 rounded-xl bg-[#101714] hover:bg-rose-500/20 text-[#91a797] hover:text-rose-400 border border-[#33473b] flex items-center justify-center transition-all"
                      title="Удалить книгу"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Finished Book Page Badge */}
                {isFinished && (
                  <div className="flex items-center space-x-2 text-xs text-[#79c5a6] font-medium bg-[#79c5a6]/10 border border-[#79c5a6]/20 px-3 py-1.5 rounded-xl w-fit">
                    <CheckCircle2 className="w-4 h-4 text-[#79c5a6]" />
                    <span>Прочитано целиком: {book.total_pages} из {book.total_pages} стр. (100%)</span>
                  </div>
                )}

                {/* Progress Bar for Currently Reading */}
                {isReading && (
                  <div className="space-y-2 pt-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-[#a4b8aa]">
                        Прогресс:{' '}
                        <button
                          onClick={() => {
                            setInlineDirectPageBookId(book.id);
                            setInlineDirectPageInput(String(curPage));
                          }}
                          className="text-[#e6eee8] font-bold underline hover:text-[#81c6ca] transition-colors"
                          title="Нажми, чтобы изменить текущую страницу"
                        >
                          {curPage}
                        </button>{' '}
                        из <span className="text-[#e6eee8] font-bold">{totPage}</span> стр.
                      </span>
                      <span className="text-[#81c6ca] font-bold">{progressPct}%</span>
                    </div>

                    <div className="w-full h-2.5 bg-[#101714] border border-[#33473b] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-[#288f97] to-[#218d79] rounded-full transition-all duration-500"
                        style={{ width: `${progressPct}%` }}
                      />
                    </div>

                    {/* Quick Reading Actions */}
                    <div className="flex flex-wrap items-center gap-2 pt-1.5">
                      <button
                        onClick={() => handleQuickAddPages(book.id, 10)}
                        className="flex items-center space-x-1.5 bg-[#79c5a6]/15 hover:bg-[#79c5a6]/25 border border-[#79c5a6]/30 text-[#79c5a6] px-3 py-1.5 rounded-xl text-xs font-bold transition-all active:scale-95"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>+10 стр (цель дня)</span>
                      </button>

                      <button
                        onClick={() => handleQuickAddPages(book.id, 25)}
                        className="bg-[#19221f] hover:bg-[#33473b] border border-[#33473b] text-[#a4b8aa] hover:text-[#e6eee8] px-3 py-1.5 rounded-xl text-xs font-medium transition-all active:scale-95"
                      >
                        +25 стр
                      </button>

                      {/* Custom amount button */}
                      <button
                        onClick={() => {
                          setInlineAdderBookId(inlineAdderBookId === book.id ? null : book.id);
                          setInlinePagesInput('15');
                        }}
                        className={`border px-3 py-1.5 rounded-xl text-xs font-medium transition-all active:scale-95 ${
                          inlineAdderBookId === book.id
                            ? 'bg-[#288f97]/20 border-[#81c6ca] text-[#81c6ca]'
                            : 'bg-[#19221f] hover:bg-[#33473b] border-[#33473b] text-[#a4b8aa] hover:text-[#e6eee8]'
                        }`}
                      >
                        + Своё кол-во
                      </button>

                      {/* Direct page setter button */}
                      <button
                        onClick={() => {
                          setInlineDirectPageBookId(inlineDirectPageBookId === book.id ? null : book.id);
                          setInlineDirectPageInput(String(curPage));
                        }}
                        className={`flex items-center space-x-1 border px-2.5 py-1.5 rounded-xl text-xs font-medium transition-all active:scale-95 ${
                          inlineDirectPageBookId === book.id
                            ? 'bg-[#8c613e]/20 border-[#e7a27d] text-[#dcaf89]'
                            : 'bg-[#19221f] hover:bg-[#33473b] border-[#33473b] text-[#a4b8aa] hover:text-[#e6eee8]'
                        }`}
                        title="Ввести номер страницы"
                      >
                        <Hash className="w-3 h-3" />
                        <span>Стр.</span>
                      </button>


                    </div>

                    {/* Inline custom page adder form */}
                    {inlineAdderBookId === book.id && (
                      <div className="flex items-center space-x-2 bg-[#101714] border border-[#81c6ca]/40 p-2.5 rounded-2xl animate-fade-in mt-2">
                        <span className="text-xs text-[#a4b8aa] shrink-0">Прочитал:</span>
                        <input
                          type="number"
                          min="1"
                          max={totPage - curPage}
                          value={inlinePagesInput}
                          onChange={(e) => setInlinePagesInput(e.target.value)}
                          className="w-20 bg-[#19221f] border border-[#33473b] rounded-xl px-2.5 py-1 text-xs text-[#e6eee8] focus:outline-none focus:border-[#81c6ca]"
                          placeholder="стр."
                          autoFocus
                        />
                        <span className="text-xs text-[#91a797]">стр.</span>
                        <button
                          onClick={() => handleCustomPagesSubmit(book.id)}
                          className="bg-[#79c5a6] hover:bg-[#90d4b8] text-[#10261b] text-xs font-bold px-3 py-1 rounded-xl transition-all ml-auto flex items-center space-x-1"
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>Записать</span>
                        </button>
                        <button
                          onClick={() => setInlineAdderBookId(null)}
                          className="text-[#91a797] hover:text-[#e6eee8] p-1"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}

                    {/* Inline direct page setter form */}
                    {inlineDirectPageBookId === book.id && (
                      <div className="flex items-center space-x-2 bg-[#101714] border border-[#e7a27d]/40 p-2.5 rounded-2xl animate-fade-in mt-2">
                        <span className="text-xs text-[#a4b8aa] shrink-0">Установить страницу:</span>
                        <input
                          type="number"
                          min="0"
                          max={totPage}
                          value={inlineDirectPageInput}
                          onChange={(e) => setInlineDirectPageInput(e.target.value)}
                          className="w-20 bg-[#19221f] border border-[#33473b] rounded-xl px-2.5 py-1 text-xs text-[#e6eee8] focus:outline-none focus:border-[#e7a27d]"
                          placeholder="стр."
                          autoFocus
                        />
                        <span className="text-xs text-[#91a797]">из {totPage}</span>
                        <button
                          onClick={() => handleDirectPageSubmit(book)}
                          className="bg-[#e7a27d] hover:bg-[#4f46e5] text-[#e6eee8] text-xs font-bold px-3 py-1 rounded-xl transition-all ml-auto flex items-center space-x-1"
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>Сохранить</span>
                        </button>
                        <button
                          onClick={() => setInlineDirectPageBookId(null)}
                          className="text-[#91a797] hover:text-[#e6eee8] p-1"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* Key Insight Quote Block */}
                {book.notes && (
                  <div className="bg-[#101714]/80 border-l-2 border-[#79c5a6] p-3 rounded-r-2xl space-y-1">
                    <span className="text-[10px] uppercase font-bold text-[#79c5a6] tracking-wider block">
                      💡 Главный инсайт:
                    </span>
                    <p className="text-xs text-[#c0d0c3] leading-relaxed italic">
                      «{book.notes}»
                    </p>
                  </div>
                )}

                {/* Start Reading Action for Planned */}
                {book.status === 'planned' && (
                  <div className="flex items-center justify-between pt-1">
                    <span className="text-xs text-[#91a797]">Объём: ~{book.total_pages || 300} стр.</span>
                    <button
                      onClick={() => onUpdateBook(book.id, { status: 'reading' })}
                      className="flex items-center space-x-1.5 bg-[#288f97]/20 hover:bg-[#288f97]/30 border border-[#81c6ca]/40 text-[#81c6ca] px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all active:scale-95"
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
          <div className="bg-[#19221f] border border-[#33473b] w-full max-w-md rounded-3xl p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#33473b] pb-3">
              <div className="flex items-center space-x-2">
                <BookOpen className="w-5 h-5 text-[#79c5a6]" />
                <h3 className="text-base font-bold text-[#e6eee8]">Добавить книгу</h3>
              </div>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="w-8 h-8 rounded-xl bg-[#101714] text-[#a4b8aa] hover:text-[#e6eee8] flex items-center justify-center"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="space-y-3.5">
              <div>
                <label className="block text-[11px] font-semibold text-[#a4b8aa] mb-1">
                  Название книги *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Например: Атомные привычки"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="w-full bg-[#101714] border border-[#33473b] rounded-2xl px-3.5 py-2.5 text-xs text-[#e6eee8] placeholder-[#475569] focus:outline-none focus:border-[#79c5a6]"
                />
              </div>

              <CatalogPicker kind="book" title={newTitle} author={newAuthor} info={newCatalog} image={newCover} onBusy={setCatalogBusy} onImage={setNewCover} onSelect={info => { setNewCatalog(info); setNewCover(info.image || ''); setNewTitle(info.title); setNewAuthor(info.author || ''); if (info.pages) setNewTotalPages(String(info.pages)); }} />
              <div>
                <label className="block text-[11px] font-semibold text-[#a4b8aa] mb-1">
                  Автор *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Например: Джеймс Клир"
                  value={newAuthor}
                  onChange={(e) => setNewAuthor(e.target.value)}
                  className="w-full bg-[#101714] border border-[#33473b] rounded-2xl px-3.5 py-2.5 text-xs text-[#e6eee8] placeholder-[#475569] focus:outline-none focus:border-[#79c5a6]"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-[#a4b8aa] mb-1">
                  Категория
                </label>
                <DarkSelect label="Категория книги" value={newCategory} onChange={setNewCategory} options={categories.map(value => ({value,label:value}))} />
              </div>

              {/* Status Selector */}
              <div>
                <label className="block text-[11px] font-semibold text-[#a4b8aa] mb-1">
                  Статус книги
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
                          ? 'bg-[#79c5a6]/20 border-[#79c5a6] text-[#79c5a6]'
                          : 'bg-[#101714] border-[#33473b] text-[#a4b8aa] disabled:opacity-30 disabled:cursor-not-allowed'
                      }`}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Page inputs depending on status */}
              {newStatus === 'reading' && (
                <div className="grid grid-cols-2 gap-3 bg-[#101714]/60 p-3 rounded-2xl border border-[#33473b]">
                  <div>
                    <label className="block text-[10px] font-semibold text-[#81c6ca] mb-1">
                      Текущая стр. (уже прочитано)
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={newCurrentPage}
                      onChange={(e) => setNewCurrentPage(e.target.value)}
                      placeholder="0"
                      className="w-full bg-[#101714] border border-[#33473b] rounded-xl px-3 py-1.5 text-xs text-[#e6eee8] focus:outline-none focus:border-[#81c6ca]"
                    />
                    <span className="text-[9px] text-[#91a797]">На какой ты странице</span>
                  </div>

                  <div>
                    <label className="block text-[10px] font-semibold text-[#a4b8aa] mb-1">
                      Всего страниц в книге *
                    </label>
                    <input
                      type="number"
                      min="1"
                      value={newTotalPages}
                      onChange={(e) => setNewTotalPages(e.target.value)}
                      placeholder="300"
                      className="w-full bg-[#101714] border border-[#33473b] rounded-xl px-3 py-1.5 text-xs text-[#e6eee8] focus:outline-none focus:border-[#79c5a6]"
                    />
                    <span className="text-[9px] text-[#91a797]">Общий объём книги</span>
                  </div>
                </div>
              )}

              {newStatus === 'finished' && (
                <div className="space-y-3 bg-[#79c5a6]/5 p-3 rounded-2xl border border-[#79c5a6]/20">
                  <div>
                    <label className="block text-[10px] font-semibold text-[#79c5a6] mb-1">
                      Всего страниц в книге *
                    </label>
                    <input
                      type="number"
                      min="1"
                      value={newTotalPages}
                      onChange={(e) => setNewTotalPages(e.target.value)}
                      placeholder="300"
                      className="w-full bg-[#101714] border border-[#33473b] rounded-xl px-3 py-1.5 text-xs text-[#e6eee8] focus:outline-none focus:border-[#79c5a6]"
                    />
                    <span className="text-[9px] text-[#79c5a6]/80">
                      ✨ Все {newTotalPages || 0} стр. будут учтены в общем счетчике прочитанного!
                    </span>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="text-[10px] font-semibold text-[#a4b8aa]">
                        Оценка (по 10-балльной шкале, можно дробные: 5.5, 8.5)
                      </label>
                      <span className="text-xs font-bold text-[#d7ad76] flex items-center space-x-1">
                        <Star className="w-3.5 h-3.5 fill-[#d7ad76]" />
                        <span>{newRating} / 10</span>
                      </span>
                    </div>

                    <div className="flex items-center space-x-3 bg-[#101714] p-2.5 rounded-2xl border border-[#33473b]">
                      <input
                        type="range"
                        min="1"
                        max="10"
                        step="0.5"
                        value={newRating}
                        onChange={(e) => setNewRating(parseFloat(e.target.value))}
                        className="w-full accent-[#b57935] cursor-pointer"
                      />
                      <div className="flex items-center space-x-1 shrink-0">
                        <input
                          type="number"
                          min="1"
                          max="10"
                          step="0.1"
                          value={newRating}
                          onChange={(e) => {
                            const val = parseFloat(e.target.value);
                            if (!isNaN(val)) setNewRating(Math.max(1, Math.min(10, val)));
                          }}
                          className="w-14 bg-[#19221f] border border-[#33473b] rounded-xl px-2 py-1 text-xs text-center font-bold text-[#d7ad76] focus:outline-none focus:border-[#d7ad76]"
                        />
                        <span className="text-xs text-[#91a797]">/10</span>
                      </div>
                    </div>

                    {/* Quick Preset Pills */}
                    <div className="flex flex-wrap items-center gap-1.5 mt-2">
                      {[5, 5.5, 6, 7, 7.5, 8, 8.5, 9, 9.5, 10].map((val) => (
                        <button
                          key={val}
                          type="button"
                          onClick={() => setNewRating(val)}
                          className={`px-2 py-0.5 rounded-lg text-[10px] font-semibold border transition-all ${
                            newRating === val
                              ? 'bg-[#b57935]/20 border-[#d7ad76] text-[#d7ad76]'
                              : 'bg-[#101714] border-[#33473b] text-[#a4b8aa] hover:text-[#e6eee8]'
                          }`}
                        >
                          {val}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {newStatus === 'planned' && (
                <div>
                  <label className="block text-[11px] font-semibold text-[#a4b8aa] mb-1">
                    Всего страниц (примерно)
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={newTotalPages}
                    onChange={(e) => setNewTotalPages(e.target.value)}
                    className="w-full bg-[#101714] border border-[#33473b] rounded-2xl px-3.5 py-2 text-xs text-[#e6eee8] focus:outline-none focus:border-[#79c5a6]"
                  />
                </div>
              )}

              <div>
                <label className="block text-[11px] font-semibold text-[#a4b8aa] mb-1">
                  Ключевая мысль / Инсайт (по желанию)
                </label>
                <textarea
                  rows={2}
                  placeholder="Главная цитата или идея книги..."
                  value={newNotes}
                  onChange={(e) => setNewNotes(e.target.value)}
                  className="w-full bg-[#101714] border border-[#33473b] rounded-2xl p-3 text-xs text-[#e6eee8] placeholder-[#475569] focus:outline-none focus:border-[#79c5a6] resize-none"
                />
              </div>

              <div className="pt-2 flex items-center space-x-3">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="w-1/2 py-2.5 rounded-2xl bg-[#101714] text-[#a4b8aa] font-semibold text-xs border border-[#33473b]"
                >
                  Отмена
                </button>
                <button
                  disabled={catalogBusy}
                  type="submit"
                  className="w-1/2 py-2.5 rounded-2xl bg-[#79c5a6] hover:bg-[#90d4b8] text-[#10261b] font-bold text-xs shadow-lg shadow-[#218d79]/20"
                >
                  Сохранить
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Edit Existing Book */}
      {editingBook && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="bg-[#19221f] border border-[#33473b] w-full max-w-md rounded-3xl p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#33473b] pb-3">
              <div className="flex items-center space-x-2">
                <Pencil className="w-5 h-5 text-[#81c6ca]" />
                <h3 className="text-base font-bold text-[#e6eee8]">Редактировать книгу</h3>
              </div>
              <button
                onClick={() => setEditingBook(null)}
                className="w-8 h-8 rounded-xl bg-[#101714] text-[#a4b8aa] hover:text-[#e6eee8] flex items-center justify-center"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleEditSubmit} className="space-y-3.5">
              <div>
                <label className="block text-[11px] font-semibold text-[#a4b8aa] mb-1">
                  Название книги *
                </label>
                <input
                  type="text"
                  required
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  className="w-full bg-[#101714] border border-[#33473b] rounded-2xl px-3.5 py-2.5 text-xs text-[#e6eee8] focus:outline-none focus:border-[#81c6ca]"
                />
              </div>

              <CatalogPicker kind="book" title={editTitle} author={editAuthor} info={editCatalog} image={editCover} onBusy={setCatalogBusy} onImage={setEditCover} onSelect={info => { setEditCatalog(info); setEditCover(info.image || ''); setEditTitle(info.title); setEditAuthor(info.author || ''); if (info.pages) setEditTotalPages(String(info.pages)); }} />
              <div>
                <label className="block text-[11px] font-semibold text-[#a4b8aa] mb-1">
                  Автор *
                </label>
                <input
                  type="text"
                  required
                  value={editAuthor}
                  onChange={(e) => setEditAuthor(e.target.value)}
                  className="w-full bg-[#101714] border border-[#33473b] rounded-2xl px-3.5 py-2.5 text-xs text-[#e6eee8] focus:outline-none focus:border-[#81c6ca]"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-[#a4b8aa] mb-1">
                  Категория
                </label>
                <DarkSelect label="Категория книги" value={editCategory} onChange={setEditCategory} options={categories.map(value => ({value,label:value}))} />
              </div>

              {/* Status Selector */}
              <div>
                <label className="block text-[11px] font-semibold text-[#a4b8aa] mb-1">
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
                      disabled={s.id === 'finished' && editingBook.status !== 'finished'}
                      title={s.id === 'finished' && editingBook.status !== 'finished' ? 'Книга завершится, когда будет прочитана последняя страница' : undefined}
                      onClick={() => setEditStatus(s.id as any)}
                      className={`py-2 rounded-xl text-xs font-semibold border transition-all ${
                        editStatus === s.id
                          ? 'bg-[#288f97]/20 border-[#81c6ca] text-[#81c6ca]'
                          : 'bg-[#101714] border-[#33473b] text-[#a4b8aa] disabled:opacity-30 disabled:cursor-not-allowed'
                      }`}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Page count inputs */}
              <div className="grid grid-cols-2 gap-3 bg-[#101714]/60 p-3 rounded-2xl border border-[#33473b]">
                <div>
                  <label className="block text-[10px] font-semibold text-[#a4b8aa] mb-1">
                    {editStatus === 'reading' ? 'Текущая страница' : 'Прочитано стр.'}
                  </label>
                  <input
                    type="number"
                    min="0"
                    disabled={editStatus === 'finished'}
                    value={editStatus === 'finished' ? editTotalPages : editCurrentPage}
                    onChange={(e) => setEditCurrentPage(e.target.value)}
                    className="w-full bg-[#101714] border border-[#33473b] rounded-xl px-3 py-1.5 text-xs text-[#e6eee8] focus:outline-none focus:border-[#81c6ca] disabled:opacity-50"
                  />
                </div>

                <div>
                  <label className="block text-[10px] font-semibold text-[#a4b8aa] mb-1">
                    Всего страниц
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={editTotalPages}
                    onChange={(e) => setEditTotalPages(e.target.value)}
                    className="w-full bg-[#101714] border border-[#33473b] rounded-xl px-3 py-1.5 text-xs text-[#e6eee8] focus:outline-none focus:border-[#81c6ca]"
                  />
                </div>
              </div>

              {editStatus === 'finished' && (
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-[11px] font-semibold text-[#a4b8aa]">
                      Оценка книги (по 10-балльной шкале, например 5.5, 9.0)
                    </label>
                    <span className="text-xs font-bold text-[#d7ad76] flex items-center space-x-1">
                      <Star className="w-3.5 h-3.5 fill-[#d7ad76]" />
                      <span>{editRating} / 10</span>
                    </span>
                  </div>

                  <div className="flex items-center space-x-3 bg-[#101714] p-2.5 rounded-2xl border border-[#33473b]">
                    <input
                      type="range"
                      min="1"
                      max="10"
                      step="0.5"
                      value={editRating}
                      onChange={(e) => setEditRating(parseFloat(e.target.value))}
                      className="w-full accent-[#b57935] cursor-pointer"
                    />
                    <div className="flex items-center space-x-1 shrink-0">
                      <input
                        type="number"
                        min="1"
                        max="10"
                        step="0.1"
                        value={editRating}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value);
                          if (!isNaN(val)) setEditRating(Math.max(1, Math.min(10, val)));
                        }}
                        className="w-14 bg-[#19221f] border border-[#33473b] rounded-xl px-2 py-1 text-xs text-center font-bold text-[#d7ad76] focus:outline-none focus:border-[#d7ad76]"
                      />
                      <span className="text-xs text-[#91a797]">/10</span>
                    </div>
                  </div>

                  {/* Quick Preset Pills */}
                  <div className="flex flex-wrap items-center gap-1.5 mt-2">
                    {[5, 5.5, 6, 7, 7.5, 8, 8.5, 9, 9.5, 10].map((val) => (
                      <button
                        key={val}
                        type="button"
                        onClick={() => setEditRating(val)}
                        className={`px-2 py-0.5 rounded-lg text-[10px] font-semibold border transition-all ${
                          editRating === val
                            ? 'bg-[#b57935]/20 border-[#d7ad76] text-[#d7ad76]'
                            : 'bg-[#101714] border-[#33473b] text-[#a4b8aa] hover:text-[#e6eee8]'
                        }`}
                      >
                        {val}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <label className="block text-[11px] font-semibold text-[#a4b8aa] mb-1">
                  Главный инсайт / Заметки
                </label>
                <textarea
                  rows={2}
                  value={editNotes}
                  onChange={(e) => setEditNotes(e.target.value)}
                  className="w-full bg-[#101714] border border-[#33473b] rounded-2xl p-3 text-xs text-[#e6eee8] placeholder-[#475569] focus:outline-none focus:border-[#81c6ca] resize-none"
                />
              </div>

              <div className="pt-2 flex items-center space-x-3">
                <button
                  type="button"
                  onClick={() => setEditingBook(null)}
                  className="w-1/2 py-2.5 rounded-2xl bg-[#101714] text-[#a4b8aa] font-semibold text-xs border border-[#33473b]"
                >
                  Отмена
                </button>
                <button
                  disabled={catalogBusy}
                  type="submit"
                  className="w-1/2 py-2.5 rounded-2xl bg-[#288f97] hover:bg-[#0284c7] text-[#10261b] font-bold text-xs shadow-lg shadow-[#288f97]/20"
                >
                  Сохранить
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};
