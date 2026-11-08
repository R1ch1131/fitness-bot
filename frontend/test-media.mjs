import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const source = ts.transpileModule(readFileSync(new URL('./src/components/MediaTab.tsx', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;
const tick = () => new Promise(setImmediate);
const sample = { id: '1', title: 'Игра', kind: 'game', status: 'finished', progress: 100, total: 100, rating: null, notes: '', updated_at: '2026-11-03' };

async function panel({ failLoad = false, failSave = false, failSteam = false, storageBackend, failStorage = false, items = [sample] } = {}) {
  const state = [], effects = [], requests = [], storage = new Map();
  let index = 0, first = true;
  const jsx = (type, props) => ({ type, props });
  const hooks = {
    useCallback: value => value,
    useState(initial) {
      const slot = index++;
      if (first) state[slot] = typeof initial === 'function' ? initial() : initial;
      return [state[slot], value => { state[slot] = typeof value === 'function' ? value(state[slot]) : value; }];
    },
    useRef(value) { const slot = index++; if (first) state[slot] = { current: value }; return state[slot]; },
    useEffect(effect) { if (first) effects.push(effect); },
  };
  const context = { exports: {}, AbortController, window: { addEventListener() {}, removeEventListener() {} },
    localStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) },
    require: name => name === 'react/jsx-runtime' ? { jsx, jsxs: jsx } : name === 'react' ? hooks : name.includes('healthConnection') ? {
      healthHeaders: () => ({}), responseError: async () => new Error('Ошибка сервера'),
    } : new Proxy({}, { get: (_, key) => key }),
    fetch: async (url, options) => {
      requests.push({ url, options });
      const saving = options.method;
      if (url === '/api/media/storage') return {ok:!failStorage,json:async()=>({backend:'upstash',state:'verified',count:1,message:'Upstash отвечает'})};
      if (url.startsWith('/api/media/covers?')) return { ok: true, json: async () => ({ results: [{ title: 'Игра — полное название', image: 'https://cdn.akamai.steamstatic.com/steam/apps/620/header.jpg' }] }) };
      if (url === '/api/media/steam/sync') return { ok: !failSteam, json: async () => ({ items: [{ ...sample, steam_appid: 10, steam_playtime_minutes: 301 }], steam_sync: { added: 1, updated: 0, matched: 1 } }) };
      return { ok: !(saving ? failSave : failLoad), json: async () => ({ items: saving === 'DELETE' ? [] : saving ? [{ ...sample, ...JSON.parse(options.body) }] : items, ...(storageBackend ? {storage:{backend:storageBackend,state:storageBackend==='upstash'?'configured':'not_configured'}} : {}) }) };
    },
  };
  vm.runInNewContext(source, context);
  const render = () => { index = 0; const tree = context.exports.MediaTab(); first = false; return tree; };
  render();
  effects.forEach(effect => effect());
  await tick();
  return { render, requests, storage };
}

function nodes(tree) {
  if (!tree || typeof tree !== 'object') return [];
  return Array.isArray(tree) ? tree.flatMap(nodes) : [tree, ...nodes(tree.props?.children)];
}
const find = (tree, predicate) => nodes(tree).find(predicate);
const label = value => Array.isArray(value) ? value.map(label).join('') : value && typeof value === 'object' ? label(value.props?.children) : value == null || typeof value === 'boolean' ? '' : String(value);
const button = (tree, text) => find(tree, node => node.type === 'button' && label(node.props.children) === text);

test('games default to descending personal ratings including fractions and zero, with unrated games last', async () => {
  const p = await panel({ items: [
    { ...sample, id: '1', title: 'Без оценки', rating: null },
    { ...sample, id: '2', title: 'Ноль', rating: 0 },
    { ...sample, id: '3', title: 'Пять с половиной', rating: 5.5 },
    { ...sample, id: '4', title: 'Девять', rating: 9 },
  ] });
  assert.deepEqual(nodes(p.render()).filter(n => n.type === 'article').map(n => label(find(n, child => child.type === 'h3'))),
    ['Девять', 'Пять с половиной', 'Ноль', 'Без оценки']);
});

test('games open with the current manual game and completed games, while planned games remain accessible', async () => {
  const p = await panel({ items: [sample,
    { ...sample, id: '2', title: 'Текущая игра', status: 'active', progress: 30 },
    { ...sample, id: '3', title: 'Будущая игра', status: 'planned', progress: 0 },
  ] });
  const tree = p.render();
  assert.equal(button(tree, 'Завершено').props['aria-pressed'], true);
  assert.ok(find(tree, n => n.type === 'h3' && n.props.children === 'Текущая игра'));
  assert.ok(find(tree, n => n.type === 'h3' && n.props.children === 'Игра'));
  assert.equal(find(tree, n => n.type === 'h3' && n.props.children === 'Будущая игра'), undefined);
  button(tree, 'Все игры').props.onClick();
  assert.ok(find(p.render(), n => n.type === 'h3' && n.props.children === 'Будущая игра'));
});

test('all watch categories sort by personal rating across statuses and retain list layout when switching', async () => {
  const items = ['movie', 'series', 'anime'].flatMap(kind => [
    { ...sample, id: kind + '1', kind, title: 'Смотрю', status: 'active', rating: 5.5 },
    { ...sample, id: kind + '2', kind, title: 'Лучшее', status: 'finished', rating: 9 },
    { ...sample, id: kind + '3', kind, title: 'Без оценки', status: 'planned', rating: null },
  ]);
  const p = await panel({ items });
  button(p.render(), 'Список').props.onClick();
  for (const category of ['Фильмы', 'Сериалы', 'Аниме']) {
    button(p.render(), category).props.onClick();
    const tree = p.render();
    assert.equal(tree.props['data-layout'], 'list');
    assert.equal(button(tree, 'Список').props['aria-pressed'], true);
    assert.deepEqual(nodes(tree).filter(n => n.type === 'article').map(n => find(n, child => child.type === 'Poster').props.title),
      ['Лучшее', 'Смотрю', 'Без оценки']);
  }
});

test('game personal rating is on the cover and is not repeated in the footer', async () => {
  const p = await panel({ items: [{ ...sample, rating: 8.5 }] });
  const tree = p.render();
  const cover = find(tree, n => n.props?.className === 'game-card-cover');
  assert.ok(find(cover, n => n.props?.['aria-label'] === 'Моя оценка: 8.5 из 10'));
  const footer = find(tree, n => n.props?.className === 'game-card-footer');
  assert.doesNotMatch(label(footer), /★/);
});

test('failed initial load cannot overwrite saved collection', async () => {
  const p = await panel({ failLoad: true });
  const tree = p.render();
  assert.equal(find(tree, n => n.type === 'button' && Array.isArray(n.props.children) && n.props.children.includes('Добавить')).props.disabled, true);
  assert.ok(find(tree, n => n.props?.role === 'alert'));
  assert.equal(p.requests.length, 1);
});

test('failed edit keeps the form and saved backup intact', async () => {
  const p = await panel({ failSave: true });
  const backup = p.storage.get('fitpulse_media_backup_v1');
  find(p.render(), n => n.props?.['aria-label'] === 'Редактировать Игра').props.onClick();
  find(p.render(), n => n.type === 'form').props.onSubmit({ preventDefault() {} });
  await tick();
  assert.ok(find(p.render(), n => n.type === 'form'));
  assert.ok(find(p.render(), n => n.props?.role === 'alert'));
  assert.equal(p.storage.get('fitpulse_media_backup_v1'), backup);
});

test('delete requires confirmation and persists an empty backup', async () => {
  const p = await panel();
  find(p.render(), n => n.props?.['aria-label'] === 'Удалить Игра').props.onClick();
  assert.equal(p.requests.length, 1);
  button(p.render(), 'Удалить').props.onClick();
  await tick();
  assert.equal(p.requests.at(-1).options.method, 'DELETE');
  assert.equal(p.storage.get('fitpulse_media_backup_v1'), '[]');
  assert.equal(find(p.render(), n => n.props?.role === 'dialog'), undefined);
});

test('category filter switches games to movies without another request', async () => {
  const p = await panel();
  assert.ok(find(p.render(), n => n.type === 'h3' && n.props.children === 'Игра'));
  find(p.render(), n => n.type === 'button' && Array.isArray(n.props.children) && n.props.children.includes('Фильмы')).props.onClick();
  assert.equal(find(p.render(), n => n.type === 'h3'), undefined);
  assert.equal(p.requests.length, 1);
});


test('Steam sync displays exact time and confirms counts after server success', async () => {
  const p = await panel();
  button(p.render(), 'Синхронизировать Steam').props.onClick();
  await tick();
  assert.equal(p.requests.at(-1).url, '/api/media/steam/sync');
  assert.equal(p.requests.at(-1).options.method, 'POST');
  assert.ok(find(p.render(), n => n.props?.role === 'status' && n.props.children === 'Steam: добавлено 1, обновлено 0.'));
  assert.match(p.storage.get('fitpulse_media_backup_v1'), /steam_playtime_minutes/);
  assert.ok(find(p.render(), n => n.type === 'span' && label(n.props.children) === '5 ч 1 мин'));
});

test('Steam failure leaves the existing collection and backup intact', async () => {
  const p = await panel({ failSteam: true });
  const before = p.storage.get('fitpulse_media_backup_v1');
  button(p.render(), 'Синхронизировать Steam').props.onClick();
  await tick();
  assert.ok(find(p.render(), n => n.props?.role === 'alert'));
  assert.equal(p.storage.get('fitpulse_media_backup_v1'), before);
  assert.ok(find(p.render(), n => n.type === 'h3' && n.props.children === 'Игра'));
});


test('manual cover selection saves artwork without linking a Steam account', async () => {
  const p = await panel();
  find(p.render(), n => n.props?.['aria-label'] === 'Редактировать Игра').props.onClick();
  await button(p.render(), 'Найти по названию').props.onClick();
  await tick();
  find(p.render(), n => n.props?.['aria-label'] === 'Выбрать обложку: Игра — полное название').props.onClick();
  find(p.render(), n => n.type === 'form').props.onSubmit({ preventDefault() {} });
  await tick();
  const saved = JSON.parse(p.requests.at(-1).options.body);
  assert.equal(saved.title, 'Игра — полное название');
  assert.equal(saved.cover_image, 'https://cdn.akamai.steamstatic.com/steam/apps/620/header.jpg');
  assert.equal(saved.steam_appid, undefined);
});

test('catalog selection fills full title and episodes but preserves personal fields', async () => {
  const p = await panel();
  button(p.render(), 'Аниме').props.onClick();
  button(p.render(), 'Добавить').props.onClick();
  const input = (type, value) => find(p.render(), n=>n.type===type && n.props?.value===value);
  input('textarea', '').props.onChange({target:{value:'Моя заметка'}});
  find(p.render(), n=>n.type?.name==='RatingInput').props.onChange(9);
  find(p.render(), n=>n.type==='CatalogPicker').props.onSelect({source:'Shikimori',external_id:'52991',title:'Полное название',image:'https://shikimori.one/system/animes/original/52991.jpg',episodes:28,score:8.5});
  find(p.render(), n=>n.type==='form').props.onSubmit({preventDefault(){}});
  await tick();
  const saved=JSON.parse(p.requests.at(-1).options.body);
  assert.equal(saved.title,'Полное название');
  assert.equal(saved.total,28);
  assert.equal(saved.notes,'Моя заметка');
  assert.equal(saved.rating,9);
  assert.equal(saved.catalog.score,8.5);
  assert.equal(saved.progress,0);
});

test('choosing a replacement anime poster preserves title, episodes, notes and rating', async () => {
  const p = await panel();
  button(p.render(), 'Аниме').props.onClick();
  button(p.render(), 'Добавить').props.onClick();
  find(p.render(), n=>n.type==='CatalogPicker').props.onSelect({source:'Shikimori',external_id:'1535',title:'Тетрадь смерти',episodes:37,score:8.6});
  find(p.render(), n=>n.type==='textarea').props.onChange({target:{value:'Моя заметка'}});
  find(p.render(), n=>n.type?.name==='RatingInput').props.onChange(9);
  find(p.render(), n=>n.type==='input' && n.props?.value===37).props.onChange({target:{value:'40'}});
  find(p.render(), n=>n.type==='CatalogPicker').props.onPoster('https://image.tmdb.org/t/p/w500/poster.jpg');
  find(p.render(), n=>n.type==='form').props.onSubmit({preventDefault(){}});
  await tick();
  const saved=JSON.parse(p.requests.at(-1).options.body);
  assert.equal(saved.title,'Тетрадь смерти');
  assert.equal(saved.total,40);
  assert.equal(saved.rating,9);
  assert.equal(saved.notes,'Моя заметка');
  assert.equal(saved.catalog.source,'Shikimori');
  assert.equal(saved.catalog.poster_source,'TMDB');
  assert.equal(saved.cover_image,'https://image.tmdb.org/t/p/w500/poster.jpg');
});


test('storage status is confirmed by a read and a failed check is visible', async () => {
  const p=await panel({storageBackend:'upstash',failStorage:true});
  assert.ok(find(p.render(),n=>n.type==='strong' && n.props.children==='Хранилище: Upstash Redis'));
  await button(p.render(),'Проверить').props.onClick();
  await tick();
  assert.equal(p.requests.at(-1).url,'/api/media/storage');
  assert.ok(find(p.render(),n=>n.props?.role==='status' && n.props.children==='Ошибка сервера'));
  assert.ok(find(p.render(),n=>n.type==='h3' && n.props.children==='Игра'));
});
