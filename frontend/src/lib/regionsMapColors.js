// Квантильная шкала choropleth карты регионов — одна точка истины для
// живого SVG (RegionsMap) и покадрового GIF-экспорта (regionsMapGif).

export const MAP_SCALE = ['#EFEAE0', '#E3D5B3', '#D2BC7E', '#BE9F4E', '#9C7B22'];
export const MAP_NO_DATA = '#F3F1EC';

/**
 * Строит функцию value → цвет по квантилям текущего среза (года).
 * `direction` связывает шкалу с порядком сортировки: при 'asc' насыщенный
 * край палитры достаётся малым значениям (лидер нового порядка — акцентный),
 * при 'desc'/null — крупным. Переключение порядка переворачивает раскраску.
 */
export function buildQuantiles(values, { scale = MAP_SCALE, noData = MAP_NO_DATA, direction = null } = {}) {
  const sorted = [...values].sort((a, b) => a - b);
  if (!sorted.length) return () => noData;
  return (v) => {
    if (v == null) return noData;
    let lo = 0;
    let hi = sorted.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (sorted[mid] < v) lo = mid + 1;
      else hi = mid;
    }
    const q = lo / Math.max(sorted.length - 1, 1);
    const index = Math.min(scale.length - 1, Math.floor(q * scale.length));
    return direction === 'asc'
      ? scale[scale.length - 1 - index]
      : scale[index];
  };
}

function entriesOf(valuesBySlug) {
  if (!valuesBySlug) return [];
  return valuesBySlug instanceof Map
    ? [...valuesBySlug.entries()]
    : Object.entries(valuesBySlug);
}

/** Map slug → цвет для текущего среза valuesBySlug (Map или plain object). */
export function colorsBySlug(valuesBySlug, { direction = null } = {}) {
  const out = new Map();
  const entries = entriesOf(valuesBySlug);
  if (!entries.length) return out;
  const q = buildQuantiles(entries.map(([, v]) => v).filter((v) => v != null), { direction });
  for (const [slug, v] of entries) out.set(slug, q(v));
  return out;
}

/** Min/max числовых значений среза — для легенды GIF и live-карты. */
export function valueExtent(valuesBySlug) {
  const nums = entriesOf(valuesBySlug)
    .map(([, v]) => v)
    .filter((v) => v != null && Number.isFinite(Number(v)))
    .map(Number);
  if (!nums.length) return null;
  return { min: Math.min(...nums), max: Math.max(...nums) };
}
