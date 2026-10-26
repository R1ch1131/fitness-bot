import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const source = ts.transpileModule(readFileSync(new URL('./src/useServerConnection.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

async function connection(responses, online = true, visible = true) {
  const state = [], effects = [], timers = new Map(), listeners = new Map(), events = [];
  let sequence = 0, calls = 0;
  const navigator = { onLine: online };
  const document = { visibilityState: visible ? 'visible' : 'hidden', addEventListener: (name, fn) => listeners.set(name, fn), removeEventListener: name => listeners.delete(name) };
  const window = { addEventListener: (name, fn) => listeners.set(name, fn), removeEventListener: name => listeners.delete(name), dispatchEvent: event => events.push(event.type) };
  const context = { exports: {}, Event, AbortController, navigator, document, window,
    setTimeout: (fn, delay) => { const id = ++sequence; timers.set(id, { fn, delay }); return id; },
    clearTimeout: id => timers.delete(id),
    require: () => ({ useState(value) { state[0] = value; return [value, value => { state[0] = value; }]; }, useEffect: fn => effects.push(fn) }),
    fetch: async () => {
      calls++;
      const health = responses.shift();
      if (health === 'error') throw Error('Network');
      return { ok: true, headers: { get: () => health === 'render' ? 'text/html' : 'application/json' }, json: async () => ({ status: 'ok', app: 'FitPulse' }) };
    },
  };
  vm.runInNewContext(source, context);
  context.exports.useServerConnection();
  const cleanup = effects[0]();
  const flush = () => new Promise(setImmediate);
  await flush();
  return { state, events, timers, listeners, navigator, document, cleanup, flush, get calls() { return calls; },
    async retry() { const entry = [...timers.entries()].find(([, value]) => value.delay === 3000 || value.delay === 5000); assert.ok(entry); timers.delete(entry[0]); await entry[1].fn(); await flush(); } };
}

test('Render loading HTML is rejected; recovery triggers exactly one reload event', async () => {
  const c = await connection(['render', 'healthy']);
  assert.equal(c.state[0], 'waking');
  assert.equal(c.events.length, 0);
  await c.retry();
  assert.equal(c.state[0], 'ready');
  assert.deepEqual(c.events, ['fitpulse:server-ready']);
  assert.equal(c.timers.size, 0);
  c.cleanup();
});

test('healthy startup does not duplicate initial dashboard requests', async () => {
  const c = await connection(['healthy']);
  assert.equal(c.state[0], 'ready');
  assert.equal(c.events.length, 0);
  c.cleanup();
});

test('offline startup makes no requests and resumes when connectivity returns', async () => {
  const c = await connection(['healthy'], false);
  assert.equal(c.state[0], 'offline');
  assert.equal(c.calls, 0);
  c.navigator.onLine = true;
  await c.listeners.get('online')();
  await c.flush();
  assert.equal(c.state[0], 'ready');
  assert.equal(c.events.length, 1);
  c.cleanup();
  assert.equal(c.timers.size, 0);
  assert.equal(c.listeners.size, 0);
});

test('hidden app waits for foreground instead of polling in background', async () => {
  const c = await connection(['healthy'], true, false);
  assert.equal(c.calls, 0);
  c.document.visibilityState = 'visible';
  await c.listeners.get('visibilitychange')();
  await c.flush();
  assert.equal(c.state[0], 'ready');
  assert.equal(c.calls, 1);
  c.cleanup();
});
