import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const source = ts.transpileModule(readFileSync(new URL('./src/components/NotificationSchedule.tsx', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;

async function panel({ failLoad = false, failSave = false } = {}) {
  const state = [], effects = [], requests = [];
  let index = 0, first = true;
  const defaults = {
    gym: { enabled: true, time: '08:30' }, laundry: { enabled: true, time: '22:00' },
    nutrition: { enabled: true, time: '23:00' }, weekly: { enabled: true, time: '12:00' },
    checkin: { enabled: true, delay_minutes: 20 },
  };
  const jsx = (type, props) => ({ type, props });
  const context = { exports: {}, AbortSignal, require: name => name === 'react/jsx-runtime' ? { jsx, jsxs: jsx } : {
    useState(initial) {
      const slot = index++;
      if (first) state[slot] = initial;
      return [state[slot], value => { state[slot] = typeof value === 'function' ? value(state[slot]) : value; }];
    },
    useEffect(effect) { if (first) effects.push(effect); },
  }, fetch: async (url, options) => {
    requests.push({ url, options });
    const saving = options.method === 'POST';
    return { ok: !(saving ? failSave : failLoad), json: async () => saving && failSave ? { detail: 'Cloud unavailable' }
      : { status: 'ok', settings: saving ? JSON.parse(options.body) : defaults } };
  } };
  vm.runInNewContext(source, context);
  const render = () => { index = 0; const tree = context.exports.NotificationSchedule(); first = false; return tree; };
  render();
  for (const effect of effects) effect();
  await new Promise(setImmediate);
  return { render, state, requests };
}

function nodes(tree) {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children)];
}
const find = (tree, predicate) => nodes(tree).find(predicate);
const save = tree => find(tree, n => n.type === 'button' && n.props.children === 'Сохранить расписание');

test('editing time saves a complete schedule and confirms only the server result', async () => {
  const p = await panel();
  let tree = p.render();
  assert.equal(save(tree).props.disabled, true);
  find(tree, n => n.props?.['aria-label'] === 'Время: Взять вещи в зал').props.onChange({ target: { value: '07:15' } });
  tree = p.render();
  assert.equal(save(tree).props.disabled, false);
  await save(tree).props.onClick();
  assert.equal(JSON.parse(p.requests.at(-1).options.body).gym.time, '07:15');
  assert.match(p.state[3], /сохранено/);
  assert.equal(save(p.render()).props.disabled, true);
});

test('cloud error keeps unsaved changes and allows retry', async () => {
  const p = await panel({ failSave: true });
  find(p.render(), n => n.props?.['aria-label'] === 'Задержка опроса в минутах').props.onChange({ target: { value: '45' } });
  await save(p.render()).props.onClick();
  assert.equal(p.state[0].checkin.delay_minutes, 45);
  assert.equal(p.state[3], 'Cloud unavailable');
  assert.equal(save(p.render()).props.disabled, false);
});

test('disabled category keeps its time and invalid delay cannot be submitted', async () => {
  const p = await panel();
  find(p.render(), n => n.type === 'input' && n.props.type === 'checkbox').props.onChange({ target: { checked: false } });
  assert.equal(p.state[0].gym.time, '08:30');
  assert.equal(find(p.render(), n => n.props?.['aria-label'] === 'Время: Взять вещи в зал').props.disabled, true);
  find(p.render(), n => n.props?.['aria-label'] === 'Задержка опроса в минутах').props.onChange({ target: { value: '0' } });
  assert.equal(save(p.render()).props.disabled, true);
});

test('failed initial load never permits overwriting settings with defaults', async () => {
  const p = await panel({ failLoad: true });
  assert.equal(p.state[0], null);
  assert.equal(save(p.render()), undefined);
  assert.match(p.state[3], /загрузить/);
});
