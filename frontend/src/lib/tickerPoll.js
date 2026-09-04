export const POLL_INTERVAL_MS = 4000;
export const TICKER_429_PAUSE_MS = 60_000;

/** Пауза опроса: 429 — окно лимита; прочая ошибка — реже, без шторма ретраев. */
export function tickerRefetchInterval(query) {
  const err = query?.state?.error;
  if (err?.status === 429) return err.retryAfterMs || TICKER_429_PAUSE_MS;
  if (query?.state?.status === 'error') return POLL_INTERVAL_MS * 4;
  return POLL_INTERVAL_MS;
}
