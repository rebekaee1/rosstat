// Квантильная шкала choropleth карты регионов — одна точка истины для
// живого SVG (RegionsMap) и покадрового GIF-экспорта (regionsMapGif).

export const MAP_SCALE = ['#EFEAE0', '#E3D5B3', '#D2BC7E', '#BE9F4E', '#9C7B22'];
export const MAP_NO_DATA = '#F3F1EC';

/** Строит функцию value → цвет по квантилям текущего среза (года). */
export function buildQuantiles(values, { scale = MAP_SCALE, noData = MAP_NO_DATA } = {}) {
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
    return scale[Math.min(scale.length - 1, Math.floor(q * scale.length))];
  };
}

/** Map slug → цвет для текущего среза valuesBySlug (Map или plain object). */
export function colorsBySlug(valuesBySlug) {
  const out = new Map();
  if (!valuesBySlug) return out;
  const entries = valuesBySlug instanceof Map
    ? [...valuesBySlug.entries()]
    : Object.entries(valuesBySlug);
  const q = buildQuantiles(entries.map(([, v]) => v).filter((v) => v != null));
  for (const [slug, v] of entries) out.set(slug, q(v));
  return out;
}
