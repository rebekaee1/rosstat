// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { behaviorInit, flush, _resetForTests } from './behavior';

vi.mock('web-vitals', () => ({ onLCP: vi.fn(), onCLS: vi.fn(), onFCP: vi.fn(), onTTFB: vi.fn() }));
vi.mock('web-vitals/attribution', () => ({ onINP: vi.fn() }));

const ok = () => ({ ok: true, status: 200, headers: { get: () => null }, json: async () => ({ accepted: true }) });
const settle = async () => { for (let i = 0; i < 12; i += 1) await Promise.resolve(); };

// Минимальный XHR: send() сразу «завершается» заданным статусом и шлёт loadend.
function makeFakeXhr(status) {
  return class FakeXhr {
    constructor() { this.status = 0; this._l = []; }
    open(method, url) { this.openedWith = [method, url]; }
    addEventListener(type, fn) { if (type === 'loadend') this._l.push(fn); }
    send() { this.status = status; queueMicrotask(() => this._l.forEach((fn) => fn())); }
  };
}

let fetchMock;
const sentEvents = () => fetchMock.mock.calls
  .filter(([url]) => url === '/api/v1/analytics/behavior')
  .flatMap(([, init]) => JSON.parse(init.body).events);

beforeEach(() => {
  _resetForTests();
  localStorage.clear(); sessionStorage.clear();
  document.body.innerHTML = '';
  window.history.replaceState({}, '', '/russia/indicator/fuel-ai95/2022');
  Object.defineProperty(navigator, 'webdriver', { configurable: true, value: false });
  Object.defineProperty(navigator, 'sendBeacon', { configurable: true, value: undefined });
  fetchMock = vi.fn().mockResolvedValue(ok());
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('IntersectionObserver', undefined);
});

afterEach(() => {
  _resetForTests();
  vi.restoreAllMocks(); vi.unstubAllGlobals();
});

describe('api_timing covers Axios XHR', () => {
  it('samples every fifth /api/ XHR, keeps the request flow and restores the prototype', async () => {
    const Fake = makeFakeXhr(503);
    const origOpen = Fake.prototype.open;
    const origSend = Fake.prototype.send;
    vi.stubGlobal('XMLHttpRequest', Fake);
    window.XMLHttpRequest = Fake;
    behaviorInit();
    expect(Fake.prototype.open).not.toBe(origOpen);

    for (let i = 0; i < 5; i += 1) {
      const xhr = new Fake();
      xhr.open('GET', `/api/v1/indicators/${i}?x=1`);
      xhr.send();
      expect(xhr.openedWith[1]).toBe(`/api/v1/indicators/${i}?x=1`); // оригинальный open вызван
    }
    // Аналитика и не-API запросы не считаются.
    const noise = new Fake(); noise.open('POST', '/api/v1/analytics/behavior'); noise.send();
    const other = new Fake(); other.open('GET', '/static/app.js'); other.send();
    await settle();
    flush(); await settle();

    const timings = sentEvents().filter((event) => event.t === 'api_timing');
    expect(timings).toHaveLength(1);
    expect(timings[0]).toMatchObject({ u: '/api/v1/indicators/4', st: 503, ok: 0 });

    _resetForTests();
    expect(Fake.prototype.open).toBe(origOpen);
    expect(Fake.prototype.send).toBe(origSend);
  });
});
