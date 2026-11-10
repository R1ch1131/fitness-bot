import { createPortal } from 'react-dom';
import { useEffect, useRef, useState } from 'react';
import { BookOpen, ImagePlus, Search } from 'lucide-react';
import { healthHeaders, responseError } from '../healthConnection';
import { prepareCover } from '../coverImage';
import './catalog.css';

export type CatalogInfo = {
  source: 'Open Library' | 'Google Books' | 'Shikimori' | 'TMDB'; external_id: string; title: string;
  image?: string | null; poster_source?: 'TMDB' | null; author?: string; year?: string; description?: string; genres?: string[];
  isbn?: string; publisher?: string; pages?: number | null; episodes?: number | null; seasons?: number | null;
  runtime?: number | null; score?: number | null; studio?: string; original_title?: string;
};
type PosterOption = { id: number; title: string; year: string; image: string; url: string };
type PosterResponse = { poster_state?: string; poster_options?: PosterOption[]; image?: string; poster_source?: 'TMDB' };
export function Poster({ image, title = '', score }: { image?: string | null; title?: string; score?: number | null }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [image]);
  return <div className="catalog-poster">{image && !failed ? <img src={image} alt={title} loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} /> : <div className="catalog-placeholder"><BookOpen size={28} /><span>{title || 'Твоя следующая история'}</span></div>}{score != null && <span className="poster-rating" title="Моя оценка" aria-label={`Моя оценка: ${score.toFixed(1)} из 10`}><span aria-hidden="true">★</span>{score.toFixed(1)}</span>}</div>;
}
export function WatchTitle({ title }: { title: string }) {
  const [open, setOpen] = useState(false);
  const dialog = useRef<HTMLDialogElement | null>(null);
  useEffect(() => {
    if (!open) return;
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, [open]);
  return <><h3 className="watch-title"><button type="button" aria-label={`Открыть полное название: ${title}`} aria-haspopup="dialog" onClick={()=>setOpen(true)}><span>{title}</span></button></h3>{open && createPortal(<dialog ref={dialog} className="catalog-title-dialog" aria-label="Полное название" onCancel={()=>setOpen(false)} onClose={()=>setOpen(false)}><div className="catalog-info-heading"><h2>Полное название</h2><button type="button" aria-label="Закрыть название" onClick={()=>setOpen(false)}>✕</button></div><p>{title}</p></dialog>,document.body)}</>;
}
export function CatalogFacts({ info, compact = false, title }: { info?: CatalogInfo | null; compact?: boolean; title?: string }) {
  const [expanded, setExpanded] = useState(false);
  const panel = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!expanded) return;
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.querySelector<HTMLButtonElement>('button')?.focus();
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { event.stopPropagation(); setExpanded(false); } };
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('keydown', escape); previous?.focus(); };
  }, [expanded]);
  if (!info) return null;
  const tags = [info.year, info.runtime ? `${info.runtime} мин` : '', info.seasons ? `Сезонов: ${info.seasons}` : '', info.studio, info.publisher, ...(info.genres || [])].filter(Boolean);
  if (compact) return <div className="catalog-facts is-compact">
    <div className="catalog-tags">{tags.slice(0,2).map((tag,index)=><span key={index} title={tag}>{tag}</span>)}{tags.length > 2 && <button type="button" className="catalog-tags-toggle" aria-expanded={expanded} aria-haspopup="dialog" onClick={()=>setExpanded(true)}>+{tags.length-2}</button>}</div>
    <p className="catalog-original" title={info.original_title}>{info.original_title && info.original_title !== title ? info.original_title : '\u00a0'}</p>
    <button type="button" className="catalog-more" aria-haspopup="dialog" onClick={()=>setExpanded(true)}>Подробнее</button>
    {expanded && createPortal(<div className="catalog-info-overlay" onClick={event=>{if(event.target===event.currentTarget)setExpanded(false);}}><div ref={panel} role="dialog" aria-modal="true" aria-label={title || info.title} className="catalog-info-panel" onKeyDown={event=>{
      if(event.key!=='Tab')return;
      const controls=panel.current?.querySelectorAll<HTMLElement>('button, a[href]');
      const first=controls?.[0],last=controls?.[controls.length-1];
      if(event.shiftKey && document.activeElement===first){event.preventDefault();last?.focus();}
      else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first?.focus();}
    }}><div className="catalog-info-heading"><h3>{title || info.title}</h3><button type="button" aria-label="Закрыть подробности" onClick={()=>setExpanded(false)}>✕</button></div><div className="catalog-tags">{tags.map((tag,index)=><span key={index}>{tag}</span>)}</div>{info.original_title && <p>{info.original_title}</p>}{info.description && <p className="catalog-description">{info.description}</p>}<small>Источник: {info.source}{info.poster_source && ' · Постер: TMDB'}</small></div></div>,document.body)}
  </div>;
  const shown = tags;
  return <div className={`catalog-facts ${compact ? 'is-compact' : ''}`}><div className="catalog-tags">{shown.map((text, index) => <span key={index}>{text}</span>)}{compact && tags.length > 2 && <button type="button" className="catalog-tags-toggle" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? 'Свернуть' : `+${tags.length - 2}`}</button>}</div>{info.original_title && info.original_title !== info.title && <p>{info.original_title}</p>}{info.description && <details><summary>Описание</summary><p className="catalog-description">{info.description}</p></details>}<small>Источник: {info.source}{info.poster_source && ' · Постер: TMDB'}{info.source === 'Open Library' && ' · Проверь издание и число страниц'}</small></div>;
}
export function CatalogPicker({ kind, title, info, image, onSelect, onImage, onBusy, onPoster, author }: {
  kind: 'book' | 'movie' | 'series' | 'anime'; title: string; author?: string; info?: CatalogInfo | null; image?: string | null;
  onSelect: (info: CatalogInfo) => void; onImage: (image: string) => void; onBusy?: (busy: boolean) => void; onPoster?: (image: string) => void;
}) {
  const [results, setResults] = useState<CatalogInfo[]>([]);
  const [seasonOptions, setSeasonOptions] = useState<CatalogInfo[]>([]);
  const [posterOptions, setPosterOptions] = useState<PosterOption[]>([]);
  const [posterMessage, setPosterMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const request = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const busyCallback = useRef(onBusy); busyCallback.current = onBusy;
  useEffect(() => () => { request.current?.abort(); generation.current++; busyCallback.current?.(false); }, []);
  function pending(value: boolean) { setBusy(value); busyCallback.current?.(value); }
  function acceptPosters(data: PosterResponse) {
    setPosterOptions(data.poster_state === 'choose' ? data.poster_options || [] : []);
    const messages: Record<string,string> = {
      no_key: 'Для запасных постеров добавь TMDB_READ_TOKEN на сервере. Основные сведения аниме уже доступны.',
      unavailable: 'TMDB сейчас недоступен. Сведения аниме сохранены в форме; постер можно найти позже.',
      not_found: 'Подходящий постер не найден. Можно загрузить свою картинку.',
      choose: 'Есть несколько вариантов. Выбери нужный постер — название, серии и заметки останутся прежними.',
      matched: 'Постер найден в TMDB по названию и году.',
    };
    setPosterMessage(messages[data.poster_state || ''] || '');
  }
  async function findPoster() {
    if (!info || info.source !== 'Shikimori') return;
    request.current?.abort(); const controller = new AbortController(); request.current = controller;
    generation.current++; pending(true); setError(''); setPosterOptions([]); setPosterMessage('');
    try {
      const response = await fetch(`/api/catalog/anime-posters?external_id=${encodeURIComponent(info.external_id)}`, {headers:healthHeaders(),signal:controller.signal});
      if (!response.ok) throw await responseError(response);
      const data: PosterResponse = await response.json();
      if (!controller.signal.aborted) {
        acceptPosters(data);
        if (data.poster_state === 'matched' && data.image) onPoster?.(data.image);
      }
    } catch (err) { if (!controller.signal.aborted) setError((err as Error).message); }
    finally { if (!controller.signal.aborted) pending(false); }
  }
  async function search() {
    if (title.trim().length < 2) { setError('Введи хотя бы 2 символа названия.'); return; }
    request.current?.abort(); const controller = new AbortController(); request.current = controller;
    generation.current++; pending(true); setError(''); setResults([]); setSeasonOptions([]); setPosterOptions([]); setPosterMessage('');
    try {
      const response = await fetch(`/api/catalog/search?kind=${kind}&title=${encodeURIComponent(title.trim())}${kind === 'book' && author ? `&author=${encodeURIComponent(author)}` : ''}`, { headers: healthHeaders(), signal: controller.signal });
      if (!response.ok) throw await responseError(response);
      const data = await response.json();
      if (!controller.signal.aborted) { setResults(data.results); if (!data.results.length) setError('Ничего не найдено. Попробуй оригинальное название или добавь вручную.'); }
    } catch (err) { if (!controller.signal.aborted) setError((err as Error).message); }
    finally { if (!controller.signal.aborted) pending(false); }
  }
  async function select(result: CatalogInfo) {
    request.current?.abort(); const controller = new AbortController(); request.current = controller;
    generation.current++; pending(true); setError(''); setPosterOptions([]); setPosterMessage('');
    let chosen = result;
    let chooseSeason = false;
    try {
      const response = await fetch(`/api/catalog/details?kind=${kind}&external_id=${encodeURIComponent(result.external_id)}`, {headers:healthHeaders(),signal:controller.signal});
      if (!response.ok) throw await responseError(response);
      const data = await response.json();
      const {poster_options: _options, poster_state: _state, season_options, ...details} = data;
      if (!controller.signal.aborted && season_options?.length) { setSeasonOptions(season_options); chooseSeason = true; }
      chosen = {...result, ...details};
      if (!controller.signal.aborted) acceptPosters(data);
    } catch { if (!controller.signal.aborted) setError('Основные сведения выбраны. Дополнительные данные пока недоступны — их можно заполнить вручную.'); }
    finally { if (!controller.signal.aborted) { if (!chooseSeason) { onSelect(chosen); setSeasonOptions([]); } setResults([]); pending(false); } }
  }
  async function upload(file?: File) {
    if (!file) return;
    request.current?.abort(); const version = ++generation.current; pending(true); setError(''); setPosterOptions([]); setPosterMessage('');
    try { const value = await prepareCover(file); if (version === generation.current) onImage(value); }
    catch (err) { if (version === generation.current) setError((err as Error).message); }
    finally { if (version === generation.current) pending(false); }
  }
  return <div className="catalog-picker">
    <div className="catalog-selection"><Poster image={image} title={title} /><div><span className="catalog-eyebrow">{kind === 'book' ? 'Найди своё издание' : 'История начинается с выбора'}</span><p>{info ? info.title : 'Обложка и сведения из каталога'}</p><small>{kind === 'book' ? 'Название, автор, издание и страницы' : kind === 'anime' ? 'TMDB: обложка, описание и выбор сезона с числом серий.' : 'Постер, описание и сведения о фильме или сериале'}</small></div></div>
    <div className="catalog-picker-actions"><button type="button" disabled={busy} onClick={() => void search()}><Search size={15} />{busy ? 'Загружаем…' : 'Найти по названию'}</button><label><ImagePlus size={15} />Своя обложка<input aria-label="Загрузить обложку" disabled={busy} type="file" accept="image/jpeg,image/png,image/webp" onChange={event => { void upload(event.target.files?.[0]); event.target.value = ''; }} /></label></div>
    {kind === 'anime' && info?.source === 'Shikimori' && onPoster && <div className="catalog-picker-actions"><button type="button" disabled={busy} onClick={() => void findPoster()}>Найти постер в TMDB</button></div>}
    {posterMessage && <p role="status" className="catalog-upload-hint">{posterMessage}</p>}
    {!!posterOptions.length && <div className="catalog-results" aria-label="Постеры TMDB">{posterOptions.map(option => <button type="button" disabled={busy} key={option.id} aria-label={`Выбрать постер: ${option.title} (${option.year || 'год неизвестен'})`} onClick={() => { onPoster?.(option.image); setPosterOptions([]); setPosterMessage('Выбран постер TMDB. Сведения об аниме не изменены.'); }}><Poster image={option.image} title={option.title} /><strong>{option.title}</strong><small>{option.year || 'Год неизвестен'} · TMDB</small></button>)}</div>}
    {!!seasonOptions.length && <div><p>Выбери сезон — количество серий будет взято для него.</p><div className="catalog-results" aria-label="Сезоны аниме">{seasonOptions.map(season => <button type="button" key={season.external_id} disabled={busy} onClick={() => void select(season)}><Poster image={season.image} title={season.title} /><strong>{season.title}</strong><small>{season.episodes ? `${season.episodes} серий` : 'Число серий неизвестно'}{season.year ? ` · ${season.year}` : ''}</small></button>)}</div></div>}
    {error && <p role="alert" className="catalog-error">{error}</p>}
    {!!results.length && <div className="catalog-results" aria-label="Результаты поиска">{results.map(result => <button type="button" key={result.external_id} disabled={busy} aria-label={`Выбрать: ${result.title}`} onClick={() => void select(result)}><Poster image={result.image} title={result.title} /><strong>{result.title}</strong><small>{[result.author, result.year, result.episodes ? `${result.episodes} серий` : ''].filter(Boolean).join(' · ') || result.source}</small></button>)}</div>}
    <CatalogFacts info={info} />
    <small className="catalog-upload-hint">Своя картинка: JPG, PNG или WebP, до 10 МБ.</small>
  </div>;
}
