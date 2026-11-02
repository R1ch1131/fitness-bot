import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const source = ts.transpileModule(readFileSync(new URL('./src/components/MediaTab.tsx', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;
const tick = () => new Promise(setImmediate);
const sample = { id: '1', title: 'Игра', kind: 'game', status: 'planned', progress: 0, total: 100, rating: null, notes: '', updated_at: '2026-11-03' };

async function panel({ failLoad = false, failSave = false, failSteam = false } = {}) {
  const state = [], effects = [], requests = [], storage = new Map();
  let index = 0, first = true;
  const jsx = (type, props) => ({ type, props });
  const hooks = {
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
      if (url === '/api/media/steam/sync') return { ok: !failSteam, json: async () => ({ items: [{ ...sample, steam_appid: 10, steam_playtime_minutes: 301 }], steam_sync: { added: 1, updated: 0, matched: 1 } }) };
      return { ok: !(saving ? failSave : failLoad), json: async () => ({ items: saving === 'DELETE' ? [] : saving ? [{ ...sample, ...JSON.parse(options.body) }] : [sample] }) };
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
const button = (tree, text) => find(tree, node => node.type === 'button' && node.props.children === text);

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
  assert.ok(find(p.render(), n => n.type === 'p' && Array.isArray(n.props.children) && n.props.children.includes(5) && n.props.children.includes(1)));
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
