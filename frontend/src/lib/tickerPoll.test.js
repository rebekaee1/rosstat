import { describe, expect, it } from 'vitest';
import { POLL_INTERVAL_MS, TICKER_429_PAUSE_MS, tickerRefetchInterval } from './tickerPoll';

describe('tickerRefetchInterval', () => {
  it('успех — штатный интервал', () => {
    expect(tickerRefetchInterval({ state: { status: 'success' } })).toBe(POLL_INTERVAL_MS);
  });

  it('429 — пауза на окно лимита', () => {
    const err = { status: 429, retryAfterMs: 45_000 };
    expect(tickerRefetchInterval({ state: { status: 'error', error: err } })).toBe(45_000);
    expect(tickerRefetchInterval({
      state: { status: 'error', error: { status: 429 } },
    })).toBe(TICKER_429_PAUSE_MS);
  });

  it('прочая ошибка — реже, без шторма', () => {
    expect(tickerRefetchInterval({
      state: { status: 'error', error: { status: 500 } },
    })).toBe(POLL_INTERVAL_MS * 4);
  });
});
