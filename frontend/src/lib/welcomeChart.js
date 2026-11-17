/**
 * Приветственный экран, третья версия (17.11.2026): настоящий ряд вместо нарисованных картинок.
 *
 * Чистые функции для линии: какой отрезок показать, как положить точки в поле, какая точка под пальцем,
 * как написать число и месяц. Проверяет `welcomeChart.test.js`. Данные — `GET /world/compare/series/{страна}/{понятие}`.
 */
export const WELCOME_CONCEPT = 'unemployment-rate';
/** Сколько последних лет показывать: видно и спокойные годы, и перелом, линия не превращается в шум. */
export const WELCOME_YEARS = 10;
/** Поле рисунка в условных единицах; SVG растягивается на всю ширину, толщина линии от этого не зависит. */
export const FIELD = Object.freeze({ w: 1000, h: 320, top: 26, bottom: 30 });

/** Точки из ответа сервера: только настоящие числа с датой, по возрастанию даты, последние `years` лет. */
export function cleanSeries(payload, years = WELCOME_YEARS) {
  const raw = Array.isArray(payload?.data) ? payload.data : [];
  const points = [];
  for (const row of raw) {
    const t = Date.parse(row?.date);
    const value = typeof row?.value === 'number' ? row.value : Number.NaN;
    if (Number.isFinite(t) && Number.isFinite(value)) points.push({ t, value, date: row.date });
  }
  points.sort((a, b) => a.t - b.t);
  if (points.length < 12) return [];
  const last = points[points.length - 1].t;
  const from = last - years * 365.25 * 86400000;
  return points.filter((p) => p.t >= from);
}

/** Общие границы поля для одного или двух рядов: время и значения с запасом сверху и снизу. */
export function fieldBounds(...series) {
  const all = series.filter((s) => s && s.length).flat();
  if (!all.length) return null;
  let tMin = Infinity; let tMax = -Infinity; let vMin = Infinity; let vMax = -Infinity;
  for (const p of all) {
    if (p.t < tMin) tMin = p.t;
    if (p.t > tMax) tMax = p.t;
    if (p.value < vMin) vMin = p.value;
    if (p.value > vMax) vMax = p.value;
  }
  const span = vMax - vMin || Math.abs(vMax) || 1;
  return { tMin, tMax: tMax === tMin ? tMin + 1 : tMax, vMin: vMin - span * 0.18, vMax: vMax + span * 0.12 };
}

/** Точка ряда в координатах поля. */
export function place(point, bounds, field = FIELD) {
  const x = ((point.t - bounds.tMin) / (bounds.tMax - bounds.tMin)) * field.w;
  const usable = field.h - field.top - field.bottom;
  const y = field.top + (1 - (point.value - bounds.vMin) / (bounds.vMax - bounds.vMin)) * usable;
  return { x, y };
}

const fix = (n) => (Math.round(n * 10) / 10).toString();

/** Линия ряда: прямые отрезки между настоящими точками (сглаживание дорисовывало бы то, чего в данных нет). */
export function linePath(series, bounds, field = FIELD) {
  return series.map((p, i) => {
    const { x, y } = place(p, bounds, field);
    return `${i ? 'L' : 'M'}${fix(x)} ${fix(y)}`;
  }).join(' ');
}

/** Площадь тона под линией до низа поля. */
export function areaPath(series, bounds, field = FIELD) {
  if (!series.length) return '';
  const first = place(series[0], bounds, field);
  const last = place(series[series.length - 1], bounds, field);
  return `${linePath(series, bounds, field)} L${fix(last.x)} ${field.h} L${fix(first.x)} ${field.h} Z`;
}

/** Ближайшая по времени точка к доле ширины поля (0…1): то, что «под пальцем». */
export function nearestIndex(series, bounds, fraction) {
  if (!series.length) return -1;
  const t = bounds.tMin + Math.max(0, Math.min(1, fraction)) * (bounds.tMax - bounds.tMin);
  let lo = 0; let hi = series.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (series[mid].t < t) lo = mid; else hi = mid;
  }
  return Math.abs(series[lo].t - t) <= Math.abs(series[hi].t - t) ? lo : hi;
}

/** Отметки лет под полем: начало каждого года внутри отрезка, не чаще чем через `step` лет. */
export function yearTicks(bounds, maxTicks = 6) {
  const first = new Date(bounds.tMin).getUTCFullYear() + 1;
  const last = new Date(bounds.tMax).getUTCFullYear();
  const count = last - first + 1;
  if (count <= 0) return [];
  const step = Math.max(1, Math.ceil(count / maxTicks));
  const ticks = [];
  for (let year = last; year >= first; year -= step) {
    const t = Date.UTC(year, 0, 1);
    ticks.unshift({ year, fraction: (t - bounds.tMin) / (bounds.tMax - bounds.tMin) });
  }
  return ticks;
}

/** «2,2 %» по-русски, «4.1%» по-английски: один знак после запятой, как у источника. */
export function formatPercent(value, locale) {
  const digits = new Intl.NumberFormat(locale === 'en' ? 'en-US' : 'ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(value);
  return locale === 'en' ? `${digits}%` : `${digits}\u00a0%`;
}

/** «сентябрь 2026» / «September 2026». Дата ряда — первое число месяца в UTC. */
export function formatMonth(dateOrMs, locale) {
  const date = new Date(dateOrMs);
  const text = new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'ru-RU', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(date);
  return text.replace(/\s*г\.?$/, '');
}
