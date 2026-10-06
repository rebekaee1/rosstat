/**
 * Витрина «Прогнозы»: чистая логика страницы (геометрия мини-графика, подписи чисел).
 * Данные приходят из `GET /api/v1/forecasts/showcase` (backend `forecast_showcase.py`).
 */

const DAY = 86400000;

function toTime(isoDate) {
  return Date.parse(`${isoDate}T00:00:00Z`);
}

function round(n) {
  return Math.round(n * 10) / 10;
}

/** Сколько знаков после запятой показывать: проценты с десятыми, крупные числа целыми. */
export function digitsFor(item, value) {
  const abs = Math.abs(Number(value));
  if (!Number.isFinite(abs)) return 1;
  if (abs >= 1000) return 0;
  if (item?.kind === 'percent') return 1;
  if (abs >= 100) return 1;
  return 2;
}

/** Знак процента ставим к числу только там, где единица начинается с «%». */
export function percentSign(unit) {
  return String(unit || '').trim().startsWith('%') ? ' %' : '';
}

/** Ключ i18n для фразы про изменение: `zb.change.points.up`, `zb.change.percent.down`, `zb.change.flat`. */
export function changeMessageKey(change) {
  if (!change || change.direction === 'flat') return 'zb.change.flat';
  return `zb.change.${change.unit === 'points' ? 'points' : 'percent'}.${change.direction === 'up' ? 'up' : 'down'}`;
}

/**
 * Геометрия мини-графика: линия факта и линия прогноза от точки последнего факта. Диапазона вокруг прогноза нет.
 */
export function chartGeometry(item, { width = 320, height = 132, pad } = {}) {
  const p = { l: 6, r: 12, t: 12, b: 10, ...(pad || {}) };
  const history = (item?.history || []).filter((row) => Number.isFinite(row.value));
  const forecast = (item?.forecast || []).filter((row) => Number.isFinite(row.value));
  if (history.length < 2 || forecast.length < 1) return null;

  const times = [...history, ...forecast].map((row) => toTime(row.date));
  const tMin = Math.min(...times);
  const tMax = Math.max(...times);
  const span = Math.max(tMax - tMin, DAY);

  const values = [];
  history.forEach((row) => values.push(row.value));
  forecast.forEach((row) => values.push(row.value));
  let vMin = Math.min(...values);
  let vMax = Math.max(...values);
  if (vMax - vMin < 1e-9) {
    vMin -= 1;
    vMax += 1;
  }
  const margin = (vMax - vMin) * 0.1;
  vMin -= margin;
  vMax += margin;

  const x = (iso) => p.l + ((toTime(iso) - tMin) / span) * (width - p.l - p.r);
  const y = (v) => p.t + (1 - (v - vMin) / (vMax - vMin)) * (height - p.t - p.b);

  const last = history[history.length - 1];
  const lastX = x(last.date);
  const lastY = y(last.value);
  const end = forecast[forecast.length - 1];

  const histPath = history
    .map((row, i) => `${i ? 'L' : 'M'}${round(x(row.date))} ${round(y(row.value))}`)
    .join(' ');
  const forePath = [`M${round(lastX)} ${round(lastY)}`]
    .concat(forecast.map((row) => `L${round(x(row.date))} ${round(y(row.value))}`))
    .join(' ');

  return {
    width,
    height,
    histPath,
    forePath,
    splitX: round(lastX),
    zone: { x: round(lastX), width: round(width - lastX) },
    now: { x: round(lastX), y: round(lastY) },
    end: { x: round(x(end.date)), y: round(y(end.value)) },
  };
}
