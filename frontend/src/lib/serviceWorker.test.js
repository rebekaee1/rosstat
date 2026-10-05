// Поведение public/sw.js, выполненное в песочнице vm с поддельным окружением service worker.
// Живую регистрацию в Chromium/WebKit проверяла отдельная приёмка (см. docs/backlog.md);
// здесь — инварианты, которые не должны сломаться при правках файла.
import { describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import vm from 'node:vm';

const SOURCE = readFileSync(resolve(import.meta.dirname, '../../public/sw.js'), 'utf8').replaceAll('__SW_VERSION__', 'v-test');

function boot({ config = { sw_enabled: true }, configOk = true, networkUp = true, existingCaches = [] } = {}) {
  const handlers = {};
  const store = new Map(existingCaches.map((n) => [n, new Map()]));
  const calls = { fetch: [], unregister: 0, notifications: [], opened: [], focused: [] };
  const cacheApi = {
    keys: async () => [...store.keys()],
    delete: async (n) => store.delete(n),
    open: async (n) => {
      if (!store.has(n)) store.set(n, new Map());
      const bucket = store.get(n);
      return { add: async (req) => { bucket.set(new URL(req.url || req, 'https://x.test').pathname, 'cached'); }, put: () => { throw new Error('put запрещён'); } };
    },
    match: async (url, opts) => {
      const bucket = opts?.cacheName ? store.get(opts.cacheName) : [...store.values()][0];
      return bucket && bucket.has(url) ? { offline: true, url } : undefined;
    },
  };
  const self = {
    location: { origin: 'https://forecasteconomy.com' },
    addEventListener: (type, fn) => { handlers[type] = fn; },
    skipWaiting: vi.fn(async () => {}),
    clients: {
      claim: vi.fn(async () => {}),
      matchAll: vi.fn(async () => []),
      openWindow: vi.fn(async (u) => { calls.opened.push(u); }),
    },
    registration: {
      unregister: vi.fn(async () => { calls.unregister += 1; }),
      showNotification: vi.fn(async (title, options) => { calls.notifications.push({ title, options }); }),
    },
  };
  const sandbox = {
    self, caches: cacheApi, console, Date, URL, JSON, Promise,
    Request: class { constructor(url, init) { this.url = url; this.init = init; } },
    Response: class { constructor(body, init) { this.body = body; this.status = init?.status; } },
    fetch: vi.fn(async (input) => {
      const url = typeof input === 'string' ? input : input.url;
      calls.fetch.push(url);
      if (!networkUp && !url.includes('/api/v1/pwa/config')) throw new TypeError('offline');
      if (url.includes('/api/v1/pwa/config')) {
        if (!configOk) return { ok: false, json: async () => ({}) };
        return { ok: true, json: async () => config };
      }
      return { ok: true, live: true, url };
    }),
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(SOURCE, sandbox);
  const waits = [];
  const fire = (type, event) => { handlers[type]({ waitUntil: (p) => waits.push(p), ...event }); };
  return { self, store, calls, fire, waits, sandbox, settle: () => Promise.all(waits) };
}

const nav = (url = 'https://forecasteconomy.com/russia') => ({ mode: 'navigate', url });

describe('установка и активация', () => {
  it('на установке кладёт в кэш только офлайн-страницу и иконку, затем skipWaiting', async () => {
    const sw = boot();
    sw.fire('install', {});
    await sw.settle();
    expect([...sw.store.keys()]).toEqual(['fe-offline-v-test']);
    expect([...sw.store.get('fe-offline-v-test').keys()].sort()).toEqual(['/icons/icon-192.png', '/offline.html']);
    expect(sw.self.skipWaiting).toHaveBeenCalled();
  });

  it('при активации чистит старые версии fe-*, чужие кэши не трогает, забирает клиентов', async () => {
    const sw = boot({ existingCaches: ['fe-offline-old', 'fe-offline-v-test', 'workbox-precache'] });
    sw.fire('activate', {});
    await sw.settle();
    expect([...sw.store.keys()].sort()).toEqual(['fe-offline-v-test', 'workbox-precache']);
    expect(sw.self.clients.claim).toHaveBeenCalled();
    expect(sw.calls.unregister).toBe(0);
  });
});

describe('аварийный выход (kill-switch)', () => {
  it('sw_enabled=false при активации: все кэши удалены, регистрация снята', async () => {
    const sw = boot({ config: { sw_enabled: false }, existingCaches: ['fe-offline-v-test', 'other'] });
    sw.fire('activate', {});
    await sw.settle();
    expect(sw.store.size).toBe(0);
    expect(sw.calls.unregister).toBe(1);
  });

  it('конфиг недоступен или сеть пропала: себя не выключает', async () => {
    const down = boot({ configOk: false, existingCaches: ['fe-offline-v-test'] });
    down.fire('activate', {});
    await down.settle();
    expect(down.calls.unregister).toBe(0);
    expect(down.store.has('fe-offline-v-test')).toBe(true);
  });

  it('при навигации проверка не чаще раза в 30 минут', async () => {
    const sw = boot();
    sw.fire('activate', {});
    await sw.settle();
    const checks = () => sw.calls.fetch.filter((u) => u.includes('/pwa/config')).length;
    expect(checks()).toBe(1);
    sw.fire('fetch', { request: nav(), respondWith: () => {} });
    sw.fire('fetch', { request: nav(), respondWith: () => {} });
    await sw.settle();
    expect(checks()).toBe(1);
  });
});

describe('fetch: данные не кэшируются, устаревшего не покажет', () => {
  it('не-навигации (API, ассеты, картинки) не перехватывает вообще', () => {
    const sw = boot();
    const respondWith = vi.fn();
    for (const url of ['https://forecasteconomy.com/api/v1/indicators/cpi', '/assets/app.js', '/og/x.png']) {
      sw.fire('fetch', { request: { mode: 'cors', url }, respondWith });
    }
    expect(respondWith).not.toHaveBeenCalled();
  });

  it('навигация онлайн: отдаёт живой ответ сети, не кэш', async () => {
    const sw = boot({ existingCaches: ['fe-offline-v-test'] });
    let answer;
    sw.fire('fetch', { request: nav(), respondWith: (p) => { answer = p; } });
    expect((await answer).live).toBe(true);
  });

  it('навигация без сети: только офлайн-страница', async () => {
    const sw = boot({ networkUp: false });
    sw.fire('install', {});
    await sw.settle();
    let answer;
    sw.fire('fetch', { request: nav('https://forecasteconomy.com/russia/indicator/cpi'), respondWith: (p) => { answer = p; } });
    expect(await answer).toEqual({ offline: true, url: '/offline.html' });
  });

  it('нет и офлайн-страницы: честный 503 текстом, а не пустой экран', async () => {
    const sw = boot({ networkUp: false });
    let answer;
    sw.fire('fetch', { request: nav(), respondWith: (p) => { answer = p; } });
    expect((await answer).status).toBe(503);
  });
});

describe('push-заготовка', () => {
  it('push показывает уведомление с безопасными полями', async () => {
    const sw = boot();
    sw.fire('push', { data: { json: () => ({ title: 'T'.repeat(300), body: 'B'.repeat(900), url: '/russia', tag: 'x'.repeat(200) }) } });
    await sw.settle();
    const { title, options } = sw.calls.notifications[0];
    expect(title.length).toBe(120);
    expect(options.body.length).toBe(300);
    expect(options.tag.length).toBe(64);
    expect(options.data.url).toBe('/russia');
  });

  it('пустой или битый payload не роняет обработчик', async () => {
    const sw = boot();
    sw.fire('push', { data: null });
    sw.fire('push', { data: { json: () => { throw new Error('bad'); } } });
    await sw.settle();
    expect(sw.calls.notifications.map((n) => n.title)).toEqual(['Forecast Economy', 'Forecast Economy']);
  });

  it('клик открывает только страницы своего origin', async () => {
    const sw = boot();
    const click = (url) => { const closed = vi.fn(); sw.fire('notificationclick', { notification: { data: { url }, close: closed } }); return closed; };
    const closed = click('https://evil.example/phish');
    click('/russia/indicator/cpi?x=1#a');
    click('//evil.example/x');
    await sw.settle();
    expect(closed).toHaveBeenCalled();
    expect(sw.calls.opened).toEqual(['/', '/russia/indicator/cpi?x=1#a', '/']);
  });
});
