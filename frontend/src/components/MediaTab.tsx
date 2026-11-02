import { useEffect, useRef, useState } from 'react';
import { Gamepad2, Film, Tv, Sparkles, Plus, Pencil, Trash2, X } from 'lucide-react';
import { healthHeaders, responseError } from '../healthConnection';

const kinds = {
  game: { label: 'Игры', icon: Gamepad2 },
  movie: { label: 'Фильмы', icon: Film },
  series: { label: 'Сериалы', icon: Tv },
  anime: { label: 'Аниме', icon: Sparkles },
};
const statuses = { planned: 'В планах', active: 'В процессе', finished: 'Завершено' };
type Kind = keyof typeof kinds;
type Status = keyof typeof statuses;
type MediaDraft = { title: string; kind: Kind; status: Status; progress: number; total: number | null; rating: number | null; notes: string };
type MediaItem = MediaDraft & { id: string; updated_at: string; steam_appid?: number; steam_playtime_minutes?: number };
const emptyDraft = (kind: Kind): MediaDraft => ({ title: '', kind, status: 'planned', progress: 0, total: null, rating: null, notes: '' });
const inputClass = 'w-full rounded-xl bg-[#0b0f19] border border-[#334155] p-3 text-white';
const cacheKey = 'fitpulse_media_backup_v1';

function cachedItems(): MediaItem[] {
  try {
    const items = JSON.parse(localStorage.getItem(cacheKey) || '[]');
    return Array.isArray(items) ? items.filter(item => item && item.kind in kinds && item.status in statuses && typeof item.title === 'string' && typeof item.id === 'string') : [];
  } catch { return []; }
}

export function MediaTab() {
  const [items, setItems] = useState<MediaItem[]>(cachedItems);
  const [kind, setKind] = useState<Kind>('game');
  const [filter, setFilter] = useState<Status | 'all'>('all');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [syncMessage, setSyncMessage] = useState('');
  const [draft, setDraft] = useState<MediaDraft | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<MediaItem | null>(null);
  const controller = useRef<AbortController | null>(null);
  const closeButton = useRef<HTMLButtonElement | null>(null);

  function accept(data: { items: MediaItem[] }) {
    setItems(data.items);
    try { localStorage.setItem(cacheKey, JSON.stringify(data.items)); } catch { /* Server remains authoritative. */ }
  }

  async function load() {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/api/media', { headers: healthHeaders(), signal: request.signal });
      if (!response.ok) throw await responseError(response);
      const data = await response.json();
      if (!request.signal.aborted) { accept(data); setReady(true); }
    } catch (err) {
      if (!request.signal.aborted) { setError((err as Error).message); setReady(false); }
    } finally { if (!request.signal.aborted) setLoading(false); }
  }

  useEffect(() => {
    void load();
    const reload = () => { void load(); };
    const events = ['fitpulse:server-ready', 'fitpulse:health-changed', 'fitpulse:media-refresh'];
    events.forEach(event => window.addEventListener(event, reload));
    return () => { controller.current?.abort(); events.forEach(event => window.removeEventListener(event, reload)); };
  }, []);

  const hasModal = !!draft || !!deleting;
  useEffect(() => {
    if (!hasModal) return;
    closeButton.current?.focus();
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) { setDraft(null); setDeleting(null); }
    };
    window.addEventListener('keydown', escape);
    return () => window.removeEventListener('keydown', escape);
  }, [hasModal, busy]);

  async function mutate(path: string, method: string, value?: MediaDraft) {
    setBusy(true);
    setError('');
    setSyncMessage('');
    // A stale list response must never overwrite a completed mutation.
    controller.current?.abort();
    setLoading(false);
    try {
      const response = await fetch(path, { method, headers: { ...healthHeaders(), 'Content-Type': 'application/json' }, body: value ? JSON.stringify(value) : undefined });
      if (!response.ok) throw await responseError(response);
      const data = await response.json();
      accept(data);
      if (data.steam_sync) {
        const { added, updated, matched } = data.steam_sync;
        setSyncMessage(matched ? `Steam: добавлено ${added}, обновлено ${updated}.` : 'В Steam нет доступных игр с временем больше 5 часов. Проверь также, что время в играх не скрыто.');
      }
      setDraft(null);
      setDeleting(null);
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  }

  const categoryItems = items.filter(item => item.kind === kind);
  const priority = { active: 0, planned: 1, finished: 2 };
  const visible = categoryItems.filter(item => (filter === 'all' || item.status === filter) && item.title.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
    .sort((a, b) => priority[a.status] - priority[b.status] || b.updated_at.localeCompare(a.updated_at));
  const episodic = draft?.kind === 'series' || draft?.kind === 'anime';

  return <section className="max-w-3xl mx-auto px-4 pt-5 pb-32 space-y-5 text-white" aria-label="Досуг">
    <div className="flex items-start justify-between gap-3">
      <div><h2 className="text-xl font-bold">Досуг</h2><p className="text-sm text-[#94a3b8] mt-1">Игры и истории, к которым хочется вернуться</p></div>
      <button disabled={!ready || busy || loading} className="flex gap-1 items-center bg-emerald-400 text-[#0b0f19] p-3 rounded-xl disabled:opacity-40" onClick={() => { setEditingId(null); setDraft(emptyDraft(kind)); }}><Plus size={18} />Добавить</button>
    </div>
    <div className="grid grid-cols-4 gap-2" aria-label="Категория">
      {(Object.keys(kinds) as Kind[]).map(key => {
        const Icon = kinds[key].icon;
        return <button key={key} aria-pressed={kind === key} onClick={() => setKind(key)} className={`flex flex-col items-center gap-2 rounded-2xl py-3 text-xs border ${kind === key ? 'border-emerald-400 text-emerald-400 bg-emerald-400/10' : 'border-[#1e293b] bg-[#111726] text-[#94a3b8]'}`}><Icon size={20} />{kinds[key].label}</button>;
      })}
    </div>
    {kind === 'game' && <div className="rounded-2xl bg-[#111726] border border-[#1e293b] p-4 space-y-2">
      <button disabled={!ready || busy || loading} onClick={() => void mutate('/api/media/steam/sync', 'POST')} className="rounded-xl px-4 py-2 bg-emerald-400/15 text-emerald-400 text-sm disabled:opacity-40">{busy ? 'Подожди…' : 'Синхронизировать Steam'}</button>
      <p className="text-xs text-[#94a3b8]">Импорт игр, в которых больше 5 часов. Оценки, заметки и прогресс сохраняются.</p>
      {syncMessage && <p role="status" className="text-sm text-emerald-400">{syncMessage}</p>}
    </div>}
    <div className="grid grid-cols-3 gap-2">
      {(Object.keys(statuses) as Status[]).map(status => <div key={status} className="rounded-2xl bg-[#111726] p-3 text-center"><p className="text-xl font-bold">{categoryItems.filter(item => item.status === status).length}</p><p className="text-xs text-[#94a3b8]">{statuses[status]}</p></div>)}
    </div>
    <input aria-label="Поиск по названию" placeholder="Найти по названию…" value={search} onChange={event => setSearch(event.target.value)} className={inputClass} />
    <div className="flex flex-wrap gap-2" aria-label="Статус">
      {(['all', 'planned', 'active', 'finished'] as const).map(status => <button key={status} aria-pressed={filter === status} onClick={() => setFilter(status)} className={`rounded-xl px-3 py-2 text-xs ${filter === status ? 'bg-emerald-400 text-[#0b0f19]' : 'bg-[#111726] text-[#94a3b8]'}`}>{status === 'all' ? 'Все' : statuses[status]}</button>)}
    </div>
    {error && !hasModal && <div role="alert" className="text-sm text-rose-300">{error}<button onClick={() => void load()} className="underline ml-2">Повторить</button></div>}
    {loading && <p role="status" className="text-sm text-[#94a3b8]">Загружаем коллекцию…</p>}
    {!loading && !visible.length && <div className="rounded-3xl border border-dashed border-[#334155] p-8 text-center text-[#94a3b8]">{categoryItems.length ? 'Ничего не найдено. Измени поиск или статус.' : 'Пока пусто. Добавь то, во что хочешь сыграть или что посмотреть.'}</div>}
    {visible.map(item => <article key={item.id} className="rounded-3xl bg-[#111726] border border-[#1e293b] p-5 space-y-3">
      <div className="flex justify-between gap-3"><div className="min-w-0"><h3 className="font-semibold break-words">{item.title}</h3><p className="text-xs text-emerald-400 mt-1">{statuses[item.status]}</p></div>
        <div className="flex shrink-0 gap-1"><button aria-label={`Редактировать ${item.title}`} disabled={!ready || busy || loading} onClick={() => { setEditingId(item.id); setDraft({ ...item }); }} className="p-2 text-[#94a3b8] disabled:opacity-40"><Pencil size={17} /></button><button aria-label={`Удалить ${item.title}`} disabled={!ready || busy || loading} onClick={() => setDeleting(item)} className="p-2 text-[#94a3b8] disabled:opacity-40"><Trash2 size={17} /></button></div>
      </div>
      {item.kind !== 'movie' && <div><p className="text-xs text-[#94a3b8] mb-2">{item.kind === 'game' ? `${item.progress}% пройдено` : `${item.progress}${item.total ? ` из ${item.total}` : ''} серий`}</p>{item.total && <progress className="w-full h-2 accent-emerald-400" aria-label={`Прогресс: ${item.title}`} value={item.progress} max={item.total} />}</div>}
      {item.kind === 'game' && item.steam_playtime_minutes !== undefined && <p className="text-sm text-[#94a3b8]">Steam · {Math.floor(item.steam_playtime_minutes / 60)} ч {item.steam_playtime_minutes % 60} мин{item.steam_appid && <a href={`https://store.steampowered.com/app/${item.steam_appid}/`} target="_blank" rel="noopener noreferrer" className="ml-2 underline">Страница игры</a>}</p>}
      {item.rating !== null && <p className="text-sm text-amber-300">★ {item.rating} / 10</p>}
      {item.notes && <p className="text-sm text-[#94a3b8] whitespace-pre-wrap break-words">{item.notes}</p>}
    </article>)}
    {hasModal && <div className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4" onKeyDown={event => {
      if (event.key !== 'Tab') return;
      const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), input, select, textarea'));
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }}>
      <div role="dialog" aria-modal="true" aria-labelledby="media-dialog-title" className="w-full max-w-md max-h-[85dvh] overflow-y-auto rounded-3xl bg-[#111726] p-5 space-y-4">
        <div className="flex justify-between items-center"><h3 id="media-dialog-title" className="font-bold">{deleting ? 'Удалить запись?' : editingId ? 'Редактировать' : 'Добавить в коллекцию'}</h3><button ref={closeButton} aria-label="Закрыть" disabled={busy} onClick={() => { setDraft(null); setDeleting(null); }} className="p-2"><X size={20} /></button></div>
        {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
        {deleting ? <><p className="break-words">«{deleting.title}» будет удалено из коллекции.</p><button disabled={busy} className="bg-rose-500 rounded-xl p-3 w-full disabled:opacity-40" onClick={() => void mutate(`/api/media/${deleting.id}`, 'DELETE')}>{busy ? 'Удаляем…' : 'Удалить'}</button></> : draft && <form className="space-y-4" onSubmit={event => { event.preventDefault(); void mutate(editingId ? `/api/media/${editingId}` : '/api/media', editingId ? 'PUT' : 'POST', { ...draft, title: draft.title.trim() }); }}>
          <fieldset disabled={busy} className="space-y-4">
            <label className="block text-sm">Название<input required maxLength={200} value={draft.title} onChange={event => setDraft({ ...draft, title: event.target.value })} className={inputClass} /></label>
            <label className="block text-sm">Категория<select value={draft.kind} onChange={event => setDraft({ ...draft, kind: event.target.value as Kind, progress: 0, total: null })} className={inputClass}>{(Object.keys(kinds) as Kind[]).map(key => <option key={key} value={key}>{kinds[key].label}</option>)}</select></label>
            <label className="block text-sm">Статус<select value={draft.status} onChange={event => setDraft({ ...draft, status: event.target.value as Status })} className={inputClass}>{(Object.keys(statuses) as Status[]).map(key => <option key={key} value={key}>{statuses[key]}</option>)}</select></label>
            {draft.kind !== 'movie' && <label className="block text-sm">{episodic ? 'Просмотрено серий' : 'Пройдено, %'}<input type="number" min={0} max={episodic ? draft.total ?? undefined : 100} step={1} required value={draft.progress} onChange={event => setDraft({ ...draft, progress: Number(event.target.value) })} className={inputClass} /></label>}
            {episodic && <label className="block text-sm">Всего серий (если известно)<input type="number" min={1} step={1} value={draft.total ?? ''} onChange={event => setDraft({ ...draft, total: event.target.value ? Number(event.target.value) : null })} className={inputClass} /></label>}
            <label className="block text-sm">Оценка от 0 до 10<input type="number" min={0} max={10} step={0.5} value={draft.rating ?? ''} onChange={event => setDraft({ ...draft, rating: event.target.value ? Number(event.target.value) : null })} className={inputClass} /></label>
            <label className="block text-sm">Заметки<textarea rows={3} maxLength={10000} value={draft.notes} onChange={event => setDraft({ ...draft, notes: event.target.value })} className={inputClass} /></label>
            <button disabled={busy || !draft.title.trim()} className="w-full rounded-xl bg-emerald-400 text-[#0b0f19] p-3 font-semibold disabled:opacity-40">{busy ? 'Сохраняем…' : 'Сохранить'}</button>
          </fieldset>
        </form>}
      </div>
    </div>}
  </section>;
}
