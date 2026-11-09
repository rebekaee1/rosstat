// R10-C: длинная история цены (ключевые годы, инфляция, пропуски). Чистые функции, без запросов.

export const KEY_YEARS = [2000, 2008, 2014, 2022];

const ymOf = (p) => p.year * 100 + p.month;

/** Точка в том же месяце года, что и последняя (ближайшая в пределах 2 месяцев; иначе null). */
export function pointNearMonth(series, year, month) {
  if (!Array.isArray(series)) return null;
  let best = null;
  let bestD = 3;
  for (const p of series) {
    if (p.year !== year || p.value == null) continue;
    const d = Math.abs(p.month - month);
    if (d < bestD) { best = p; bestD = d; }
  }
  return best;
}

/** Индекс ИПЦ: Map YYYYMM → число из ответа API ([[ym, idx], ...]). */
export function cpiMap(cpi) {
  const m = new Map();
  if (Array.isArray(cpi)) for (const row of cpi) if (Array.isArray(row) && row[1] > 0) m.set(row[0], row[1]);
  return m;
}

/**
 * Строки «цена в ключевые годы». Если у региона года нет, но он есть у России, берём Россию (source 'russia').
 * Строки без данных остаются (source null): учитель видит, где данных нет.
 */
export function keyYearRows(series, russiaSeries, last, cpi, years = KEY_YEARS) {
  if (!last) return [];
  const cm = cpiMap(cpi);
  const nowCpi = cm.get(ymOf(last));
  const rows = [];
  for (const year of years) {
    if (year >= last.year) continue;
    let point = pointNearMonth(series, year, last.month);
    let source = point ? 'region' : null;
    if (!point) {
      const rp = pointNearMonth(russiaSeries, year, last.month);
      if (rp) { point = rp; source = 'russia'; }
    }
    if (!point) { rows.push({ year, point: null, source: null }); continue; }
    let lastVal = last.value;
    if (source === 'russia') {
      const rl = (russiaSeries || []).find((p) => ymOf(p) === ymOf(last));
      lastVal = rl ? rl.value : null;
    }
    const times = lastVal != null && point.value > 0 ? lastVal / point.value : null;
    const thenCpi = cm.get(ymOf(point));
    const infl = nowCpi && thenCpi ? nowCpi / thenCpi : null;
    const real = times != null && infl ? times / infl : null;
    rows.push({ year, point, source, times, infl, real });
  }
  return rows;
}

/** «в 2,7 раза» / «в 5 раз» / «2.7x» (en). */
export function timesText(x, locale = 'ru') {
  if (!(x > 0)) return '';
  const digits = x >= 10 ? 0 : 1;
  const r = Number(x.toFixed(digits));
  if (locale === 'en') return `${r.toLocaleString('en-US', { maximumFractionDigits: digits })}x`;
  const body = r.toLocaleString('ru-RU', { maximumFractionDigits: digits });
  const whole = Number.isInteger(r);
  const mod10 = r % 10;
  const mod100 = r % 100;
  const word = whole && mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14) ? 'раза'
    : whole ? 'раз' : 'раза';
  return `в\u00A0${body}\u00A0${word}`;
}

/** Короткое «×2,7» для плиток. */
export function timesShort(x, locale = 'ru') {
  if (!(x > 0)) return '';
  const digits = x >= 10 ? 0 : 1;
  return `×${Number(x.toFixed(digits)).toLocaleString(locale === 'en' ? 'en-US' : 'ru-RU', { maximumFractionDigits: digits })}`;
}

/** Рубли последнего месяца: значение каждой точки, пересчитанное на уровень цен последнего месяца. */
export function deflateSeries(series, cpi, lastYm) {
  const cm = cpiMap(cpi);
  const now = cm.get(lastYm);
  if (!now || !Array.isArray(series)) return null;
  const out = [];
  for (const p of series) {
    const c = cm.get(ymOf(p));
    if (!c || p.value == null) continue;
    out.push({ ...p, value: Math.round(((p.value * now) / c) * 100) / 100 });
  }
  return out.length > 2 ? out : null;
}

/** Пропуски в месячном ряду: [{from, to, months}] по YYYYMM. */
export function monthGaps(series) {
  const gaps = [];
  if (!Array.isArray(series)) return gaps;
  for (let i = 1; i < series.length; i++) {
    const a = series[i - 1];
    const b = series[i];
    const d = (b.year * 12 + b.month) - (a.year * 12 + a.month);
    if (d > 1) gaps.push({ from: ymOf(a), to: ymOf(b), months: d - 1 });
  }
  return gaps;
}

/** Вставляет пустые месяцы (value null), чтобы линия рвалась на пропуске. Слишком длинные дыры не раздувают ось. */
export function fillMonthGaps(series, maxFill = 60) {
  if (!Array.isArray(series) || series.length < 2) return series;
  const out = [];
  for (let i = 0; i < series.length; i++) {
    const p = series[i];
    if (i > 0) {
      const a = series[i - 1];
      const d = (p.year * 12 + p.month) - (a.year * 12 + a.month);
      if (d > 1 && d - 1 <= maxFill) {
        for (let k = 1; k < d; k++) {
          const tot = a.year * 12 + a.month - 1 + k;
          const y = Math.floor(tot / 12);
          const m = (tot % 12) + 1;
          out.push({ year: y, month: m, value: null, label: `${y}-${String(m).padStart(2, '0')}` });
        }
      }
    }
    out.push(p);
  }
  return out;
}

/** Годы-метки для вертикальных линий графика (только внутри показанного периода). */
export function eventPeriods(points, years = [2008, 2014, 2022]) {
  if (!Array.isArray(points) || points.length < 36) return [];
  const first = points[0].year;
  const res = [];
  for (const y of years) {
    if (y <= first + 1) continue;
    const hit = points.find((p) => p.year === y && p.month === 1) || points.find((p) => p.year === y);
    if (hit) res.push({ year: y, period: hit.label || `${hit.year}-${String(hit.month).padStart(2, '0')}` });
  }
  return res;
}

/** Для каждого года: цена в том же месяце, что и последняя точка, и изменение к прошлому году. */
export function yearlyRows(series, last) {
  if (!Array.isArray(series) || !last) return [];
  const rows = [];
  let prev = null;
  for (let y = series[0].year; y < last.year; y++) {
    const p = pointNearMonth(series, y, last.month);
    if (p) {
      rows.push({ year: y, point: p, yoy: prev && prev.value ? ((p.value - prev.value) / prev.value) * 100 : null });
      prev = p;
    } else {
      rows.push({ year: y, point: null, yoy: null });
      prev = null;
    }
  }
  return rows.reverse();
}
