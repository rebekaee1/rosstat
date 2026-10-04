import { resolveDateFormat } from './format';
import { periodPhrase } from './periodPhrase';

/** Подпись периода значения для плитки каталога («на 3 октября 2026», «за август 2026») или undefined. */
export function tileDatePhrase(indicator, t, locale) {
  if (!indicator) return undefined;
  const dateFmt = resolveDateFormat({ frequency: indicator.frequency });
  return periodPhrase(t, indicator.current_date, dateFmt, locale);
}

/**
 * Самая частая подпись периода среди плиток списка — её выносим в одну строку над списком,
 * а на плитках не повторяем. Нужны хотя бы три плитки с ней и половина списка: иначе общей даты нет.
 */
export function commonTilePhrase(indicators, t, locale) {
  const list = (indicators || []).filter((item) => item?.is_active);
  if (list.length < 3) return null;
  const counts = new Map();
  for (const item of list) {
    const phrase = tileDatePhrase(item, t, locale);
    if (phrase) counts.set(phrase, (counts.get(phrase) || 0) + 1);
  }
  let best = null;
  let bestCount = 0;
  for (const [phrase, count] of counts) {
    if (count > bestCount) { best = phrase; bestCount = count; }
  }
  return best && bestCount >= 3 && bestCount * 2 >= list.length ? best : null;
}
