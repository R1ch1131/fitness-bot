import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

function worker({ failAsset = false } = {}) {
  const handlers = {}, versions = new Map(), requests = [];
  let skipped = false;
  const toKey = key => typeof key === 'string' ? new URL(key, 'https://fit.test').href : key.url;
  const caches = {
    async open(name) {
      if (!versions.has(name)) versions.set(name, new Map());
      const entries = versions.get(name);
      return { put: async (key, value) => entries.set(toKey(key), value.clone()), match: async key => entries.get(toKey(key))?.clone() };
    },
    async keys() { return [...versions.keys()]; },
    async delete(name) { return versions.delete(name); },
    async match(key) {
      for (const entries of versions.values()) if (entries.has(toKey(key))) return entries.get(toKey(key)).clone();
    },
  };
  class AppRequest extends Request { constructor(path, options) { super(new URL(path, 'https://fit.test'), options); } }
  const fetch = async request => {
    requests.push(typeof request === 'string' ? request : request.url);
    if (failAsset) return new Response('APPLICATION LOADING', { headers: { 'Content-Type': 'text/html' } });
    return new Response('app asset', { headers: { 'Content-Type': 'application/javascript' } });
  };
  const source = readFileSync(new URL('./public/sw.js', import.meta.url), 'utf8')
    .replace('"__BUILD_VERSION__"', '"test-build"')
    .replace('"__BUILD_HTML__"', JSON.stringify('<!doctype html><div id="root">FitPulse</div>'))
    .replace('["__BUILD_ASSETS__"]', '["/assets/app.js"]');
  vm.runInNewContext(source, { URL, Request: AppRequest, Response, caches, fetch, self: {
    location: { origin: 'https://fit.test' }, clients: { claim: async () => {} },
    skipWaiting: async () => { skipped = true; }, addEventListener: (name, callback) => { handlers[name] = callback; },
  } });
  return { handlers, versions, requests, get skipped() { return skipped; } };
}

async function install(w) {
  let ready;
  w.handlers.install({ waitUntil: value => { ready = value; } });
  await ready;
}

test('installed app opens cached shell instead of contacting sleeping Render', async () => {
  const w = worker();
  await install(w);
  const before = w.requests.length;
  let response;
  w.handlers.fetch({ request: { url: 'https://fit.test/?tab=chat', method: 'GET', mode: 'navigate' }, respondWith: value => { response = value; } });
  assert.match(await (await response).text(), /FitPulse/);
  assert.equal(w.requests.length, before);
  assert.equal(w.skipped, true);
});

test('Render HTML masquerading as an asset rejects installation and deletes incomplete cache', async () => {
  const w = worker({ failAsset: true });
  await assert.rejects(install(w), /wake-up page/);
  assert.equal(w.skipped, false);
  assert.equal(w.versions.size, 0);
});

test('API requests, health and mutations are never intercepted or cached', async () => {
  const w = worker();
  await install(w);
  for (const [url, method] of [['/api/dashboard', 'GET'], ['/health', 'GET'], ['/api/habits/toggle', 'POST']]) {
    let intercepted = false;
    w.handlers.fetch({ request: { url: 'https://fit.test' + url, method, mode: 'cors' }, respondWith: () => { intercepted = true; } });
    assert.equal(intercepted, false);
  }
});

test('assets continue loading from cache without server availability', async () => {
  const w = worker();
  await install(w);
  const before = w.requests.length;
  let result;
  w.handlers.fetch({ request: new Request('https://fit.test/assets/app.js'), respondWith: value => { result = value; } });
  assert.equal(await (await result).text(), 'app asset');
  assert.equal(w.requests.length, before);
});
