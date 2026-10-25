import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const source = ts.transpileModule(readFileSync(new URL('./src/usePushNotifications.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

function client({ installed = true, permission = 'default', failSave = false } = {}) {
  const state = [], calls = [];
  let idx = 0;
  const sub = { endpoint: 'https://web.push.apple.com/token', options: {}, toJSON: () => ({ endpoint: 'token', keys: {} }) };
  const Notification = { permission, requestPermission: async () => { calls.push('permission'); return 'granted'; } };
  const reg = { pushManager: { getSubscription: async () => null, subscribe: async () => { calls.push('subscribe'); return sub; } } };
  const context = {
    exports: {}, Uint8Array, Array, Error, Promise, setTimeout, clearTimeout, atob, AbortSignal,
    require: () => ({ useEffect() {}, useState: value => {
      const i = idx++;
      state[i] = typeof value === 'function' ? value() : value;
      return [state[i], value => { state[i] = value; }];
    } }),
    Notification,
    window: { isSecureContext: true, matchMedia: () => ({ matches: installed }), Notification, PushManager: {} },
    navigator: { userAgent: 'iPhone', platform: 'iPhone', maxTouchPoints: 1, serviceWorker: {
      register: async () => { calls.push('register'); return reg; }, ready: Promise.resolve(reg),
    } },
    fetch: async path => {
      calls.push(path);
      return { ok: !(failSave && path.endsWith('/subscribe')), json: async () => path.endsWith('vapid_key') ? { public_key: 'AQID' } : failSave ? { detail: 'Save failed' } : { status: 'ok' } };
    },
  };
  vm.runInNewContext(source, context);
  return { hook: context.exports.usePushNotifications(), state, calls };
}

test('iPhone outside Home Screen explains installation without prompting', async () => {
  const c = client({ installed: false });
  await c.hook.enable();
  assert.match(c.state[3], /Домой/);
  assert.equal(c.calls.length, 0);
});

test('iOS permission is requested before service worker/network work', async () => {
  const c = client();
  await c.hook.enable();
  assert.equal(c.calls[0], 'permission');
  assert.equal(c.state[0], true);
  assert.ok(c.calls.includes('/api/notifications/subscribe'));
});

test('server subscription failure cannot display connected state', async () => {
  const c = client({ failSave: true });
  await c.hook.enable();
  assert.equal(c.state[0], false);
  assert.equal(c.state[2], 'Save failed');
});

test('denied permission explains Settings without repeated permission prompts', async () => {
  const c = client({ permission: 'denied' });
  await c.hook.enable();
  assert.match(c.state[3], /настройках/);
  assert.equal(c.calls.length, 0);
});
