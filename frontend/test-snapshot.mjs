import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const source = ts.transpileModule(readFileSync(new URL('./src/snapshot.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
function cache() {
  const values = new Map();
  let now = '2026-10-25T17:59:00Z';
  class Clock extends Date { constructor(value) { super(value === undefined ? now : value); } }
  const storage = { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value) };
  const context = { exports: {}, Date: Clock, localStorage: storage };
  vm.runInNewContext(source, context);
  return { api: context.exports, values, storage, setTime: time => { now = time; } };
}

test('confirmed marks are available before the first network response', () => {
  const c = cache();
  const marks = [{ id: 'reading', title: 'Чтение', history: { '2026-10-25': true } }];
  c.api.writeSnapshot('habits', marks);
  assert.equal(JSON.stringify(c.api.readSnapshot('habits', c.api.isHabits)), JSON.stringify(marks));
});

test('yesterday snapshots expire at midnight in Omsk', () => {
  const c = cache();
  c.api.writeSnapshot('habits', []);
  assert.ok(c.api.readSnapshot('habits', c.api.isHabits));
  c.setTime('2026-10-25T18:00:00Z');
  assert.equal(c.api.readSnapshot('habits', c.api.isHabits), null);
});

test('invalid JSON and invalid habit shape fall back to network loading', () => {
  const c = cache();
  c.values.set('fitpulse_snapshot_v1_habits', '{');
  assert.equal(c.api.readSnapshot('habits', c.api.isHabits), null);
  c.api.writeSnapshot('habits', [{ id: 'bad' }]);
  assert.equal(c.api.readSnapshot('habits', c.api.isHabits), null);
});

test('blocked or full storage does not break the app', () => {
  const c = cache();
  c.storage.setItem = () => { throw Error('Quota'); };
  c.storage.getItem = () => { throw Error('Denied'); };
  assert.doesNotThrow(() => c.api.writeSnapshot('habits', []));
  assert.equal(c.api.readSnapshot('habits', c.api.isHabits), null);
});

test('nutrition snapshots must describe the current day', () => {
  const c = cache();
  c.api.writeSnapshot('dashboard', { date: '2026-10-24', nutrition: {}, profile: {}, workout: {} });
  assert.equal(c.api.readSnapshot('dashboard', c.api.isDashboard), null);
});
