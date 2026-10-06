// Квантильная шкала choropleth карты регионов — одна точка истины для
// живого SVG (RegionsMap) и покадрового GIF-экспорта (regionsMapGif).

// Девять ступеней вместо пяти: у соседей с близкими значениями цвета различимы. Шкала холодная, как у карты мира и планеты
// (круг 6: прежняя золотая снята по принципу «не слишком жёлтый»): лёд → средний синий → глубокий синий.
const MAP_SCALE_STOPS = ['#C9D7EA', '#7C9AC9', '#1E3A6E'];

function mixHex(a, b, f) {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  const mixed = pa.map((v, i) => Math.round(v + (pb[i] - v) * f));
  return `#${mixed.map((v) => v.toString(16).padStart(2, '0')).join('').toUpperCase()}`;
}

function buildScale(stops, steps) {
  return Array.from({ length: steps }, (_, i) => {
    const pos = (i / (steps - 1)) * (stops.length - 1);
    const lo = Math.floor(pos);
    const hi = Math.min(stops.length - 1, lo + 1);
    return mixHex(stops[lo], stops[hi], pos - lo);
  });
}

export const MAP_SCALE = buildScale(MAP_SCALE_STOPS, 9);
// Нет данных: матовое стекло (светлый иней), не серый прочерк.
export const MAP_NO_DATA = '#EEF2F6';

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
