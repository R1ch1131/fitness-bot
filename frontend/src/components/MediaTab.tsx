import { CatalogPicker, CatalogFacts, Poster, WatchTitle } from './CatalogPicker';
import type { CatalogInfo } from './CatalogPicker';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Gamepad2, Film, Tv, Sparkles, Plus, Pencil, Trash2, X, Clock3, Trophy, ArrowUpRight, Search, RefreshCw, ShieldCheck, Download, Upload, LayoutGrid, List } from 'lucide-react';
import { healthHeaders, responseError } from '../healthConnection';
import { GameArt, GameDetailsDialog } from './GameDetailsDialog';
import type { GameDetails } from './GameDetailsDialog';
import './games.css';
import { prepareCover } from '../coverImage';
import { DarkSelect } from './DarkSelect';

const kinds = {
  game: { label: 'Игры', icon: Gamepad2 },
  movie: { label: 'Фильмы', icon: Film },
  series: { label: 'Сериалы', icon: Tv },
  anime: { label: 'Аниме', icon: Sparkles },
};
const statuses = { planned: 'В планах', active: 'В процессе', finished: 'Завершено' };
type Kind = keyof typeof kinds;
type Status = keyof typeof statuses;
type MediaDraft = { manual_playtime_minutes?: number | null; title: string; kind: Kind; status: Status; progress: number; total: number | null; rating: number | null; notes: string; cover_image?: string | null; catalog?: CatalogInfo | null };
type MediaItem = MediaDraft & { id: string; updated_at: string; steam_appid?: number; steam_playtime_minutes?: number; steam_last_played?: number; steam_recent_minutes?: number; steam_header_image?: string | null; steam_genres?: string[]; steam_achievements?: { unlocked: number; total: number } };
const playtime = (item: MediaItem) => item.steam_appid ? item.steam_playtime_minutes : item.manual_playtime_minutes ?? item.steam_playtime_minutes;
const emptyDraft = (kind: Kind): MediaDraft => ({ title: '', kind, status: 'planned', progress: 0, total: null, rating: null, notes: '' });
const inputClass = 'w-full rounded-xl bg-[#101714] border border-[#33473b] p-3 text-[#e6eee8]';
const cacheKey = 'fitpulse_media_backup_v1';

function cachedItems(): MediaItem[] {
  try {
    const items = JSON.parse(localStorage.getItem(cacheKey) || '[]');
    return Array.isArray(items) ? items.filter(item => item && item.kind in kinds && item.status in statuses && typeof item.title === 'string' && typeof item.id === 'string') : [];
  } catch { return []; }
}

function RatingInput({ value, onChange }: { value: number | null; onChange: (value: number | null) => void }) {
  const [text, setText] = useState(value == null ? '' : String(value));
  useEffect(() => {
    setText(current => (current === '' && value == null) || (current !== '' && Number(current.replace(',', '.')) === value) ? current : value == null ? '' : String(value));
  }, [value]);
  return <input type="text" inputMode="decimal" pattern="(?:10(?:[.,]0)?|[0-9](?:[.,][0-9])?)" title="Оценка от 0 до 10, например 5.5 или 5,5" placeholder="Например, 5.5" value={text} onChange={event=>{
    const next=event.target.value;
    if (!/^\d{0,2}([.,]\d?)?$/.test(next)) return;
    setText(next);
    if (next === '') onChange(null);
    else { const number=Number(next.replace(',', '.')); if (Number.isFinite(number) && number>=0 && number<=10) onChange(number); }
  }} className={inputClass} />;
}

type StorageStatus = { backend: 'upstash' | 'local' | 'demo'; state: string; count?: number; message?: string };

export function MediaTab() {
  const [items, setItems] = useState<MediaItem[]>(cachedItems);
  const [kind, setKind] = useState<Kind>('game');
  const [filters, setFilters] = useState<Record<Kind, Status | 'all'>>({ game: 'finished', movie: 'all', series: 'all', anime: 'all' });
  const filter = filters[kind];
  const setFilter = (status: Status | 'all') => setFilters(current => ({ ...current, [kind]: status }));
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [storage, setStorage] = useState<StorageStatus | null>(null);
  const [storageBusy, setStorageBusy] = useState(false);
  const storageRequest = useRef<AbortController | null>(null);
  const [syncMessage, setSyncMessage] = useState('');
  const [selectedGame, setSelectedGame] = useState<MediaItem | null>(null);
  const [sort, setSort] = useState('rating');
  const [layout, setLayout] = useState<'grid' | 'list'>('list');
  const [enrichmentVersion, setEnrichmentVersion] = useState(0);
  const attemptedDetails = useRef(new Set<string>());
  const [hoursInput, setHoursInput] = useState('');
  const [draft, setDraft] = useState<MediaDraft | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<MediaItem | null>(null);
  const [coverBusy, setCoverBusy] = useState(false);
  const [coverError, setCoverError] = useState('');
  const [coverResults, setCoverResults] = useState<{ title: string; image: string }[]>([]);
  const coverSearch = useRef<AbortController | null>(null);
  const formSession = useRef(0);
  const formOpen = !!draft;
  useEffect(() => {
    formSession.current += 1;
    if (!formOpen) { coverSearch.current?.abort(); setCoverError(''); setCoverResults([]); setCoverBusy(false); }
    return () => coverSearch.current?.abort();
  }, [formOpen]);

  async function searchCover() {
    if (!draft || draft.title.trim().length < 2) { setCoverError('Сначала введи название — хотя бы 2 символа.'); return; }
    coverSearch.current?.abort();
    const request = new AbortController();
    coverSearch.current = request;
    setCoverBusy(true); setCoverError(''); setCoverResults([]);
    try {
      const response = await fetch(`/api/media/covers?title=${encodeURIComponent(draft.title.trim())}`, { headers: healthHeaders(), signal: request.signal });
      if (!response.ok) throw await responseError(response);
      const data = await response.json();
      if (!request.signal.aborted) {
        setCoverResults(data.results);
        if (!data.results.length) setCoverError('Не нашли обложку. Можно загрузить свою картинку.');
      }
    } catch (error) { if (!request.signal.aborted) setCoverError((error as Error).message); }
    finally { if (coverSearch.current === request) setCoverBusy(false); }
  }

  async function uploadCover(file?: File) {
    if (!file) return;
    const session = formSession.current;
    setCoverBusy(true); setCoverError(''); coverSearch.current?.abort();
    try {
      const image = await prepareCover(file);
      if (session !== formSession.current) return;
      setDraft(current => current ? { ...current, cover_image: image } : current);
      setCoverResults([]);
    } catch (error) { if (session === formSession.current) setCoverError((error as Error).message); }
    finally { if (session === formSession.current) setCoverBusy(false); }
  }
  const controller = useRef<AbortController | null>(null);
  const closeButton = useRef<HTMLButtonElement | null>(null);

  function accept(data: { items: MediaItem[]; storage?: StorageStatus }) {
    setItems(data.items);
    if (data.storage) setStorage(data.storage);
    try { localStorage.setItem(cacheKey, JSON.stringify(data.items)); } catch { /* Server remains authoritative. */ }
  }

  async function checkStorage() {
    storageRequest.current?.abort(); const request = new AbortController(); storageRequest.current = request;
    setStorageBusy(true);
    try {
      const response = await fetch('/api/media/storage', {headers:healthHeaders(), signal:request.signal});
      if (!response.ok) throw await responseError(response);
      const data: StorageStatus = await response.json();
      if (!request.signal.aborted) setStorage(data);
    } catch(err) { if (!request.signal.aborted) setStorage(current=>({...current,backend:current?.backend || 'local',state:'error',message:(err as Error).message})); }
    finally { if (!request.signal.aborted) setStorageBusy(false); }
  }

  function exportMedia() {
    const blob = new Blob([JSON.stringify({version:1,timestamp:new Date().toISOString(),items},null,2)], {type:'application/json'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href=url; link.download=`fitpulse-media-${new Date().toISOString().slice(0,10)}.json`;
    link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
  }

  async function importMedia(file?: File) {
    if (!file) return;
    setError('');
    try {
      if (file.size>25_000_000) throw new Error('Файл резервной копии слишком большой — максимум 25 МБ.');
      const payload = JSON.parse(await file.text());
      const restored = Array.isArray(payload) ? payload : payload.items ?? payload.media;
      if (!Array.isArray(restored) || restored.some(item=>!item || typeof item.id!=='string' || typeof item.title!=='string' || !(item.kind in kinds))) throw new Error('В файле нет корректной коллекции «Досуг».');
      if (!window.confirm(`Заменить всю коллекцию «Досуг» (${items.length} записей) данными из файла (${restored.length} записей)? Перед заменой скачай текущую копию.`)) return;
      controller.current?.abort(); setLoading(false); setBusy(true);
      const response = await fetch('/api/media/restore', {method:'POST',headers:{...healthHeaders(),'Content-Type':'application/json'},body:JSON.stringify({items:restored})});
      if (!response.ok) throw await responseError(response);
      accept(await response.json()); setReady(true); setSyncMessage(`Коллекция восстановлена: ${restored.length} записей.`);
    } catch(err) { setError((err as Error).message); }
    finally { setBusy(false); }
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
    return () => { controller.current?.abort(); storageRequest.current?.abort(); events.forEach(event => window.removeEventListener(event, reload)); };
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
        attemptedDetails.current.clear();
        setEnrichmentVersion(value => value + 1);
        const { added, updated, matched } = data.steam_sync;
        setSyncMessage(matched ? `Steam: добавлено ${added}, обновлено ${updated}.` : 'В Steam нет доступных игр с временем больше 5 часов. Проверь также, что время в играх не скрыто.');
      }
      setDraft(null);
      setDeleting(null);
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  }

  const categoryItems = items.filter(item => item.kind === kind);
  const visible = categoryItems.filter(item => (filter === 'all' || item.status === filter) && item.title.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
    .sort((a, b) => {
      if (kind === 'anime' || kind === 'series') {
        const activeFirst = Number(b.status === 'active') - Number(a.status === 'active');
        if (activeFirst) return activeFirst;
      }
      return kind !== 'game' || sort === 'rating' ? (b.rating ?? -1) - (a.rating ?? -1) || a.title.localeCompare(b.title, 'ru') : sort === 'hours' ? (playtime(b) || 0) - (playtime(a) || 0) : sort === 'title' ? a.title.localeCompare(b.title, 'ru') : sort === 'achievements' ? (b.steam_achievements?.unlocked || 0) - (a.steam_achievements?.unlocked || 0) : (b.steam_last_played || 0) - (a.steam_last_played || 0) || b.updated_at.localeCompare(a.updated_at);
    });
  const episodic = draft?.kind === 'series' || draft?.kind === 'anime';

  const featured = categoryItems.filter(item => item.status === 'active').sort((a, b) => (b.steam_last_played || 0) - (a.steam_last_played || 0) || b.updated_at.localeCompare(a.updated_at))[0];
  const totalMinutes = categoryItems.reduce((sum, item) => sum + (playtime(item) || 0), 0);
  const steamGames = categoryItems.filter(item => item.steam_appid);
  const knownAchievements = steamGames.filter(item => item.steam_achievements);
  const unlocked = knownAchievements.reduce((sum, item) => sum + (item.steam_achievements?.unlocked || 0), 0);
  const edit = (item: MediaItem) => { setEditingId(item.id); setHoursInput(item.manual_playtime_minutes == null ? '' : String(item.manual_playtime_minutes / 60)); setDraft({ ...item }); };
  const openGame = (item: MediaItem) => item.steam_appid ? setSelectedGame(item) : edit(item);
  const detailsLoaded = useCallback((id: string, details: GameDetails) => {
    setItems(current => current.map(item => item.id === id ? {
      ...item,
      ...(details.store ? { steam_header_image: details.store.header_image, steam_genres: details.store.genres } : {}),
      ...(details.achievements.state === 'ready' ? { steam_achievements: { unlocked: details.achievements.unlocked || 0, total: details.achievements.total || 0 } } : {}),
    } : item));
  }, []);
  const visibleSteamKey = kind === 'game' ? visible.filter(item => item.steam_appid).slice(0, 12).map(item => item.id).join(',') : '';
  useEffect(() => {
    if (!visibleSteamKey) return;
    const request = new AbortController();
    const pending = visibleSteamKey.split(',').filter(id => !attemptedDetails.current.has(id));
    // Artwork and achievement summaries fill in without blocking the collection.
    const worker = async () => {
      while (pending.length && !request.signal.aborted) {
        const id = pending.shift()!;
        attemptedDetails.current.add(id);
        try {
          const response = await fetch(`/api/media/${encodeURIComponent(id)}/details`, { headers: healthHeaders(), signal: request.signal });
          if (!response.ok) continue;
          const data: GameDetails = await response.json();
          if (!request.signal.aborted) detailsLoaded(id, data);
        } catch { /* Optional game data must never interrupt the library. */ }
        finally { if (request.signal.aborted) attemptedDetails.current.delete(id); }
      }
    };
    void worker();
    void worker();
    return () => request.abort();
  }, [visibleSteamKey, enrichmentVersion, detailsLoaded]);

  const layoutToggle = <button type="button" className="media-view-toggle" aria-label={layout === 'list' ? 'Показать карточками' : 'Показать списком'} title={layout === 'list' ? 'Показать карточками' : 'Показать списком'} onClick={() => setLayout(current => current === 'list' ? 'grid' : 'list')}>{layout === 'list' ? <LayoutGrid size={18} /> : <List size={18} />}</button>;

  return <section className={`mx-auto px-4 pt-5 pb-32 space-y-5 text-[#e6eee8] ${kind === 'game' ? 'game-library' : 'max-w-3xl'}`} aria-label="Досуг" data-layout={layout}>
    <div className="flex items-start justify-between gap-3">
      <div><h2 className="text-xl font-bold">Досуг</h2><p className="text-sm text-[#a4b8aa] mt-1">Игры и истории, к которым хочется вернуться</p></div>
      <button disabled={!ready || busy || loading} className="media-add-button flex gap-1 items-center disabled:opacity-40" onClick={() => { setEditingId(null); setHoursInput(''); setDraft(emptyDraft(kind)); }}><Plus size={18} />Добавить</button>
    </div>
    <div className="grid grid-cols-4 gap-2" aria-label="Категория">
      {(Object.keys(kinds) as Kind[]).map(key => {
        const Icon = kinds[key].icon;
        return <button key={key} aria-pressed={kind === key} onClick={() => setKind(key)} className={`flex flex-col items-center gap-2 rounded-2xl py-3 text-xs border ${kind === key ? 'border-emerald-400 text-emerald-400 bg-emerald-400/10' : 'border-[#33473b] bg-[#19221f] text-[#a4b8aa]'}`}><Icon size={20} />{kinds[key].label}</button>;
      })}
    </div>
    {kind === 'game' ? <>
      <div className="game-library-heading"><div><span className="game-eyebrow">Личная коллекция · Steam</span><h2>Моя игротека</h2></div><div className="media-heading-actions">{layoutToggle}<button aria-label="Синхронизировать Steam" disabled={!ready || busy || loading} onClick={() => void mutate('/api/media/steam/sync', 'POST')} className="game-sync"><RefreshCw size={13} className={busy ? 'animate-spin' : ''} /><span>{busy ? 'Синхронизируем…' : 'Синхронизировать Steam'}</span></button></div></div>
      {syncMessage && <p role="status" className="text-sm text-emerald-300">{syncMessage}</p>}
      <div className="game-overview">
        <div><span className="game-overview-label"><Gamepad2 size={13} />В коллекции</span><strong>{categoryItems.length}<small> игр</small></strong></div>
        <div><span className="game-overview-label"><Clock3 size={13} />Время в мирах</span><strong>{Math.floor(totalMinutes / 60).toLocaleString('ru-RU')}<small> часов</small></strong></div>
        <div><span className="game-overview-label"><Trophy size={13} />Достижения</span><strong>{knownAchievements.length ? unlocked : '—'}<small>{knownAchievements.length ? ' получено' : ' открой игру'}</small></strong></div>
      </div>
      {featured && !search && (filter === 'all' || filter === 'finished') && <div className="game-feature">
        <GameArt appid={featured.steam_appid} image={featured.cover_image || featured.steam_header_image} /><div className="game-feature-shade" />{featured.rating != null && <span className="poster-rating game-cover-rating" aria-label={`Моя оценка: ${featured.rating} из 10`}>★ {featured.rating}</span>}
        <div className="game-feature-content"><span className="game-eyebrow">Играю сейчас</span><h3>{featured.title}</h3>{playtime(featured) != null && <p><Clock3 size={13} />{Math.floor(playtime(featured)! / 60)} ч в игре{featured.steam_last_played ? ` · ${new Date(featured.steam_last_played * 1000).toLocaleDateString('ru-RU', { timeZone: 'Asia/Omsk', day: 'numeric', month: 'long' })}` : ''}</p>}<button onClick={() => openGame(featured)}>{featured.steam_appid ? 'Об игре и достижениях' : 'Об игре'}<ArrowUpRight size={15} /></button></div>
      </div>}
      <div><div className="game-collection-heading"><h3>{filter === 'finished' ? 'Пройденные игры' : filter === 'active' ? 'Играю сейчас' : filter === 'planned' ? 'Хочу поиграть' : 'Все твои миры'}<span>{visible.length}</span></h3><DarkSelect label="Сортировка игр" value={sort} onChange={setSort} compact options={[{value:'rating',label:'По моей оценке',icon:<Trophy />},{value:'recent',label:'Недавно играл',icon:<Clock3 />},{value:'hours',label:'Больше часов',icon:<Clock3 />},{value:'title',label:'По названию',icon:<Gamepad2 />},{value:'achievements',label:'Больше достижений',icon:<Trophy />}]} /></div>
        <div className="game-toolbar"><label className="game-search"><Search size={15} /><input aria-label="Поиск по названию" placeholder="Найти свой мир…" value={search} onChange={event => setSearch(event.target.value)} /></label><div className="game-filters" aria-label="Статус">{(['all', 'active', 'planned', 'finished'] as const).map(status => <button key={status} aria-pressed={filter === status} onClick={() => setFilter(status)}>{status === 'all' ? 'Все игры' : statuses[status]}</button>)}</div></div>
        {error && !hasModal && <p role="alert" className="text-sm text-rose-300 mb-4">{error}<button onClick={() => void load()} className="underline ml-2">Повторить</button></p>}
        {loading && <p role="status" className="game-loading"><RefreshCw size={14} className="animate-spin" />Загружаем коллекцию…</p>}
        {!loading && !visible.length && <div className="rounded-3xl border border-dashed border-[#33473b] p-8 text-center text-[#a4b8aa]">{categoryItems.length ? 'Не нашли такую игру. Попробуй другой поиск или статус.' : 'Твоя история начинается здесь. Добавь игру или синхронизируй Steam.'}</div>}
        <div className="game-grid">{visible.map(item => <article key={item.id} className="game-card">
          <button className="game-card-cover" aria-label={`Открыть ${item.title}`} onClick={() => openGame(item)}><GameArt appid={item.steam_appid} image={layout === 'list' ? item.cover_image : item.cover_image || item.steam_header_image} fullHeight={layout === 'list'} />{item.rating != null && <span className="poster-rating game-cover-rating" aria-label={`Моя оценка: ${item.rating} из 10`}>★ {item.rating}</span>}<span className={`game-status ${item.status === 'active' ? 'is-active' : ''}`}>{statuses[item.status]}</span></button>
          <div className="game-card-body"><button className="game-card-title" onClick={() => openGame(item)}><h3>{item.title}</h3></button><p className="game-card-genre">{item.steam_genres?.slice(0, 2).join(' · ') || (item.steam_appid ? 'Из твоей библиотеки Steam' : 'Добавлено тобой')}</p>
            <p className="game-card-time"><Clock3 size={12} />{playtime(item) != null ? <span>{Math.floor(playtime(item)! / 60)} ч {playtime(item)! % 60} мин</span> : <span>Часы не указаны</span>}{!!item.steam_recent_minutes && <small>+{Math.round(item.steam_recent_minutes / 60 * 10) / 10} ч за 2 недели</small>}</p>
            <div className="game-card-achievements">{item.steam_achievements ? <><div><Trophy size={12} /><span>Достижения</span><strong>{item.steam_achievements.unlocked} / {item.steam_achievements.total}</strong></div><div className="game-mini-progress" role="progressbar" aria-label={`Достижения: ${item.title}`} aria-valuenow={item.steam_achievements.unlocked} aria-valuemin={0} aria-valuemax={item.steam_achievements.total}><div style={{ width: `${item.steam_achievements.total ? item.steam_achievements.unlocked / item.steam_achievements.total * 100 : 0}%` }} /></div></> : <button className="game-card-achievement-link" onClick={() => openGame(item)}>{item.steam_appid ? <><span>Посмотреть достижения</span><ArrowUpRight size={13} /></> : <span>Об игре</span>}</button>}</div>
            <div className="game-card-footer"><div className="game-card-actions"><button aria-label={`Редактировать ${item.title}`} disabled={!ready || busy || loading} onClick={() => edit(item)}><Pencil size={13} /></button><button aria-label={`Удалить ${item.title}`} disabled={!ready || busy || loading} onClick={() => setDeleting(item)}><Trash2 size={13} /></button></div></div>
          </div>
        </article>)}</div>
        <p className="game-library-note"><ShieldCheck size={12} />Из Steam — только игры с временем больше 5 часов</p>
        {!!knownAchievements.length && knownAchievements.length < steamGames.length && <p className="game-library-note">Достижения посчитаны для {knownAchievements.length} из {steamGames.length} игр Steam. Открой остальные карточки, чтобы загрузить данные.</p>}
      </div>
    </> : <>
    <div className="watch-heading"><div><span className="catalog-eyebrow">Твоя личная коллекция</span><h2>{kind === 'movie' ? 'Мой кинотеатр' : kind === 'series' ? 'Ещё одна серия' : 'Миры аниме'}</h2><p>Сохраняй находки, отмечай просмотренное и собирай впечатления.</p></div>{layoutToggle}</div>
    <div className="grid grid-cols-3 gap-2">
      {(Object.keys(statuses) as Status[]).map(status => <div key={status} className="rounded-2xl bg-[#19221f] p-3 text-center"><p className="text-xl font-bold">{categoryItems.filter(item => item.status === status).length}</p><p className="text-xs text-[#a4b8aa]">{statuses[status]}</p></div>)}
    </div>
    <input aria-label="Поиск по названию" placeholder="Найти по названию…" value={search} onChange={event => setSearch(event.target.value)} className={inputClass} />
    <div className="flex flex-wrap gap-2" aria-label="Статус">
      {(['all', 'planned', 'active', 'finished'] as const).map(status => <button key={status} aria-pressed={filter === status} onClick={() => setFilter(status)} className={`rounded-xl px-3 py-2 text-xs ${filter === status ? 'bg-emerald-400 text-[#10261b]' : 'bg-[#19221f] text-[#a4b8aa]'}`}>{status === 'all' ? 'Все' : statuses[status]}</button>)}
    </div>
    {error && !hasModal && <div role="alert" className="text-sm text-rose-300">{error}<button onClick={() => void load()} className="underline ml-2">Повторить</button></div>}
    {loading && <p role="status" className="text-sm text-[#a4b8aa]">Загружаем коллекцию…</p>}
    {!loading && !visible.length && <div className="rounded-3xl border border-dashed border-[#33473b] p-8 text-center text-[#a4b8aa]">{categoryItems.length ? 'Ничего не найдено. Измени поиск или статус.' : 'Пока пусто. Добавь то, во что хочешь сыграть или что посмотреть.'}</div>}
    <div className="watch-grid">{visible.map(item => <article key={item.id} className="watch-card">
      <Poster image={item.cover_image} title={item.title} score={item.rating} />
      <div className="watch-card-body"><p className="text-xs text-emerald-300 mb-2">{statuses[item.status]}</p><WatchTitle title={item.title} />
      {item.catalog ? <CatalogFacts info={item.catalog} title={item.title} compact /> : <div className="catalog-facts is-compact" />}
      {item.kind !== 'movie' && <div className="watch-card-progress"><div><span>{item.progress}{item.total ? ` из ${item.total}` : ''} серий</span>{item.total && <strong>{Math.min(100, Math.round(item.progress / item.total * 100))}%</strong>}</div>{item.total && <progress aria-label={`Прогресс: ${item.title}`} value={item.progress} max={item.total} />}</div>}
      {item.notes && <p className="watch-card-note" title={item.notes}>{item.notes}</p>}
      <div className="watch-card-actions">{item.kind !== 'movie' && item.status !== 'finished' && <button className="watch-next-episode" disabled={busy || !ready || loading} onClick={() => void mutate(`/api/media/${item.id}`, 'PUT', {...item, progress:item.progress + 1})}>+1 серия</button>}<div className="watch-edit-actions"><button aria-label={`Редактировать ${item.title}`} disabled={!ready || busy || loading} onClick={() => edit(item)}><Pencil size={16} /></button><button aria-label={`Удалить ${item.title}`} disabled={!ready || busy || loading} onClick={() => setDeleting(item)}><Trash2 size={16} /></button></div></div></div>
    </article>)}</div>
    {(kind === 'movie' || kind === 'series' || kind === 'anime') && <details className="catalog-credits"><summary>О каталогах и источниках</summary><img alt="TMDB" src="https://www.themoviedb.org/assets/2/v4/logos/v2/blue_short-8e7b30f73a4020692ccca9c88bafe5dcb6f8a62a4c6bc55cd9ba82bb2cd95f6c.svg" /><a href="https://www.themoviedb.org" target="_blank" rel="noreferrer">Данные и изображения: TMDB</a><p>This product uses the TMDB API but is not endorsed or certified by TMDB.</p></details>}
    </>}
    <details className="media-storage-panel media-storage-footer">
      <summary>Хранение и резервные копии</summary>
      {storage && <div className="media-storage-status"><ShieldCheck size={15} /><div><strong>{storage.backend === 'demo' ? 'Демонстрационная коллекция' : storage.backend === 'upstash' ? 'Хранилище: Upstash Redis' : 'Хранилище: файлы сервера'}</strong><p role="status">{storage.message || (storage.state === 'configured' ? 'Используется та же база, что для книг. Проверь соединение кнопкой справа.' : 'Upstash не подключён. На Render данные могут потеряться при обновлении. Скачай копию.')}</p></div><button type="button" disabled={storageBusy || busy} onClick={()=>void checkStorage()}>{storageBusy ? 'Проверяем…' : 'Проверить'}</button></div>}
      <div className="media-backup-actions"><button type="button" disabled={busy || (!items.length && !ready)} onClick={exportMedia}><Download size={13} />Скачать копию</button><label className={busy || !ready || loading ? 'is-disabled' : ''}><Upload size={13} />Восстановить<input aria-label="Восстановить коллекцию из файла" type="file" accept="application/json,.json" disabled={busy || !ready || loading} onChange={event=>{void importMedia(event.target.files?.[0]);event.target.value='';}} /></label></div>
    </details>
    {selectedGame && <GameDetailsDialog key={selectedGame.id} item={selectedGame} onClose={() => setSelectedGame(null)} onLoaded={detailsLoaded} />}
    {hasModal && <div className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4" onKeyDown={event => {
      if (event.key !== 'Tab') return;
      const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), input, select, textarea'));
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }}>
      <div role="dialog" aria-modal="true" aria-labelledby="media-dialog-title" className="w-full max-w-md max-h-[85dvh] overflow-y-auto rounded-3xl bg-[#19221f] p-5 space-y-4">
        <div className="flex justify-between items-center"><h3 id="media-dialog-title" className="font-bold">{deleting ? 'Удалить запись?' : editingId ? 'Редактировать' : 'Добавить в коллекцию'}</h3><button ref={closeButton} aria-label="Закрыть" disabled={busy} onClick={() => { setDraft(null); setDeleting(null); }} className="p-2"><X size={20} /></button></div>
        {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
        {deleting ? <><p className="break-words">«{deleting.title}» будет удалено из коллекции.</p><button disabled={busy} className="bg-rose-500 rounded-xl p-3 w-full disabled:opacity-40" onClick={() => void mutate(`/api/media/${deleting.id}`, 'DELETE')}>{busy ? 'Удаляем…' : 'Удалить'}</button></> : draft && <form className="space-y-4" onSubmit={event => { event.preventDefault(); void mutate(editingId ? `/api/media/${editingId}` : '/api/media', editingId ? 'PUT' : 'POST', { ...draft, title: draft.title.trim() }); }}>
          <fieldset disabled={busy} className="space-y-4">
            <label className="block text-sm">Название<input required maxLength={200} value={draft.title} onChange={event => setDraft({ ...draft, title: event.target.value })} className={inputClass} /></label>
            {draft.kind === 'game' && <div className="manual-cover-field">
              <div className="manual-cover-heading"><span>Обложка игры</span>{draft.cover_image && <button type="button" disabled={coverBusy} onClick={() => setDraft({ ...draft, cover_image: null })}>Убрать свою</button>}</div>
              <GameArt appid={editingId ? items.find(item => item.id === editingId)?.steam_appid : undefined} image={draft.cover_image || (editingId ? items.find(item => item.id === editingId)?.steam_header_image : null)} />
              <div className="manual-cover-actions"><button type="button" disabled={coverBusy} onClick={() => void searchCover()}>{coverBusy ? 'Подожди…' : 'Найти по названию'}</button><label className={coverBusy ? 'opacity-40' : ''}>Загрузить картинку<input aria-label="Загрузить обложку игры" disabled={coverBusy} type="file" accept="image/jpeg,image/png,image/webp" onChange={event => { void uploadCover(event.target.files?.[0]); event.target.value = ''; }} /></label></div>
              <p>Из каталога Steam или свой JPG, PNG, WebP — до 10 МБ.</p>
              {coverError && <p role="alert" className="text-rose-300">{coverError}</p>}
              {!!coverResults.length && <div className="manual-cover-results" aria-label="Найденные обложки">{coverResults.map(result => <button key={result.image} type="button" aria-label={`Выбрать обложку: ${result.title}`} onClick={() => { setDraft({ ...draft, title: result.title, cover_image: result.image }); setCoverResults([]); }}><GameArt image={result.image} /><span>{result.title}</span></button>)}</div>}
            </div>}
            {draft.kind !== 'game' && <CatalogPicker key={editingId || 'new'} kind={draft.kind} title={draft.title} info={draft.catalog} image={draft.cover_image} onBusy={setCoverBusy} onPoster={image => setDraft(current => current ? {...current, cover_image:image, catalog:current.catalog ? {...current.catalog, poster_source:'TMDB'} : current.catalog} : current)} onImage={image => setDraft(current => current ? {...current, cover_image:image, catalog:current.catalog ? {...current.catalog, poster_source:null} : current.catalog} : current)} onSelect={info => setDraft(current => current ? {...current, title:info.title, catalog:info, cover_image:info.image || null, total:info.episodes && info.episodes >= current.progress ? info.episodes : current.total} : current)} />}
            <div className="space-y-2"><span className="block text-sm">Статус</span><DarkSelect label="Статус" value={draft.status} disabled={busy} onChange={value => setDraft({ ...draft, status: value as Status })} options={(Object.keys(statuses) as Status[]).map(key => ({value:key,label:statuses[key],icon:<span className={`select-status-dot ${key}`} />}))} /></div>
            {draft.kind === 'game' && !(editingId && items.find(item => item.id === editingId)?.steam_appid) && <label className="block text-sm">Часов в игре<input aria-label="Часов в игре" type="number" inputMode="decimal" min={0} max={1000000} step="any" placeholder="Например, 12.5" value={hoursInput} onChange={event => { const value = event.target.value; setHoursInput(value); setDraft({...draft, manual_playtime_minutes:value === '' ? null : Math.round(Number(value) * 60)}); }} className={inputClass} /><span className="block text-xs text-[#a4b8aa] mt-1">Можно указать дробное число: 12.5 — это 12 ч 30 мин. Пустое поле — время не указано.</span></label>}
            {episodic && <label className="block text-sm">Просмотрено серий<input type="number" min={0} max={episodic ? draft.total ?? undefined : 100} step={1} required value={draft.progress} onChange={event => setDraft({ ...draft, progress: Number(event.target.value) })} className={inputClass} /></label>}
            {episodic && <label className="block text-sm">Всего серий (если известно)<input type="number" min={1} step={1} value={draft.total ?? ''} onChange={event => setDraft({ ...draft, total: event.target.value ? Number(event.target.value) : null })} className={inputClass} /></label>}
            <label className="block text-sm">Оценка от 0 до 10<RatingInput value={draft.rating} onChange={rating => setDraft(current => current ? {...current, rating} : current)} /><span className="block text-xs text-[#a4b8aa] mt-1">Можно дробную: 5.5 или 5,5</span></label>
            <label className="block text-sm">Заметки<textarea rows={3} maxLength={10000} value={draft.notes} onChange={event => setDraft({ ...draft, notes: event.target.value })} className={inputClass} /></label>
            <button disabled={busy || coverBusy || !draft.title.trim()} className="w-full rounded-xl bg-emerald-400 text-[#10261b] p-3 font-semibold disabled:opacity-40">{busy ? 'Сохраняем…' : 'Сохранить'}</button>
          </fieldset>
        </form>}
      </div>
    </div>}
  </section>;
}
