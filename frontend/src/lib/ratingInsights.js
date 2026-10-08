/**
 * Производные величины рейтинга стран из уже загруженного map-series: изменение к прошлому году,
 * мини-график страны, сдвиг мест за несколько лет. Сервер ничего не считает заново: все значения
 * берутся из `values_by_year[год][код страны]`.
 */

function numberOrNull(item) {
  const value = item?.value;
  if (value == null || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

/** Значение страны в году или null. */
export function valueAt(valuesByYear, year, code) {
  return numberOrNull(valuesByYear?.[String(year)]?.[code]);
}

/**
 * Изменение к предыдущему году, за который у страны есть значение (не дальше 3 лет назад).
 * `pct` — относительное изменение, `abs` — разность; pct null, когда база нулевая или отрицательная.
 */
export function yearOverYear(valuesByYear, years, activeYear, code) {
  const now = valueAt(valuesByYear, activeYear, code);
  if (now == null) return null;
  const list = [...(years || [])].map(Number).filter((y) => y < Number(activeYear)).sort((a, b) => b - a);
  for (const year of list) {
    if (Number(activeYear) - year > 3) break;
    const before = valueAt(valuesByYear, year, code);
    if (before == null) continue;
    const abs = now - before;
    const pct = before > 0 ? (abs / before) * 100 : null;
    return { year, before, now, abs, pct };
  }
  return null;
}

/** Последние `limit` значений страны по годам до выбранного включительно (для мини-графика). */
export function countrySeries(valuesByYear, years, activeYear, code, limit = 12) {
  const list = [...(years || [])].map(Number).filter((y) => y <= Number(activeYear)).sort((a, b) => a - b);
  const points = [];
  for (const year of list) {
    const value = valueAt(valuesByYear, year, code);
    if (value != null) points.push({ year, value });
  }
  return points.slice(-limit);
}

/** Место каждой страны в году: 1 — лучший по направлению (`desc` — больше лучше, `asc` — меньше лучше). */
export function rankMap(valuesByYear, year, direction = 'desc') {
  const bucket = valuesByYear?.[String(year)] || {};
  const rows = Object.entries(bucket)
    .map(([code, item]) => [code, numberOrNull(item)])
    .filter(([, value]) => value != null)
    .sort((a, b) => (direction === 'asc' ? a[1] - b[1] : b[1] - a[1]));
  const map = new Map();
  rows.forEach(([code], index) => map.set(code, index + 1));
  return map;
}

/**
 * Как изменились места за `span` лет: берётся ближайший к `activeYear - span` год с достаточным числом
 * стран. Возвращает null, когда сравнивать не с чем (мало стран или нет такого года).
 */
export function rankShifts(valuesByYear, years, activeYear, direction = 'desc', {
  span = 5, minCountries = 8, top = 5,
} = {}) {
  const target = Number(activeYear) - span;
  const candidates = [...(years || [])].map(Number)
    .filter((y) => y < Number(activeYear) && y >= target - 2 && y <= target + 1)
    .sort((a, b) => Math.abs(a - target) - Math.abs(b - target));
  const nowMap = rankMap(valuesByYear, activeYear, direction);
  if (nowMap.size < minCountries) return null;
  for (const fromYear of candidates) {
    const thenMap = rankMap(valuesByYear, fromYear, direction);
    if (thenMap.size < minCountries) continue;
    const moves = [];
    for (const [code, now] of nowMap) {
      const then = thenMap.get(code);
      if (then == null) continue;
      moves.push({ code, now, then, change: then - now });
    }
    if (moves.length < minCountries) continue;
    const risers = moves.filter((m) => m.change > 0).sort((a, b) => b.change - a.change || a.now - b.now).slice(0, top);
    const fallers = moves.filter((m) => m.change < 0).sort((a, b) => a.change - b.change || a.now - b.now).slice(0, top);
    return { fromYear, toYear: Number(activeYear), risers, fallers, compared: moves.length };
  }
  return null;
}

/**
 * Доли значений для полоски: от нуля до максимума, только при неотрицательных значениях.
 * При `opts.scale === 'log'` полоска идёт по логарифму между наименьшим положительным значением (`opts.min`) и максимумом:
 * у ВВП и населения разница между странами в тысячи раз, и на линейной шкале у всех, кроме двух-трёх стран, была бы «точка».
 */
export function shareOf(value, max, positive = true, opts = {}) {
  const v = Number(value);
  if (!positive || !Number.isFinite(v) || !(max > 0) || v < 0) return 0;
  if (opts.scale === 'log' && v > 0 && opts.min > 0 && max > opts.min) {
    const part = (Math.log(v) - Math.log(opts.min)) / (Math.log(max) - Math.log(opts.min));
    return Math.max(6, Math.min(100, 6 + part * 94));
  }
  return Math.max(2, Math.min(100, (v / max) * 100));
}

/** Шкала полосок рейтинга по всем значениям: максимум, наименьшее положительное, есть ли отрицательные и линейная или логарифмическая. */
export function barScaleOf(values) {
  let max = 0;
  let min = Infinity;
  let positive = true;
  const all = [];
  for (const raw of values || []) {
    const value = Number(raw);
    if (!Number.isFinite(value)) continue;
    if (value < 0) positive = false;
    if (value > max) max = value;
    if (value > 0) {
      if (value < min) min = value;
      all.push(value);
    }
  }
  all.sort((a, b) => a - b);
  const median = all.length ? all[Math.floor(all.length / 2)] : 0;
  // Размах больше чем в 20 раз между максимумом и «типичной» страной: линейная шкала сжимает почти всех в точку.
  const scale = median > 0 && max / median > 20 ? 'log' : 'linear';
  return { max, min: Number.isFinite(min) ? min : 0, positive, scale };
}
