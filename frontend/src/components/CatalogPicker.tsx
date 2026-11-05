import { useEffect, useRef, useState } from 'react';
import { BookOpen, ImagePlus, Search } from 'lucide-react';
import { healthHeaders, responseError } from '../healthConnection';
import { prepareCover } from '../coverImage';
import './catalog.css';

export type CatalogInfo = {
  source: 'Open Library' | 'Shikimori' | 'TMDB'; external_id: string; title: string;
  image?: string | null; poster_source?: 'TMDB' | null; author?: string; year?: string; description?: string; genres?: string[];
  publisher?: string; pages?: number | null; episodes?: number | null; seasons?: number | null;
  runtime?: number | null; score?: number | null; studio?: string; original_title?: string;
};
type PosterOption = { id: number; title: string; year: string; image: string; url: string };
type PosterResponse = { poster_state?: string; poster_options?: PosterOption[]; image?: string; poster_source?: 'TMDB' };
export function Poster({ image, title = '' }: { image?: string | null; title?: string }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [image]);
  return <div className="catalog-poster">{image && !failed ? <img src={image} alt={title} loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} /> : <div className="catalog-placeholder"><BookOpen size={28} /><span>{title || 'Твоя следующая история'}</span></div>}</div>;
}
export function CatalogFacts({ info }: { info?: CatalogInfo | null }) {
  if (!info) return null;
  return <div className="catalog-facts"><div className="catalog-tags">{[info.year, info.runtime ? `${info.runtime} мин` : '', info.seasons ? `Сезонов: ${info.seasons}` : '', info.studio, info.publisher, ...(info.genres || []).slice(0, 3)].filter(Boolean).map((text, index) => <span key={index}>{text}</span>)}{info.score != null && <span className="catalog-score">★ {info.score.toFixed(1)} · {info.source}</span>}</div>{info.original_title && info.original_title !== info.title && <p>{info.original_title}</p>}{info.description && <details><summary>Описание</summary><p className="catalog-description">{info.description}</p></details>}<small>Источник: {info.source}{info.poster_source && ' · Постер: TMDB'}{info.source === 'Open Library' && ' · Проверь издание и число страниц'}</small></div>;
}
export function CatalogPicker({ kind, title, info, image, onSelect, onImage, onBusy, onPoster }: {
  kind: 'book' | 'movie' | 'series' | 'anime'; title: string; info?: CatalogInfo | null; image?: string | null;
  onSelect: (info: CatalogInfo) => void; onImage: (image: string) => void; onBusy?: (busy: boolean) => void; onPoster?: (image: string) => void;
}) {
  const [results, setResults] = useState<CatalogInfo[]>([]);
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
    generation.current++; pending(true); setError(''); setResults([]); setPosterOptions([]); setPosterMessage('');
    try {
      const response = await fetch(`/api/catalog/search?kind=${kind}&title=${encodeURIComponent(title.trim())}`, { headers: healthHeaders(), signal: controller.signal });
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
    try {
      const response = await fetch(`/api/catalog/details?kind=${kind}&external_id=${encodeURIComponent(result.external_id)}`, {headers:healthHeaders(),signal:controller.signal});
      if (!response.ok) throw await responseError(response);
      const data = await response.json();
      const {poster_options: _options, poster_state: _state, ...details} = data;
      chosen = {...result, ...details};
      if (!controller.signal.aborted) acceptPosters(data);
    } catch { if (!controller.signal.aborted) setError('Основные сведения выбраны. Дополнительные данные пока недоступны — их можно заполнить вручную.'); }
    finally { if (!controller.signal.aborted) { onSelect(chosen); setResults([]); pending(false); } }
  }
  async function upload(file?: File) {
    if (!file) return;
    request.current?.abort(); const version = ++generation.current; pending(true); setError(''); setPosterOptions([]); setPosterMessage('');
    try { const value = await prepareCover(file); if (version === generation.current) onImage(value); }
    catch (err) { if (version === generation.current) setError((err as Error).message); }
    finally { if (version === generation.current) pending(false); }
  }
  return <div className="catalog-picker">
    <div className="catalog-selection"><Poster image={image} title={title} /><div><span className="catalog-eyebrow">{kind === 'book' ? 'Найди своё издание' : 'История начинается с выбора'}</span><p>{info ? info.title : 'Обложка и сведения из каталога'}</p><small>{kind === 'book' ? 'Название, автор, издание и страницы' : kind === 'anime' ? 'Постер, описание, студия, жанры и серии.' : 'Постер, описание и сведения о фильме или сериале'}</small></div></div>
    <div className="catalog-picker-actions"><button type="button" disabled={busy} onClick={() => void search()}><Search size={15} />{busy ? 'Загружаем…' : 'Найти по названию'}</button><label><ImagePlus size={15} />Своя обложка<input aria-label="Загрузить обложку" disabled={busy} type="file" accept="image/jpeg,image/png,image/webp" onChange={event => { void upload(event.target.files?.[0]); event.target.value = ''; }} /></label></div>
    {kind === 'anime' && info?.source === 'Shikimori' && onPoster && <div className="catalog-picker-actions"><button type="button" disabled={busy} onClick={() => void findPoster()}>Найти постер в TMDB</button></div>}
    {posterMessage && <p role="status" className="catalog-upload-hint">{posterMessage}</p>}
    {!!posterOptions.length && <div className="catalog-results" aria-label="Постеры TMDB">{posterOptions.map(option => <button type="button" disabled={busy} key={option.id} aria-label={`Выбрать постер: ${option.title} (${option.year || 'год неизвестен'})`} onClick={() => { onPoster?.(option.image); setPosterOptions([]); setPosterMessage('Выбран постер TMDB. Сведения об аниме не изменены.'); }}><Poster image={option.image} title={option.title} /><strong>{option.title}</strong><small>{option.year || 'Год неизвестен'} · TMDB</small></button>)}</div>}
    {error && <p role="alert" className="catalog-error">{error}</p>}
    {!!results.length && <div className="catalog-results" aria-label="Результаты поиска">{results.map(result => <button type="button" key={result.external_id} disabled={busy} aria-label={`Выбрать: ${result.title}`} onClick={() => void select(result)}><Poster image={result.image} title={result.title} /><strong>{result.title}</strong><small>{[result.author, result.year, result.episodes ? `${result.episodes} серий` : ''].filter(Boolean).join(' · ') || result.source}</small></button>)}</div>}
    <CatalogFacts info={info} />
    <small className="catalog-upload-hint">Своя картинка: JPG, PNG или WebP, до 10 МБ.</small>
  </div>;
}
