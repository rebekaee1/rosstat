/**
 * Топ-10 и низ-10 регионов по значению на карте (круг 11, F). Чистые функции: считают по уже загруженным значениям года,
 * сервер ничего не досчитывает. Если рейтинг по смыслу «чем меньше, тем лучше» (безработица, бедность), лучшие идут первыми
 * по возрастанию; у величин без оценки (население) первыми стоят наибольшие значения.
 */

/** @returns {Array<{ slug: string, name: string, value: number }>} все регионы со значением, лучшие первыми */
export function rankRegions(valuesBySlug, namesBySlug = {}, { direction = 'desc' } = {}) {
  if (!valuesBySlug) return [];
  const rows = [];
  for (const [slug, raw] of valuesBySlug instanceof Map ? valuesBySlug : Object.entries(valuesBySlug)) {
    const value = Number(raw);
    if (raw == null || raw === '' || !Number.isFinite(value)) continue;
    rows.push({ slug, name: namesBySlug[slug] || slug, value });
  }
  rows.sort((a, b) => (direction === 'asc' ? a.value - b.value : b.value - a.value));
  return rows;
}

/**
 * @param {Array<{ slug: string, name: string, value: number }>} ranked результат rankRegions
 * @returns {{ top: Array, bottom: Array, total: number }} top — первые `limit` с местами; bottom — последние `limit`, самый
 *   последний первым; при малом числе регионов списки не пересекаются
 */
export function leadersAndTrailers(ranked, limit = 10) {
  const total = ranked.length;
  const n = Math.min(limit, Math.floor(total / 2));
  const top = ranked.slice(0, n).map((row, i) => ({ ...row, place: i + 1 }));
  const bottom = ranked.slice(total - n).map((row, i) => ({ ...row, place: total - n + i + 1 })).reverse();
  return { top, bottom, total };
}

/** Направление порядка по ответу heatmap: «меньше — лучше» даёт возрастание, иначе убывание. */
export function leadersDirection(heatmap) {
  if (heatmap?.rank_as_achievement && heatmap?.default_sort === 'asc') return 'asc';
  return 'desc';
}
