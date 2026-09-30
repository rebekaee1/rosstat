import axios from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';
import api from './api';

afterEach(() => {
  vi.useRealTimers();
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
