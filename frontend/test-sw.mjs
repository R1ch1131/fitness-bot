import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

function worker(windows = []) {
  const handlers = {};
  const notifications = [];
  const opened = [];
  const context = { URL, self: {
    location: { origin: 'https://fit.test' },
    addEventListener: (name, fn) => { handlers[name] = fn; },
    registration: { showNotification: async (...args) => notifications.push(args) },
    clients: { matchAll: async () => windows, openWindow: async url => opened.push(url) },
  } };
  vm.runInNewContext(readFileSync(new URL('./public/sw.js', import.meta.url), 'utf8'), context);
  return { handlers, notifications, opened };
}

test('push displays a notification for empty, invalid JSON, and null payloads', async () => {
  for (const data of [undefined, { json: () => null }, { json() { throw Error(); }, text: () => 'text' }]) {
    const w = worker();
    let done;
    w.handlers.push({ data, waitUntil: p => { done = p; } });
    await done;
    assert.equal(w.notifications.length, 1);
  }
});

test('cold notification click opens its requested tab', async () => {
  const w = worker();
  let done;
  w.handlers.notificationclick({ notification: { close() {}, data: { url: '/?tab=chat' } }, waitUntil: p => { done = p; } });
  await done;
  assert.equal(w.opened[0], 'https://fit.test/?tab=chat');
});

test('existing window navigates to weekly instead of always opening chat', async () => {
  let destination, focused = false;
  const w = worker([{ url: 'https://fit.test/', navigate: async url => { destination = url; return { focus: async () => { focused = true; } }; } }]);
  let done;
  w.handlers.notificationclick({ notification: { close() {}, data: { url: '/?tab=weekly' } }, waitUntil: p => { done = p; } });
  await done;
  assert.equal(destination, 'https://fit.test/?tab=weekly');
  assert.equal(focused, true);
  assert.equal(w.opened.length, 0);
});

test('notification cannot navigate outside the app origin', async () => {
  const w = worker();
  let done;
  w.handlers.notificationclick({ notification: { close() {}, data: { url: 'https://evil.test/' } }, waitUntil: p => { done = p; } });
  await done;
  assert.equal(w.opened[0], 'https://fit.test/');
});
