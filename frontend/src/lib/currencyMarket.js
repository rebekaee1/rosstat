// Биржевые котировки для раздела «Курсы валют»: доллар на рынке рядом с курсом ЦБ, золото, нефть, биткоин.
// Берутся из той же живой ленты, что и бегущая строка сверху; без ответа сервера блоки просто не рисуются.
import { useQuery } from '@tanstack/react-query';

export const MARKET_BOARD_CODES = ['gold-rub-live', 'brent', 'btc-usd'];

async function fetchMarket() {
  try {
    const response = await fetch('/api/v1/ticker/live?lane=russia', { cache: 'no-store', credentials: 'same-origin' });
    if (!response.ok) return { snapshots: [] };
    const body = await response.json();
    return { snapshots: Array.isArray(body?.snapshots) ? body.snapshots : [] };
  } catch {
    return { snapshots: [] };
  }
}

/**
 * Снимки ленты по коду: { 'usd-rub-live': { price, change_pct, as_of_day, age_days, stale, ... } } и признак, что ответа ещё нет
 * (по нему страница резервирует место под плитку «Рынок», чтобы конвертер не сдвигался).
 */
export function useMarketState() {
  const query = useQuery({
    queryKey: ['z8', 'market', 'russia'],
    queryFn: fetchMarket,
    staleTime: 30_000,
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: false,
    retry: false,
  });
  const map = {};
  for (const snap of query.data?.snapshots || []) {
    if (snap?.code && Number(snap.price) > 0) map[snap.code] = snap;
  }
  return { market: map, pending: query.isPending };
}

/** Снимки ленты по коду (без признака загрузки). */
export function useMarketSnapshots() {
  return useMarketState().market;
}

/** Серия для годового графика: по возрастанию даты, без мусора, не старше года от последней точки. */
export function yearSeries(rows, { invert = false, days = 366 } = {}) {
  const points = (rows || [])
    .map((row) => ({ date: String(row?.date || '').slice(0, 10), value: Number(row?.value) }))
    .filter((p) => p.date && Number.isFinite(p.value) && p.value > 0)
    .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
  if (!points.length) return [];
  const last = Date.parse(`${points[points.length - 1].date}T12:00:00Z`);
  const from = last - days * 86_400_000;
  const trimmed = points.filter((p) => Date.parse(`${p.date}T12:00:00Z`) >= from);
  return trimmed.map((p) => ({ date: p.date, value: invert ? 1 / p.value : p.value }));
}

/** Какой ряд рисовать для пары конвертера: прямой, обратный (значения переворачиваются) или ближайший. */
export function chartPairFor(edges, from, to) {
  const direct = edges.find((edge) => edge.from === from && edge.to === to);
  if (direct) return { code: direct.code, base: from, quote: to, invert: false };
  const reverse = edges.find((edge) => edge.from === to && edge.to === from);
  if (reverse) return { code: reverse.code, base: from, quote: to, invert: true };
  const near = edges.find((edge) => edge.from === from || edge.to === from) || edges[0];
  return near ? { code: near.code, base: near.from, quote: near.to, invert: false } : null;
}
