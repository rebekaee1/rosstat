/**
 * Режимы показателя («к прошлому периоду», «год к году», «индекс») из исходного ряда на самой странице.
 *
 * Сервер иногда отвечает отказом на такой режим (например, у рядов с нулями и отрицательными значениями).
 * Тогда страница не показывает ошибку, а считает то же самое из значений: человек видит график.
 * Если посчитать нельзя (нет положительной базы), возвращаем null, и страница прячет этот режим.
 */

function shiftYear(iso, delta) {
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return null;
  d.setUTCFullYear(d.getUTCFullYear() + delta);
  return d.toISOString().slice(0, 10);
}

function clean(points) {
  return (Array.isArray(points) ? points : [])
    .filter((p) => p && p.date && Number.isFinite(Number(p.value)))
    .map((p) => ({ ...p, date: String(p.date).slice(0, 10), value: Number(p.value) }));
}

/**
 * @param {Array<{date: string, value: number}>} levelPoints исходный ряд (значения), по возрастанию дат
 * @param {'step'|'yoy'|'yoyabs'|'index'} type
 * @returns {{ points: Array<{date: string, value: number}>, unit: 'percent'|'same'|'index' } | null}
 */
export function deriveWorldMode(levelPoints, type) {
  const points = clean(levelPoints);
  if (points.length < 2) return null;
  let out = [];
  let unit = 'percent';
  if (type === 'step') {
    for (let i = 1; i < points.length; i += 1) {
      const prev = points[i - 1].value;
      if (prev > 0) out.push({ date: points[i].date, value: (points[i].value / prev - 1) * 100 });
    }
  } else if (type === 'yoy' || type === 'yoyabs') {
    const byDate = new Map(points.map((p) => [p.date, p.value]));
    unit = type === 'yoy' ? 'percent' : 'same';
    for (const p of points) {
      const back = shiftYear(p.date, -1);
      const base = back ? byDate.get(back) : undefined;
      if (base == null) continue;
      if (type === 'yoy') {
        if (base > 0) out.push({ date: p.date, value: (p.value / base - 1) * 100 });
      } else {
        out.push({ date: p.date, value: p.value - base });
      }
    }
  } else if (type === 'index') {
    unit = 'index';
    const first = points.find((p) => p.value > 0);
    if (!first) return null;
    out = points
      .filter((p) => p.date >= first.date)
      .map((p) => ({ date: p.date, value: (p.value / first.value) * 100 }));
  } else {
    return null;
  }
  return out.length >= 2 ? { points: out, unit } : null;
}
