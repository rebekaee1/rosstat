import { useQuery } from '@tanstack/react-query';
import { tickerLaneFor } from './tickerLane';
import { useLocale } from '../i18n';

/** Снимок живой ленты курсов (один запрос на всю страницу: ключ общий у ленты и у страниц, которым нужна та же котировка). */
export async function fetchLiveTicker(lane) {
  const r = await fetch(`/api/v1/ticker/live?lane=${encodeURIComponent(lane)}`, {
    cache: 'no-store',
    credentials: 'same-origin',
  });
  if (!r.ok) {
    const err = new Error(`Live ticker: HTTP ${r.status}`);
    err.status = r.status;
    if (r.status === 429) {
      const raw = Number.parseInt(r.headers.get('retry-after') || '60', 10);
      const sec = Number.isFinite(raw) ? raw : 60;
      err.retryAfterMs = Math.min(Math.max(sec, 1), 120) * 1000;
    }
    throw err;
  }
  return r.json();
}

/**
 * Круг 13, V4 (Биткоин): котировка кода из той же живой ленты, что стоит над шапкой сайта. Нужна странице показателя, чтобы число и
 * изменение в шапке брались от той же базы, что и лента (Binance: цена и изменение к цене 24 часа назад). `code = null` — не запрашивать.
 * Ключ запроса общий с лентой: отдельных обращений к серверу страница не добавляет.
 */
export function useLiveQuote(code) {
  const { locale } = useLocale();
  const lane = tickerLaneFor(locale);
  const { data } = useQuery({
    queryKey: ['ticker', 'live', lane],
    queryFn: () => fetchLiveTicker(lane),
    enabled: Boolean(code),
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 4000,
  });
  if (!code) return null;
  return (data?.snapshots || []).find((s) => s.code === code) || null;
}

/** Снимок пригоден для шапки: внутридневная биржевая котировка, свежая, с ценой и изменением за 24 часа. */
export function isFreshIntraday(snapshot) {
  if (!snapshot || !snapshot.market_open || snapshot.stale === true) return false;
  if (!(Number(snapshot.price) > 0) || snapshot.change_pct == null || !Number.isFinite(Number(snapshot.change_pct))) return false;
  const fetched = snapshot.fetched_at ? Date.parse(snapshot.fetched_at) : NaN;
  return Number.isFinite(fetched) && Date.now() - fetched < 15 * 60 * 1000;
}
