// Круг 11 (E): ряды для графика курса: период (неделя, месяц, год, всё время), вторая пара поверх первой в индексе
// «старт = 100», подписи оси X без наложений и день в подсказке. Чистая логика без React.
import { unitMeta } from './currencyRates';

export const CHART_PERIODS = ['week', 'month', 'year', 'all'];
const PERIOD_DAYS = { week: 7, month: 31, year: 366, all: 36500 };
const DAY_MS = 86_400_000;
const MAX_POINTS = 600;

/** Сколько точек просить у сервера: для «всё время» максимум, для остальных хватает 400 дневных. */
export function limitForPeriod(period) {
  return period === 'all' ? 10000 : 400;
}

export function unitName(unit, locale) {
  const meta = unitMeta(unit);
  if (!meta) return unit;
  return locale === 'en' ? meta.en : meta.ru;
}

/** Значок валюты: у доллара знак «$» (флаг США читался как «валюта страны»), у остальных флаг, у монет их знак. */
export function coinOf(unit) {
  const meta = unitMeta(unit);
  if (!meta) return {};
  return unit === 'USD' ? { symbol: '$' } : { flag: meta.flag, symbol: meta.symbol };
}

/** Знаков после запятой по величине курса. */
export function rateDigits(value) {
  const abs = Math.abs(value);
  if (abs >= 1000) return 0;
  if (abs >= 1) return 2;
  if (abs >= 0.01) return 4;
  return 6;
}

/** Число знаков для делений оси по шагу: 1000 -> 0, 0,5 -> 1, 0,00005 -> 5. */
export function digitsForStep(step) {
  if (!(step > 0) || step >= 1) return 0;
  return Math.min(8, Math.ceil(-Math.log10(step) - 1e-9));
}

const toMs = (iso) => Date.parse(`${String(iso).slice(0, 10)}T12:00:00Z`);

/** Строки API в точки { date, value }: по возрастанию даты, без мусора. */
export function cleanSeries(rows, { invert = false } = {}) {
  const points = (rows || [])
    .map((row) => ({ date: String(row?.date || '').slice(0, 10), value: Number(row?.value) }))
    .filter((p) => /^\d{4}-\d{2}-\d{2}$/.test(p.date) && Number.isFinite(p.value) && p.value > 0)
    .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
  return invert ? points.map((p) => ({ date: p.date, value: 1 / p.value })) : points;
}

/** Не больше `max` точек: равномерная выборка, последняя точка остаётся. */
export function downsample(points, max = MAX_POINTS) {
  if (points.length <= max) return points;
  const step = (points.length - 1) / (max - 1);
  const out = [];
  for (let i = 0; i < max; i += 1) out.push(points[Math.round(i * step)]);
  return out;
}

/** Срез за период от последней точки ряда. Если за неделю меньше двух точек, берутся две последние. */
export function sliceByPeriod(points, period) {
  if (!points.length) return [];
  const days = PERIOD_DAYS[period] ?? PERIOD_DAYS.year;
  const from = toMs(points[points.length - 1].date) - days * DAY_MS;
  const sliced = points.filter((p) => toMs(p.date) >= from);
  const result = sliced.length >= 2 ? sliced : points.slice(-2);
  return period === 'all' ? downsample(result) : result;
}

/** Значение ряда на дату или ближайшее до неё; `cursor` — изменяемый указатель для линейного прохода. */
function valueAtOrBefore(points, date, cursor) {
  while (cursor.i + 1 < points.length && points[cursor.i + 1].date <= date) cursor.i += 1;
  return points[cursor.i] && points[cursor.i].date <= date ? points[cursor.i].value : null;
}

/**
 * Две пары в одном индексе: на общую дату начала обе равны 100. Даты берутся у первой пары,
 * значение второй на дату: ближайшее не позже неё. Возвращает [] , если общих дат меньше двух.
 * Точка: { date, a, b, rawA, rawB } (a и b — индексы).
 */
export function alignIndex(primary, secondary) {
  if (!primary.length || !secondary.length) return [];
  const cursor = { i: 0 };
  const joined = [];
  for (const point of primary) {
    const other = valueAtOrBefore(secondary, point.date, cursor);
    if (other != null) joined.push({ date: point.date, rawA: point.value, rawB: other });
  }
  if (joined.length < 2) return [];
  const a0 = joined[0].rawA;
  const b0 = joined[0].rawB;
  return joined.map((p) => ({ ...p, a: (p.rawA / a0) * 100, b: (p.rawB / b0) * 100 }));
}

/** Изменение за период в процентах (первое → последнее значение). */
export function changePct(points, pick = (p) => p.value) {
  if (points.length < 2) return null;
  const first = pick(points[0]);
  const last = pick(points[points.length - 1]);
  return first ? ((last - first) / first) * 100 : null;
}

/**
 * Подписи оси X. kind: 'day' (до полутора месяцев: «9 окт»), 'month' («окт», у краёв и января с годом) или 'year' («2019»).
 * slots — сколько подписей максимум (3 на узком графике, 5 на широком). Подписи не повторяются.
 */
export function axisPlan(points, narrow = false) {
  if (!points.length) return { kind: 'month', ticks: [] };
  const spanDays = (toMs(points[points.length - 1].date) - toMs(points[0].date)) / DAY_MS;
  const kind = spanDays <= 45 ? 'day' : spanDays <= 400 ? 'month' : 'year';
  const slots = narrow ? 3 : 5;
  const last = points.length - 1;
  let indexes;
  if (kind === 'year') {
    // Первая точка каждого года; если лет больше, чем подписей, берётся равномерная выборка лет.
    const firstOfYear = [];
    points.forEach((p, i) => {
      const year = p.date.slice(0, 4);
      if (!firstOfYear.length || points[firstOfYear[firstOfYear.length - 1]].date.slice(0, 4) !== year) firstOfYear.push(i);
    });
    if (firstOfYear.length <= slots) indexes = firstOfYear;
    else {
      indexes = [];
      for (let s = 0; s < slots; s += 1) indexes.push(firstOfYear[Math.round(((firstOfYear.length - 1) * s) / (slots - 1))]);
    }
  } else {
    indexes = [];
    const n = Math.min(slots, points.length);
    for (let s = 0; s < n; s += 1) indexes.push(n === 1 ? 0 : Math.round((last * s) / (n - 1)));
  }
  const ticks = [...new Set(indexes)].map((i) => points[i].date);
  return { kind, ticks };
}
