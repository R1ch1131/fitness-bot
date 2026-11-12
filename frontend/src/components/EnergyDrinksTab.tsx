import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ImagePlus, LayoutGrid, List, Pencil, Plus, Search, Trash2, Zap } from 'lucide-react';
import { healthHeaders, responseError } from '../healthConnection';
import { prepareCover } from '../coverImage';

type Drink = { image_source?: 'UPCitemdb' | 'Open Food Facts' | null; id: string; title: string; image: string | null; rating: number | null; notes: string };
type Product = { source?: 'UPCitemdb' | 'Open Food Facts'; id: string; title: string; brand: string; quantity: string; image: string };
const empty = {title:'',image:null,rating:null,image_source:null,notes:''};

export function EnergyDrinksTab({onBack}: {onBack:()=>void}) {
  const [items,setItems]=useState<Drink[]>([]);
  const [ready,setReady]=useState(false),[error,setError]=useState(''),[retry,setRetry]=useState(0);
  const [layout,setLayout]=useState<'list'|'grid'>('list');
  const [query,setQuery]=useState('');
  const [draft,setDraft]=useState<Omit<Drink,'id'> | null>(null),[editing,setEditing]=useState<string|null>(null);
  const [deleting,setDeleting]=useState<Drink|null>(null);
  const [busy,setBusy]=useState(false),[searching,setSearching]=useState(false);
  const [results,setResults]=useState<Product[]>([]),[formError,setFormError]=useState('');
  const dialog=useRef<HTMLDialogElement>(null);
  const request=useRef<AbortController|null>(null);
  const generation=useRef(0);
  const modal=!!draft||!!deleting;
  useEffect(()=>{const controller=new AbortController();setReady(false);setError('');void(async()=>{try{const r=await fetch('/api/energy-drinks',{headers:healthHeaders(),cache:'no-store',signal:controller.signal});if(!r.ok)throw await responseError(r);const data=await r.json();if(!Array.isArray(data.items))throw Error('Не удалось прочитать коллекцию');if(!controller.signal.aborted){setItems(data.items);setReady(true);}}catch(e){if(!controller.signal.aborted)setError((e as Error).message);}})();return()=>controller.abort();},[retry]);
  useEffect(()=>{if(modal)dialog.current?.showModal();else dialog.current?.close();},[modal]);
  useEffect(()=>()=>{request.current?.abort();generation.current++;},[]);
  function close(){if(busy)return;request.current?.abort();generation.current++;setDraft(null);setDeleting(null);setResults([]);setFormError('');setSearching(false);}
  async function mutate(method:string,id?:string){setBusy(true);setFormError('');try{const r=await fetch('/api/energy-drinks'+(id?'/'+encodeURIComponent(id):''),{method,headers:{'Content-Type':'application/json',...healthHeaders()},...(method!=='DELETE'?{body:JSON.stringify(draft)}:{})});if(!r.ok)throw await responseError(r);const data=await r.json();if(!Array.isArray(data.items))throw Error('Не удалось подтвердить сохранение');setItems(data.items);setDraft(null);setDeleting(null);setResults([]);}catch(e){setFormError((e as Error).message);}finally{setBusy(false);}}
  async function search(){if(!draft||draft.title.trim().length<2){setFormError('Введи хотя бы 2 символа названия.');return;}request.current?.abort();const controller=new AbortController();request.current=controller;generation.current++;setSearching(true);setFormError('');setResults([]);try{const r=await fetch('/api/energy-drinks/search?title='+encodeURIComponent(draft.title.trim()),{headers:healthHeaders(),signal:controller.signal});if(!r.ok)throw await responseError(r);const data=await r.json();if(!controller.signal.aborted){setResults(data.results);if(!data.results.length)setFormError('Не нашли картинку. Попробуй бренд и вкус, например Monster Mango Loco, или загрузи фото.');}}catch(e){if(!controller.signal.aborted)setFormError((e as Error).message);}finally{if(!controller.signal.aborted)setSearching(false);}}
  async function upload(file?:File){if(!file)return;request.current?.abort();const version=++generation.current;setSearching(true);setFormError('');setResults([]);try{const image=await prepareCover(file);if(version===generation.current)setDraft(current=>current?{...current,image,image_source:null}:current);}catch(e){if(version===generation.current)setFormError((e as Error).message);}finally{if(version===generation.current)setSearching(false);}}
  const visible=items.filter(item=>item.title.toLowerCase().includes(query.toLowerCase())).sort((a,b)=>(b.rating??-1)-(a.rating??-1)||a.title.localeCompare(b.title,'ru'));
  return <section className="energy-page">
    <button type="button" className="energy-back" onClick={onBack}><ArrowLeft size={16}/>К играм и фильмам</button>
    <div className="energy-heading"><div><span className="catalog-eyebrow">Личная коллекция вкусов</span><h2><Zap size={24}/>Энергетики</h2><p>{items.length} в коллекции · твои оценки и впечатления</p></div><button type="button" className="media-view-toggle" aria-label={layout==='list'?'Показать энергетики карточками':'Показать энергетики списком'} onClick={()=>setLayout(value=>value==='list'?'grid':'list')}>{layout==='list'?<LayoutGrid size={18}/>:<List size={18}/>}</button></div>
    <input className="energy-input" aria-label="Поиск энергетиков в коллекции" placeholder="Найти в своей коллекции…" value={query} onChange={event=>setQuery(event.target.value)}/>
    {error&&<p role="alert">{error}<button onClick={()=>setRetry(value=>value+1)}>Повторить</button></p>}
    {!ready&&!error&&<p role="status">Загружаем коллекцию…</p>}
    {ready&&!visible.length&&<div className="energy-empty"><Zap size={32}/><h3>{items.length?'Ничего не найдено':'Какой вкус запомнился?'}</h3><p>Добавь энергетик, поставь оценку и сохрани впечатления.</p></div>}
    <div className={`energy-collection is-${layout}`}>{visible.map(item=><article className="energy-card" key={item.id}><div className="energy-art">{item.image?<img src={item.image} alt={item.title} loading="lazy" onError={event=>{event.currentTarget.style.visibility='hidden';}}/>:<Zap size={32}/>}</div><div className="energy-card-body"><h3>{item.title}</h3><strong className="energy-score">{item.rating==null?'Без оценки':`★ ${item.rating} / 10`}</strong>{item.notes&&<p>{item.notes}</p>}<div className="energy-card-actions"><button aria-label={`Редактировать энергетик ${item.title}`} onClick={()=>{setEditing(item.id);setDraft({title:item.title,image:item.image,rating:item.rating,notes:item.notes,image_source:item.image_source});setFormError('');}}><Pencil size={16}/></button><button aria-label={`Удалить энергетик ${item.title}`} onClick={()=>{setDeleting(item);setFormError('');}}><Trash2 size={16}/></button></div></div></article>)}</div>
    <p className="energy-credits">Поиск разных брендов: <a href="https://www.upcitemdb.com" target="_blank" rel="noreferrer">UPCitemdb</a>, запасной каталог — <a href="https://world.openfoodfacts.org" target="_blank" rel="noreferrer">Open Food Facts</a> (его фотографии — CC BY-SA). В UPCitemdb бесплатно до 20 поисков в сутки; повторные запросы сохраняются в кэше. Качество фото зависит от товара; можно загрузить своё.</p>
    <button type="button" disabled={!ready||busy} className="media-add-button" onClick={()=>{setEditing(null);setDraft({...empty});setFormError('');setResults([]);}}><Plus size={18}/>Добавить энергетик</button>
    {modal&&<dialog ref={dialog} className="energy-dialog" aria-label={deleting?'Удалить энергетик':'Энергетик'} onCancel={event=>{event.preventDefault();close();}}><div className="catalog-info-heading"><h2>{deleting?'Удалить энергетик?':editing?'Редактировать энергетик':'Новый энергетик'}</h2><button aria-label="Закрыть энергетик" disabled={busy} onClick={close}>✕</button></div>{formError&&<p role="alert">{formError}</p>}{deleting?<><p>«{deleting.title}» исчезнет из коллекции.</p><button className="energy-save" disabled={busy} onClick={()=>void mutate('DELETE',deleting.id)}>Удалить</button></>:draft&&<form onSubmit={event=>{event.preventDefault();void mutate(editing?'PUT':'POST',editing||undefined);}}><fieldset disabled={busy}>
    <label>Название<input className="energy-input" required maxLength={200} value={draft.title} onChange={event=>setDraft({...draft,title:event.target.value})}/></label>
    <div className="energy-art energy-preview">{draft.image?<img src={draft.image} alt={draft.title}/>:<Zap size={36}/>}</div>
    {draft.image_source && <p className="energy-image-source">Фото: {draft.image_source}</p>}
    <div className="energy-search-actions"><button type="button" disabled={searching} onClick={()=>void search()}><Search size={15}/>{searching?'Ищем…':'Найти картинку'}</button><label><ImagePlus size={15}/>Своё фото<input aria-label="Загрузить фото энергетика" disabled={searching} type="file" accept="image/png,image/jpeg,image/webp" onChange={event=>{void upload(event.target.files?.[0]);event.target.value='';}}/></label></div>
    {!!results.length&&<div className="energy-results" aria-label="Картинки энергетиков">{results.map(product=><button type="button" key={product.id} onClick={()=>{setDraft({...draft,image:product.image,image_source:product.source || 'Open Food Facts'});setResults([]);}}><img src={product.image} alt=""/><strong>{product.title}</strong><small>{product.brand} {product.quantity}</small><small className="energy-result-source">{product.source === 'UPCitemdb' ? 'Товарный каталог · UPCitemdb' : 'Open Food Facts'}</small></button>)}</div>}
    <label>Оценка от 0 до 10<input className="energy-input" type="number" inputMode="decimal" min={0} max={10} step="0.1" placeholder="Например, 8.5" value={draft.rating??''} onChange={event=>setDraft({...draft,rating:event.target.value===''?null:Number(event.target.value)})}/></label>
    <label>Заметки<textarea className="energy-input" rows={3} maxLength={10000} placeholder="Вкус, сладость, послевкусие…" value={draft.notes} onChange={event=>setDraft({...draft,notes:event.target.value})}/></label>
    <button className="energy-save" disabled={busy||searching||!draft.title.trim()}>{busy?'Сохраняем…':'Сохранить'}</button>
    </fieldset></form>}</dialog>}
  </section>;
}
