import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Check, Clock3, Gamepad2, LockKeyhole, RefreshCw, Trophy, X } from 'lucide-react';
import { healthHeaders, responseError } from '../healthConnection';

export type Achievement = { id: string; name: string; description: string; icon: string | null; unlocked: boolean; unlocked_at: number };
export type GameDetails = {
  store: { header_image: string | null; description: string; genres: string[]; developers: string[]; release_date: string | null; screenshots: string[] } | null;
  achievements: { state: 'ready' | 'no_key' | 'none' | 'unavailable'; total?: number; unlocked?: number; entries?: Achievement[] };
};

function gameCover(appid?: number, image?: string | null) {
  return image || (appid ? `https://cdn.akamai.steamstatic.com/steam/apps/${appid}/header.jpg` : null);
}

export function GameArt({ appid, image, className = '', fullHeight = false }: { appid?: number; image?: string | null; className?: string; fullHeight?: boolean }) {
  const [failedUrls, setFailedUrls] = useState<string[]>([]);
  const candidates = [fullHeight && appid && !image ? `https://cdn.akamai.steamstatic.com/steam/apps/${appid}/library_600x900.jpg` : null, gameCover(appid, image)].filter((value): value is string => !!value);
  const url = candidates.find(candidate => !failedUrls.includes(candidate));
  return <div className={`game-art ${className} ${fullHeight ? 'is-full-height' : ''}`} aria-hidden="true">
    {url ? <>{fullHeight && <img className="game-art-backdrop" src={url} alt="" loading="lazy" />}<img className="game-art-image" src={url} alt="" loading="lazy" onError={() => setFailedUrls(current => [...current, url])} /></> : <div className="game-art-fallback"><Gamepad2 size={36} /><span>Твоя следующая история</span></div>}
  </div>;
}

type Props = {
  item: { id: string; title: string; steam_appid?: number; steam_playtime_minutes?: number; steam_header_image?: string | null; cover_image?: string | null; rating?: number | null; progress?: number; notes?: string };
  onClose: () => void;
  onLoaded: (id: string, details: GameDetails) => void;
};

export function GameDetailsDialog({ item, onClose, onLoaded }: Props) {
  const [details, setDetails] = useState<GameDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [filter, setFilter] = useState<'all' | 'unlocked' | 'locked'>('all');
  const dialog = useRef<HTMLDivElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const loadedCallback = useRef(onLoaded);
  useEffect(() => { loadedCallback.current = onLoaded; }, [onLoaded]);

  useEffect(() => {
    const request = new AbortController();
    fetch(`/api/media/${encodeURIComponent(item.id)}/details`, { headers: healthHeaders(), signal: request.signal })
      .then(async response => {
        if (!response.ok) throw await responseError(response);
        return response.json() as Promise<GameDetails>;
      }).then(data => {
        if (!request.signal.aborted) { setDetails(data); loadedCallback.current(item.id, data); }
      }).catch(err => { if (!request.signal.aborted) setError((err as Error).message); })
      .finally(() => { if (!request.signal.aborted) setLoading(false); });
    return () => request.abort();
  }, [item.id, retry]);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    close.current?.focus();
    return () => { document.body.style.overflow = overflow; previous?.focus(); };
  }, []);

  const achievement = details?.achievements;
  const percent = achievement?.total ? Math.round((achievement.unlocked || 0) / achievement.total * 100) : 0;
  const entries = (achievement?.entries || []).filter(entry => filter === 'all' || entry.unlocked === (filter === 'unlocked'));
  const messages = {
    no_key: 'Достижения появятся после подключения Steam API-ключа на сервере.',
    unavailable: 'Steam пока не открыл достижения. Они могут быть скрыты или недоступны для этой игры.',
    none: 'У этой игры нет доступных достижений Steam.',
  };

  return <div className="game-dialog-backdrop" onClick={event => { if (event.target === event.currentTarget) onClose(); }} onKeyDown={event => {
    if (event.key === 'Escape') onClose();
    if (event.key !== 'Tab') return;
    const controls = Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href]') || []);
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  }}>
    <div ref={dialog} role="dialog" aria-modal="true" aria-labelledby="game-detail-title" className="game-dialog">
      <div className="game-dialog-cover">
        <GameArt appid={item.steam_appid} image={item.cover_image || details?.store?.header_image || item.steam_header_image} />
        <div className="game-dialog-cover-shade" />
        <button ref={close} onClick={onClose} aria-label="Закрыть подробности игры" className="game-close"><X size={20} /></button>
        <div className="game-dialog-heading"><span className="game-eyebrow">В твоей коллекции</span><h2 id="game-detail-title">{item.title}</h2>
          <div className="game-meta">{item.steam_playtime_minutes !== undefined && <span><Clock3 size={14} />{Math.floor(item.steam_playtime_minutes / 60)} ч {item.steam_playtime_minutes % 60} мин</span>}<a href={`https://store.steampowered.com/app/${item.steam_appid}/`} target="_blank" rel="noopener noreferrer">В Steam<ArrowUpRight size={14} /></a></div>
        </div>
      </div>
      <div className="game-dialog-body">
        {loading && <p role="status" className="game-loading"><RefreshCw size={16} className="animate-spin" />Загружаем историю игры и достижения…</p>}
        {error && <p role="alert" className="text-rose-300">{error} <button className="underline" onClick={() => { setLoading(true); setError(''); setRetry(value => value + 1); }}>Повторить</button></p>}
        {details && <>
          {details.store ? <div className="game-about">
            <div className="game-genre-list">{details.store.genres.map(genre => <span key={genre}>{genre}</span>)}</div>
            <p>{details.store.description}</p>
            <div className="game-about-facts">{details.store.developers.length > 0 && <span>{details.store.developers.join(', ')}</span>}{details.store.release_date && <span>{details.store.release_date}</span>}</div>
          </div> : <p className="game-muted text-sm">Описание магазина временно недоступно.</p>}
          <div className="game-personal">{item.rating !== null && item.rating !== undefined && <span>★ Твоя оценка: {item.rating} / 10</span>}{!!item.progress && <span>Ручной прогресс: {item.progress}%</span>}{item.notes && <p>{item.notes}</p>}</div>
          <section aria-label="Достижения игры" className="game-achievement-section">
            <div className="game-section-heading"><div><span className="game-eyebrow">Ещё один повод вернуться</span><h3><Trophy size={20} />Достижения</h3></div>{achievement?.state === 'ready' && <strong>{achievement.unlocked}<span> / {achievement.total}</span></strong>}</div>
            {achievement?.state === 'ready' ? <>
              <div className="game-achievement-progress"><div style={{ width: `${percent}%` }} /></div>
              <div className="game-achievement-toolbar"><span>{percent}% получено</span><div>{(['all', 'unlocked', 'locked'] as const).map(value => <button key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>{value === 'all' ? 'Все' : value === 'unlocked' ? 'Получены' : 'Впереди'}</button>)}</div></div>
              <div className="game-achievement-list">{entries.map(entry => <div key={entry.id} className={`game-achievement ${entry.unlocked ? 'is-unlocked' : ''}`}>
                <div className="game-achievement-icon">{entry.icon ? <img src={entry.icon} alt="" loading="lazy" onError={event => { event.currentTarget.style.display = 'none'; }} /> : <Trophy size={22} />}</div>
                <div><h4>{entry.name}</h4>{entry.description && <p>{entry.description}</p>}{entry.unlocked_at > 0 && <time dateTime={new Date(entry.unlocked_at * 1000).toISOString()}>{new Date(entry.unlocked_at * 1000).toLocaleDateString('ru-RU', { timeZone: 'Asia/Omsk', day: 'numeric', month: 'short', year: 'numeric' })}</time>}</div>
                {entry.unlocked ? <Check size={17} className="game-unlocked-check" aria-label="Получено" /> : <LockKeyhole size={14} className="game-muted shrink-0" aria-label="Не получено" />}
              </div>)}{!entries.length && <p className="game-muted text-sm py-4">В этой категории пока нет достижений.</p>}</div>
            </> : achievement && <p className="game-achievement-unavailable"><LockKeyhole size={18} />{messages[achievement.state as keyof typeof messages]}</p>}
          </section>
          {!!details.store?.screenshots.length && <section><div className="game-section-heading"><h3>Внутри игры</h3><span className="game-muted text-xs">Скриншоты Steam</span></div><div className="game-screenshots">{details.store.screenshots.map((shot, index) => <a key={shot} href={shot} target="_blank" rel="noopener noreferrer"><img src={shot} alt={`Скриншот ${index + 1}: ${item.title}`} loading="lazy" /></a>)}</div></section>}
        </>}
      </div>
    </div>
  </div>;
}
