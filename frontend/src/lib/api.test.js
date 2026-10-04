// @vitest-environment jsdom
import axios from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';
import api, { isRetrySafe, parseRetryAfter } from './api';

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('API cancellation', () => {
  it('ends an aborted world request without scheduling another attempt', async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    let requestStarted;
    const started = new Promise((resolve) => { requestStarted = resolve; });
    const adapter = vi.fn((config) => new Promise((resolve, reject) => {
      config.signal.addEventListener('abort', () => reject(new axios.CanceledError('Query replaced', config)), { once: true });
      requestStarted();
    }));
    const request = api.get('/world/compare/map-series/gdp-usd', { signal: controller.signal, adapter });
    const rejected = expect(request).rejects.toMatchObject({ code: 'ERR_CANCELED' });

    await started;
    controller.abort();
    await rejected;

    expect(adapter).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('honours cancellation codes even when the error has no Axios cancel marker', async () => {
    vi.useFakeTimers();
    const adapter = vi.fn((config) => Promise.reject(new axios.AxiosError('Query replaced', 'ERR_CANCELED', config)));

    await expect(api.get('/world/compare/snapshot/gdp-usd', { adapter })).rejects.toMatchObject({ code: 'ERR_CANCELED' });

    expect(adapter).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });
});

// Адаптер, который отвечает заданными статусами по очереди (последний повторяется).
function sequenceAdapter(steps) {
  let i = 0;
  return vi.fn((config) => {
    const step = steps[Math.min(i, steps.length - 1)];
    i += 1;
    if (step === 'network') return Promise.reject(new axios.AxiosError('Network Error', 'ERR_NETWORK', config));
    const { status, headers = {} } = typeof step === 'number' ? { status: step } : step;
    const response = { data: { ok: status < 400 }, status, statusText: '', headers, config };
    if (status >= 200 && status < 300) return Promise.resolve(response);
    return Promise.reject(new axios.AxiosError(`HTTP ${status}`, 'ERR_BAD_RESPONSE', config, null, response));
  });
}

describe('retry policy (F11)', () => {
  it('retries an idempotent GET after 503 and returns the later success', async () => {
    vi.useFakeTimers();
    vi.spyOn(Math, 'random').mockReturnValue(0);
    const adapter = sequenceAdapter([503, 200]);
    const request = api.get('/indicators', { adapter });
    await vi.advanceTimersByTimeAsync(2000);
    await expect(request).resolves.toMatchObject({ status: 200 });
    expect(adapter).toHaveBeenCalledTimes(2);
  });

  it('retries a GET after a network miss', async () => {
    vi.useFakeTimers();
    vi.spyOn(Math, 'random').mockReturnValue(0);
    const adapter = sequenceAdapter(['network', 200]);
    const request = api.get('/indicators', { adapter });
    await vi.advanceTimersByTimeAsync(2000);
    await expect(request).resolves.toMatchObject({ status: 200 });
    expect(adapter).toHaveBeenCalledTimes(2);
  });

  it.each(['post', 'put', 'patch', 'delete'])('does not retry %s after 503 or 429', async (method) => {
    vi.useFakeTimers();
    for (const status of [503, 429]) {
      const adapter = sequenceAdapter([status, 200]);
      await expect(api.request({ url: '/feedback', method, adapter })).rejects.toMatchObject({ response: { status } });
      expect(adapter).toHaveBeenCalledTimes(1);
    }
    expect(vi.getTimerCount()).toBe(0);
  });

  it('does not retry a POST after a network miss', async () => {
    vi.useFakeTimers();
    const adapter = sequenceAdapter(['network', 200]);
    await expect(api.post('/export/table', {}, { adapter })).rejects.toMatchObject({ code: 'ERR_NETWORK' });
    expect(adapter).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('retries a mutation only when it is explicitly marked idempotent', async () => {
    vi.useFakeTimers();
    vi.spyOn(Math, 'random').mockReturnValue(0);
    const flagged = sequenceAdapter([503, 200]);
    const first = api.put('/prefs', {}, { adapter: flagged, idempotent: true });
    await vi.advanceTimersByTimeAsync(2000);
    await expect(first).resolves.toMatchObject({ status: 200 });
    expect(flagged).toHaveBeenCalledTimes(2);

    const keyed = sequenceAdapter([503, 200]);
    const second = api.post('/prefs', {}, { adapter: keyed, headers: { 'Idempotency-Key': 'k-1' } });
    await vi.advanceTimersByTimeAsync(2000);
    await expect(second).resolves.toMatchObject({ status: 200 });
    expect(keyed).toHaveBeenCalledTimes(2);
  });

  it('never retries /auth endpoints, even when marked idempotent', async () => {
    vi.useFakeTimers();
    const adapter = sequenceAdapter([429, 200]);
    await expect(api.post('/auth/login', {}, { adapter, idempotent: true })).rejects.toMatchObject({ response: { status: 429 } });
    expect(adapter).toHaveBeenCalledTimes(1);
  });

  it('waits for Retry-After before repeating a GET', async () => {
    vi.useFakeTimers();
    vi.spyOn(Math, 'random').mockReturnValue(0);
    const adapter = sequenceAdapter([{ status: 429, headers: { 'retry-after': '4' } }, 200]);
    const request = api.get('/indicators', { adapter });
    await vi.advanceTimersByTimeAsync(3999);
    expect(adapter).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    await expect(request).resolves.toMatchObject({ status: 200 });
    expect(adapter).toHaveBeenCalledTimes(2);
  });

  it('does not wait out a Retry-After beyond the UI ceiling', async () => {
    vi.useFakeTimers();
    const adapter = sequenceAdapter([{ status: 503, headers: { 'retry-after': '120' } }, 200]);
    await expect(api.get('/indicators', { adapter })).rejects.toMatchObject({ response: { status: 503 } });
    expect(adapter).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('stops after the attempt ceiling (1 request + 3 retries)', async () => {
    vi.useFakeTimers();
    vi.spyOn(Math, 'random').mockReturnValue(0);
    const adapter = sequenceAdapter([503]);
    const request = api.get('/indicators', { adapter });
    const rejected = expect(request).rejects.toMatchObject({ response: { status: 503 } });
    await vi.advanceTimersByTimeAsync(20000);
    await rejected;
    expect(adapter).toHaveBeenCalledTimes(4);
  });

  it('does not retry non-transient statuses', async () => {
    vi.useFakeTimers();
    const adapter = sequenceAdapter([500, 200]);
    await expect(api.get('/indicators', { adapter })).rejects.toMatchObject({ response: { status: 500 } });
    expect(adapter).toHaveBeenCalledTimes(1);
  });
});

describe('retry helpers', () => {
  it('classifies retry safety by method and explicit markers', () => {
    expect(isRetrySafe({ method: 'get' })).toBe(true);
    expect(isRetrySafe({ method: 'HEAD' })).toBe(true);
    expect(isRetrySafe({ method: 'post' })).toBe(false);
    expect(isRetrySafe({ method: 'post', idempotent: true })).toBe(true);
    expect(isRetrySafe({ method: 'delete', headers: { 'idempotency-key': 'x' } })).toBe(true);
    expect(isRetrySafe(undefined)).toBe(false);
  });

  it('parses Retry-After seconds and HTTP dates', () => {
    expect(parseRetryAfter({ 'retry-after': '3' })).toBe(3000);
    expect(parseRetryAfter({ 'Retry-After': '2' })).toBe(2000);
    const now = Date.parse('2026-10-04T10:00:00Z');
    expect(parseRetryAfter({ 'retry-after': 'Sun, 04 Oct 2026 10:00:05 GMT' }, now)).toBe(5000);
    expect(parseRetryAfter({ 'retry-after': 'garbage' })).toBeNull();
    expect(parseRetryAfter({})).toBeNull();
  });
});
