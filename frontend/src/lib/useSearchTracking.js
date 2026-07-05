import { useEffect } from 'react';
import { track, events } from './track';

/**
 * Спрос-аналитика ЛЮБОГО внутреннего поиска сайта (директива владельца
 * 2026-07-05: «собирать всю информацию, которую люди пишут в наш поисковик —
 * любой из поисков»). Единый канал: событие `search_query` с параметрами
 * {q, results, context} — тот же, что у глобального ⌘K-поиска, поэтому все
 * поля автоматически попадают в «Пульс», Telegram-дайджест и BI-дашборд без
 * дополнительной проводки. Запрос с results=0 — карта пробелов каталога.
 *
 * Debounce отсекает сырые keystroke'и: фиксируем то, что человек реально
 * искал, а не каждую букву.
 *
 * context — короткий идентификатор поля: 'global' | 'compare-macro' |
 * 'compare-region' | 'compare-region-indicator' | 'regions-list' |
 * 'map-metric' | 'region-profile' | 'table'.
 */
export default function useSearchTracking(context, query, resultsCount, { minLen = 2, delay = 900 } = {}) {
  useEffect(() => {
    const q = (query || '').trim();
    if (q.length < minLen) return undefined;
    const t = setTimeout(() => {
      track(events.SEARCH_QUERY, { q: q.slice(0, 60), results: resultsCount, context });
    }, delay);
    return () => clearTimeout(t);
  }, [context, query, resultsCount, minLen, delay]);
}
