// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { behaviorInit, flush, _resetForTests } from './behavior';
import { saveConsent } from './consent';

vi.mock('web-vitals', () => ({ onLCP: vi.fn(), onCLS: vi.fn(), onFCP: vi.fn(), onTTFB: vi.fn() }));
vi.mock('web-vitals/attribution', () => ({ onINP: vi.fn() }));

const response = (status = 200, retryAfter = null) => ({
  ok: status >= 200 && status < 300, status,
  headers: { get: (key) => key.toLowerCase() === 'retry-after' ? retryAfter : null },
  json: async () => ({ accepted: true }),
});
let fetchMock;
const requests = () => fetchMock.mock.calls.filter(([url]) => url === '/api/v1/analytics/behavior');
const body = (index) => JSON.parse(requests()[index][1].body);
const settle = async () => { for (let i = 0; i < 12; i += 1) await Promise.resolve(); };
const clock = async (ms) => { await vi.advanceTimersByTimeAsync(ms); await settle(); };

beforeEach(() => {
  _resetForTests();
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-09-30T16:53:37Z'));
  localStorage.clear(); sessionStorage.clear();
  document.body.innerHTML = '';
  window.history.replaceState({}, '', '/russia/indicator/fuel-ai95/2022');
  Object.defineProperty(navigator, 'webdriver', { configurable: true, value: false });
  Object.defineProperty(navigator, 'sendBeacon', { configurable: true, value: undefined });
  fetchMock = vi.fn().mockResolvedValue(response());
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('IntersectionObserver', undefined);
  delete window.__feApplyConsent;
});

afterEach(() => {
  _resetForTests();
  vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers();
});

describe('bounded behavior delivery', () => {
  it('retries a rejected first request with exactly the original body and batch ID', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Injected pre-server rejection'));
    behaviorInit(); flush(); await settle();
    const original = requests()[0][1].body;
    expect(body(0).events.map((event) => event.t)).toEqual(expect.arrayContaining(['pageview', 'session_start']));
    expect(sessionStorage.getItem('fe:analytics:session:meta')).toBeNull();
    await clock(1000);
    expect(requests()).toHaveLength(2);
    expect(requests()[1][1].body).toBe(original);
    expect(body(1).batch_id).toBe(body(0).batch_id);
    expect(sessionStorage.getItem('fe:analytics:session:meta')).toBe('1');
  });

  it('keeps the portrait unacknowledged after503 and acknowledges only successful retry', async () => {
    fetchMock.mockResolvedValueOnce(response(503));
    behaviorInit(); flush(); await settle();
    expect(sessionStorage.getItem('fe:analytics:session:meta')).toBeNull();
    await clock(1000);
    expect(requests()).toHaveLength(2);
    expect(requests()[1][1].body).toBe(requests()[0][1].body);
    expect(sessionStorage.getItem('fe:analytics:session:meta')).toBe('1');
  });

  it('does not acknowledge or retry HTTP200 that explicitly rejects intake', async () => {
    fetchMock.mockResolvedValue({ ...response(), json: async () => ({ accepted: false, reason: 'disabled' }) });
    behaviorInit(); flush(); await settle(); await clock(70000);
    expect(requests()).toHaveLength(1);
    expect(sessionStorage.getItem('fe:analytics:session:meta')).toBeNull();
  });

  it('retries a missing acceptance body with the original batch without false acknowledgement', async () => {
    fetchMock.mockResolvedValueOnce({ ...response(), json: async () => { throw new SyntaxError('Injected incomplete response'); } });
    behaviorInit(); flush(); await settle();
    expect(sessionStorage.getItem('fe:analytics:session:meta')).toBeNull();
    await clock(1000);
    expect(requests()).toHaveLength(2);
    expect(requests()[1][1].body).toBe(requests()[0][1].body);
    expect(sessionStorage.getItem('fe:analytics:session:meta')).toBe('1');
  });

  it.each([400, 403, 413])('does not retry permanent HTTP%s', async (status) => {
    fetchMock.mockResolvedValue(response(status));
    behaviorInit(); flush(); await settle(); await clock(70000);
    expect(requests()).toHaveLength(1);
    expect(sessionStorage.getItem('fe:analytics:session:meta')).toBeNull();
  });

  it('honors429 Retry-After rather than immediately repeating', async () => {
    fetchMock.mockResolvedValueOnce(response(429, '3'));
    behaviorInit(); flush(); await settle();
    await clock(2999); expect(requests()).toHaveLength(1);
    await clock(1); expect(requests()).toHaveLength(2);
    expect(body(1).batch_id).toBe(body(0).batch_id);
  });

  it('honors an HTTP-date Retry-After and does not bypass it on pagehide', async () => {
    fetchMock.mockResolvedValueOnce(response(429, new Date(Date.now() + 4000).toUTCString()));
    behaviorInit(); flush(); await settle();
    const originalId = body(0).batch_id;
    await clock(1000);
    window.dispatchEvent(new Event('pagehide')); await settle();
    expect(requests().filter(([, options]) => JSON.parse(options.body).batch_id === originalId)).toHaveLength(1);
    await clock(3000);
    window.dispatchEvent(new Event('pageshow')); await settle();
    expect(requests().filter(([, options]) => JSON.parse(options.body).batch_id === originalId)).toHaveLength(2);
  });

  it('does not retry earlier than a Retry-After beyond the batch lifetime', async () => {
    fetchMock.mockResolvedValue(response(429, '120'));
    behaviorInit(); flush(); await settle(); await clock(70000);
    expect(requests()).toHaveLength(1);
  });

  it('honors server503 Retry-After longer than the local backoff', async () => {
    fetchMock.mockResolvedValueOnce(response(503, '4'));
    behaviorInit(); flush(); await settle();
    await clock(3999); expect(requests()).toHaveLength(1);
    await clock(1); expect(requests()).toHaveLength(2);
    expect(requests()[1][1].body).toBe(requests()[0][1].body);
  });

  it('stops after four failed attempts and does not persist raw batches', async () => {
    fetchMock.mockRejectedValue(new TypeError('Injected network outage'));
    behaviorInit(); flush(); await settle(); await clock(70000);
    expect(requests()).toHaveLength(4);
    expect(new Set(requests().map(([, options]) => JSON.parse(options.body).batch_id)).size).toBe(1);
    for (const store of [localStorage, sessionStorage]) {
      const stored = Array.from({ length: store.length }, (_, i) => store.getItem(store.key(i))).join(' ');
      expect(stored).not.toContain('pageview');
      expect(stored).not.toContain('fuel-ai95');
    }
  });

  it('cancels a scheduled retry when consent is revoked', async () => {
    fetchMock.mockRejectedValue(new TypeError('Injected network rejection'));
    behaviorInit(); flush(); await settle();
    saveConsent({ analytics: false, ads: false });
    await clock(70000); flush(); await settle();
    expect(requests()).toHaveLength(1);
    expect(sessionStorage.getItem('fe:analytics:session:meta')).toBeNull();
  });

  it('never acknowledges a late successful response after revocation', async () => {
    let resolve;
    fetchMock.mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    behaviorInit(); flush();
    saveConsent({ analytics: false, ads: false });
    resolve(response()); await settle(); await clock(2000);
    expect(sessionStorage.getItem('fe:analytics:session:meta')).toBeNull();
    expect(requests()).toHaveLength(1);
  });

  it('does not acknowledge acceptance JSON that finishes after consent revocation', async () => {
    let resolveJson;
    fetchMock.mockResolvedValueOnce({ ...response(), json: () => new Promise((done) => { resolveJson = done; }) });
    behaviorInit(); flush(); await settle();
    saveConsent({ analytics: false, ads: false });
    resolveJson({ accepted: true }); await settle();
    expect(sessionStorage.getItem('fe:analytics:session:meta')).toBeNull();
    expect(requests()).toHaveLength(1);
  });

  it('serializes requests and releases a hanging batch at its lifetime ceiling', async () => {
    fetchMock.mockImplementationOnce(() => new Promise(() => {}));
    behaviorInit(); flush();
    await clock(1000);
    document.body.innerHTML = '<button>Год</button>';
    document.querySelector('button').click(); flush();
    expect(requests()).toHaveLength(1);
    await clock(59000);
    expect(requests()).toHaveLength(2);
    expect(requests()[0][1].signal.aborted).toBe(true);
  });

  it('bounds pending batches while a first request hangs', async () => {
    fetchMock.mockImplementationOnce(() => new Promise(() => {}));
    behaviorInit(); flush();
    for (let i = 1; i <= 5; i += 1) {
      await clock(1000);
      document.body.innerHTML = `<button>Год ${i}</button>`;
      document.querySelector('button').click(); flush();
    }
    expect(requests()).toHaveLength(1);
    await clock(55000);
    expect(requests()).toHaveLength(4);
    const clicks = requests().flatMap(([, options]) => JSON.parse(options.body).events).filter((event) => event.t === 'click');
    expect(clicks.map((event) => event.text)).toEqual(['Год 1', 'Год 2', 'Год 3']);
    expect(requests().every(([, options]) => options.keepalive === false)).toBe(true);
  });

  it('releases expired data and ignores its late successful response', async () => {
    let resolve;
    fetchMock.mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    behaviorInit(); flush(); await clock(60000);
    resolve(response()); await settle();
    expect(sessionStorage.getItem('fe:analytics:session:meta')).toBeNull();
    expect(requests()).toHaveLength(1);
  });

  it('treats a queued pagehide beacon as best effort and does not acknowledge the portrait', async () => {
    const beacon = vi.fn().mockReturnValue(true);
    Object.defineProperty(navigator, 'sendBeacon', { configurable: true, value: beacon });
    behaviorInit();
    window.dispatchEvent(new Event('pagehide')); await settle();
    expect(beacon).toHaveBeenCalledWith('/api/v1/analytics/behavior', expect.any(Blob));
    expect(sessionStorage.getItem('fe:analytics:session:meta')).toBeNull();
  });

  it('does not acknowledge an explicitly rejected keepalive fallback response', async () => {
    fetchMock.mockResolvedValue({ ...response(), json: async () => ({ accepted: false, reason: 'disabled' }) });
    behaviorInit(); window.dispatchEvent(new Event('pagehide')); await settle();
    expect(requests()).toHaveLength(1);
    expect(requests()[0][1].keepalive).toBe(true);
    expect(sessionStorage.getItem('fe:analytics:session:meta')).toBeNull();
  });

  it('bounds all pagehide beacons together below the shared64KiB keepalive budget', async () => {
    window.history.replaceState({}, '', `/russia/indicator/fuel-ai95/2022?test=${'x'.repeat(1600)}`);
    fetchMock.mockImplementationOnce(() => new Promise(() => {}));
    const beacon = vi.fn().mockReturnValue(true);
    Object.defineProperty(navigator, 'sendBeacon', { configurable: true, value: beacon });
    behaviorInit(); flush();
    document.body.innerHTML = '<button>Год</button>';
    for (let i = 0; i < 60; i += 1) document.querySelector('button').click();
    window.dispatchEvent(new Event('pagehide')); await settle();
    const bytes = beacon.mock.calls.reduce((total, [, payload]) => total + payload.size, 0);
    expect(bytes).toBeGreaterThan(0);
    expect(bytes).toBeLessThanOrEqual(48 * 1024);
    expect(beacon.mock.calls.every(([, payload]) => payload.size <= 48 * 1024)).toBe(true);
    window.dispatchEvent(new Event('pagehide'));
    expect(beacon.mock.calls.reduce((total, [, payload]) => total + payload.size, 0)).toBe(bytes);
    expect(sessionStorage.getItem('fe:analytics:session:meta')).toBeNull();
  });

  it('survives throwing beacon/fetch and never sends a pending batch after revocation', async () => {
    Object.defineProperty(navigator, 'sendBeacon', { configurable: true, value: vi.fn(() => { throw new Error('Injected beacon failure'); }) });
    fetchMock.mockImplementation(() => { throw new Error('Injected fetch failure'); });
    behaviorInit();
    expect(() => window.dispatchEvent(new Event('pagehide'))).not.toThrow();
    expect(requests()).toHaveLength(1);
    saveConsent({ analytics: false, ads: false });
    window.dispatchEvent(new Event('pageshow')); await clock(70000);
    expect(requests()).toHaveLength(1);
    expect(sessionStorage.getItem('fe:analytics:session:meta')).toBeNull();
  });
});
