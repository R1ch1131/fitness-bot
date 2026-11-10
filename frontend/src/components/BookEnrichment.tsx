import { useEffect, useRef, useState } from 'react';
import { CatalogPicker } from './CatalogPicker';
import type { CatalogInfo } from './CatalogPicker';
import type { BookItem } from '../types';

export function BookEnrichment({ book, onSave, onClose }: { book: BookItem; onSave: (updates: Partial<BookItem>) => Promise<void>; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [query, setQuery] = useState(book.title);
  const [chosen, setChosen] = useState<CatalogInfo | null>(null);
  const [busy, setBusy] = useState(false);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { dialog.current?.showModal(); return () => dialog.current?.close(); }, []);
  async function save() {
    if (!chosen) return;
    setBusy(true); setError('');
    try {
      const old = book.catalog;
      const catalog = old ? {...chosen, ...Object.fromEntries(Object.entries(old).filter(([,value]) => value != null && value !== '' && (!Array.isArray(value) || value.length > 0)))} as CatalogInfo : chosen;
      if (!old?.description && chosen.description) {
        catalog.description = chosen.description;
        catalog.description_source = chosen.description_source || (chosen.source === 'Google Books' ? 'Google Books' : 'Open Library');
      }
      await onSave({catalog, ...(!book.cover_image && chosen.image ? {cover_image:chosen.image} : {})});
      onClose();
    } catch (e) { setError((e as Error).message || 'Не удалось сохранить сведения. Попробуй ещё раз.'); }
    finally { setBusy(false); }
  }
  return <dialog ref={dialog} className="book-enrichment" aria-label="Дополнить сведения о книге" onCancel={event => {if (busy) event.preventDefault(); else onClose();}} onClose={onClose}>
    <div className="catalog-info-heading"><h2>Дополнить сведения</h2><button type="button" aria-label="Закрыть сведения" disabled={busy} onClick={onClose}>✕</button></div>
    <p>{book.title} · {book.author}</p><p className="book-enrichment-note">Выбери свою книгу в каталоге. Добавим недостающие сведения и обложку. Твои страницы, оценка и заметки сохранятся.</p>
    <label>Название для поиска<input value={query} disabled={busy} onChange={event=>setQuery(event.target.value)} /></label>
    <fieldset disabled={busy}><CatalogPicker kind="book" title={query} author={book.author} info={chosen} image={chosen?.image || book.cover_image} onBusy={setSearching} onSelect={setChosen} onImage={image=>setChosen(current=>current ? {...current,image} : current)} /></fieldset>
    {chosen && !chosen.description && <p role="status">Описание не найдено в Google Books и Open Library. Можно сохранить доступные сведения или выбрать другое издание.</p>}
    {error && <p role="alert">{error}</p>}
    <button type="button" className="book-enrichment-save" disabled={!chosen || busy || searching} onClick={()=>void save()}>{busy ? 'Сохраняем…' : 'Сохранить сведения'}</button>
  </dialog>;
}
