/**
 * Сводка ряда для страницы показателя: что показать в плитках и заголовке, чтобы это имело смысл для человека.
 *
 * Среднее и «исторический максимум» бессмысленны для индекса, ВВП и численности населения, поэтому тип ряда
 * (процент, индекс, обычная величина) решает, какие плитки показывать: рост за 10 лет, место среди стран,
 * разброс за 10 лет. Здесь только чистые функции без React: их проверяют тестами.
 */
import { formatValue } from './format';

const NBSP = ' ';
const MINUS = '−';
const DAY_MS = 86400000;

export const PERIODS_PER_YEAR = Object.freeze({
  daily: 365, weekly: 52, monthly: 12, quarterly: 4, annual: 1,
});

/** Единица вида «изменение за год, %», «annual change, %»: сам ряд уже в процентах изменения, пересчитывать его в рост незачем. */
export function isPercentChangeUnit(unit) {
  const u = String(unit ?? '').toLowerCase();
  if (!/%|процент|percent/.test(u)) return false;
  return /изменени|рост|за\s+год|per\s+year|annual|year[-\s]?on[-\s]?year|yoy|change|growth/.test(u);
}

/**
 * Единица ряда для показа. Если в ответе с данными стоит «индекс 2015 = 100», а в описании показателя процентная единица
 * («изменение за год, %»), верим описанию: значения процентные, индексом они не бывают (Китай «0,05 индекс», Турция «34,88 индекс»).
 */
export function preferPercentUnit(dataUnit, ...fallbacks) {
  const own = String(dataUnit ?? '');
  if (own && !/индекс|index|=\s*100/i.test(own)) return own;
  for (const candidate of fallbacks) {
    const text = String(candidate ?? '');
    if (text && isPercentChangeUnit(text) && !/индекс|index|=\s*100/i.test(text)) return text;
  }
  return own;
}

/**
 * 'rate'  — проценты, пункты, «на 1000 жителей» и любые изменения (сами уже темп);
 * 'index' — индексы с базовым годом («2015 = 100»);
 * 'level' — обычные величины: деньги, люди, тонны.
 */
export function unitKind(unit, modeType) {
  if (modeType === 'yoy' || modeType === 'step' || modeType === 'yoyabs') return 'rate';
  const u = String(unit ?? '').toLowerCase();
  // «изменение за год, %» уже темп: слово «индекс» рядом (старая подпись понятия «индекс 2015 = 100») не делает ряд индексом.
  if (isPercentChangeUnit(u)) return 'rate';
  if (/индекс|index|=\s*100/.test(u)) return 'index';
  if (/%|п\.\s?п\.|\bpp\b|на\s+1\s?000|per\s+1,?000|‰|промилле/.test(u)) return 'rate';
  return 'level';
}

function isoOf(value) {
  return String(value ?? '').slice(0, 10);
}

function shiftYears(iso, years) {
  const d = new Date(`${isoOf(iso)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return null;
  d.setUTCFullYear(d.getUTCFullYear() - years);
  return d.toISOString().slice(0, 10);
}

function finitePoints(points) {
  return (Array.isArray(points) ? points : []).filter(
    (point) => point && point.date && Number.isFinite(Number(point.value)),
  );
}

function pointOnOrBefore(points, iso) {
  for (let i = points.length - 1; i >= 0; i -= 1) {
    if (isoOf(points[i].date) <= iso) return points[i];
  }
  return null;
}

/** Рост последнего значения к значению `years` лет назад, в процентах; null, если истории не хватает. */
export function growthOverYears(points, years, { maxGapDays = 400 } = {}) {
  const valid = finitePoints(points);
  if (valid.length < 2) return null;
  const last = valid[valid.length - 1];
  const target = shiftYears(last.date, years);
  if (!target) return null;
  const from = pointOnOrBefore(valid, target);
  if (!from || from === last) return null;
  const gap = (Date.parse(target) - Date.parse(isoOf(from.date))) / DAY_MS;
  if (gap > maxGapDays) return null;
  const a = Number(from.value);
  const b = Number(last.value);
  if (!(a > 0) || b < 0) return null;
  return { pct: (b / a - 1) * 100, years, from, to: last };
}

/** Самое длинное окно из списка, для которого хватает истории (10, затем 5, затем 3 года). */
export function bestGrowth(points, windows = [10, 5, 3]) {
  for (const years of windows) {
    const growth = growthOverYears(points, years);
    if (growth) return growth;
  }
  return null;
}

/** Наибольшее, наименьшее и среднее за последние `years` лет; null, если точек мало. */
export function windowStats(points, years = 10) {
  const valid = finitePoints(points);
  if (valid.length < 3) return null;
  const last = valid[valid.length - 1];
  const cutoff = shiftYears(last.date, years);
  const inside = cutoff ? valid.filter((point) => isoOf(point.date) >= cutoff) : valid;
  if (inside.length < 3) return null;
  let highest = inside[0];
  let lowest = inside[0];
  let sum = 0;
  for (const point of inside) {
    const v = Number(point.value);
    sum += v;
    if (v > Number(highest.value)) highest = point;
    if (v < Number(lowest.value)) lowest = point;
  }
  const spanDays = (Date.parse(isoOf(last.date)) - Date.parse(isoOf(inside[0].date))) / DAY_MS;
  return {
    highest: { value: Number(highest.value), date: highest.date },
    lowest: { value: Number(lowest.value), date: lowest.date },
    average: sum / inside.length,
    // Сколько полных лет охватывают значения: если меньше года, подпись плитки говорит «за весь период», а не «за 1 год».
    years: Math.floor(spanDays / 365 + 0.15),
    count: inside.length,
  };
}

/**
 * Оценка, а не факт: годовое значение за текущий или будущий год (так публикует МВФ) либо точка с датой в будущем.
 * `now` передаётся снаружи, чтобы функция оставалась чистой.
 */
export function isEstimateDate(date, frequency, now = new Date()) {
  const d = new Date(`${isoOf(date)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return false;
  if (frequency === 'annual') return d.getUTCFullYear() >= now.getUTCFullYear();
  return d.getTime() > now.getTime();
}

/** Сколько лет охватывает ряд: для подписи «за 12 лет». */
export function spanYears(points) {
  const valid = finitePoints(points);
  if (valid.length < 2) return 0;
  const first = Date.parse(isoOf(valid[0].date));
  const last = Date.parse(isoOf(valid[valid.length - 1].date));
  return Math.round((last - first) / (DAY_MS * 365));
}

// Ступени «покрупнее»: 30 767 млрд $ читается как 30,8 трлн $, 28 076 986 человек как 28,1 млн человек.
const LADDER_RU = [
  { re: /^млрд(?=\s|$)/, min: 1000, div: 1000, to: 'трлн' },
  { re: /^млн(?=\s|$)/, min: 1000, div: 1000, to: 'млрд' },
  { re: /^тыс\.\s*человек/, min: 1000, div: 1000, to: 'млн человек' },
  { re: /^человек$/, min: 1e6, div: 1e6, to: 'млн человек' },
  { re: /^тыс\.(?=\s|$)/, min: 1000, div: 1000, to: 'млн' },
];
const LADDER_EN = [
  { re: /^billion(?=\s|$)/i, min: 1000, div: 1000, to: 'trillion' },
  { re: /^million(?=\s|$)/i, min: 1000, div: 1000, to: 'billion' },
  { re: /^(ths|thousand)\s+(persons|people)/i, min: 1000, div: 1000, to: 'million people' },
  { re: /^(people|persons)$/i, min: 1e6, div: 1e6, to: 'million people' },
  { re: /^(ths|thousand)(?=\s|$)/i, min: 1000, div: 1000, to: 'million' },
];

function compactDigits(v) {
  const abs = Math.abs(v);
  if (abs >= 100) return 0;
  if (abs >= 1) return 1;
  return 2;
}

/** Знаков после запятой ровно столько, сколько есть в самих данных (не больше двух): «3,1», а не «3,10». */
export function dataDigitsOf(points, fallback = 2) {
  const valid = finitePoints(points);
  if (!valid.length) return fallback;
  let max = 0;
  for (const point of valid.slice(-60)) {
    const decimals = (String(Math.abs(Number(point.value))).split('.')[1] || '').length;
    if (decimals > max) max = decimals;
  }
  return Math.min(2, max);
}

/**
 * Знаков после запятой для обычного (не укрупнённого) числа: ровно как в данных ряда.
 * Раньше у чисел от 100 знаков было не больше одного, и шапка писала «114,0», а таблица под ней «113,96»: выглядело как два разных числа.
 */
export function tidyDigits(value, dataDigits = 2) {
  const abs = Math.abs(Number(value));
  if (!Number.isFinite(abs)) return dataDigits;
  return Math.max(0, Math.min(2, dataDigits));
}

/**
 * Значение и единица для плитки: крупные числа укрупняются, лишние знаки убираются.
 * @returns {{ text: string, unit: string, compacted: boolean }}
 */
export function formatTileValue(value, unit, { dataDigits = 2, locale = 'ru' } = {}) {
  const n = Number(value);
  const u = String(unit ?? '').trim();
  if (value == null || !Number.isFinite(n)) {
    return { text: '—', unit: u, compacted: false, div: 1, digits: 0 };
  }
  const ladder = locale === 'en' ? LADDER_EN : LADDER_RU;
  for (const rule of ladder) {
    if (rule.re.test(u) && Math.abs(n) >= rule.min) {
      const scaled = n / rule.div;
      const digits = compactDigits(scaled);
      return {
        text: formatValue(scaled, digits, locale),
        unit: u.replace(rule.re, rule.to),
        compacted: true,
        div: rule.div,
        digits,
      };
    }
  }
  const digits = tidyDigits(n, dataDigits);
  return { text: formatValue(n, digits, locale), unit: u, compacted: false, div: 1, digits };
}

/** «+5,0 %» со знаком минус-тире и неразрывным пробелом; null, если после округления изменения нет. */
export function formatPercentChange(pct, locale = 'ru', digits = 1) {
  const n = Number(pct);
  if (pct == null || !Number.isFinite(n)) return null;
  if (Number(n.toFixed(digits)) === 0) return null;
  const body = formatValue(Math.abs(n), digits, locale);
  return `${n > 0 ? '+' : MINUS}${body}${NBSP}%`;
}

/** Рост в процентах крупными окнами: от 1000 % убираем дробную часть, чтобы не было «+1 234,5 %». */
export function growthDigits(pct) {
  return Math.abs(Number(pct)) >= 100 ? 0 : 1;
}

/**
 * Место страны среди остальных по последним значениям (больше значение — выше место).
 * `items` — строки снимка рейтинга {country_code, value}; свою страну находим по коду,
 * а при её отсутствии в списке встраиваем по собственному значению.
 */
export function rankAmongCountries(items, countryCode, ownValue) {
  const rows = (Array.isArray(items) ? items : [])
    .filter((item) => item && Number.isFinite(Number(item.value)));
  if (rows.length < 3) return null;
  const own = rows.find((item) => item.country_code === countryCode);
  const value = own ? Number(own.value) : Number(ownValue);
  if (!Number.isFinite(value)) return null;
  const higher = rows.filter(
    (item) => item !== own && Number(item.value) > value,
  ).length;
  return { rank: higher + 1, total: rows.length + (own ? 0 : 1) };
}

/**
 * Всё, что нужно заголовку и плиткам страницы показателя, одним объектом.
 * `unit` — уже локализованная единица («млрд $», «%», «индекс 2015 = 100»), `modeType` — тип режима мировой карточки.
 * @returns {null | {
 *   kind: 'rate'|'index'|'level', unit: string, estimate: boolean,
 *   last: {value: number, date: string}, prev: {value: number, date: string}|null,
 *   shown: ReturnType<typeof formatTileValue>, prevShown: ReturnType<typeof formatTileValue>|null,
 *   fmt: (v: number) => string,
 *   changeAbs: number|null, changePct: number|null, yearPct: number|null,
 *   growth: ReturnType<typeof bestGrowth>, stats: ReturnType<typeof windowStats>,
 * }}
 */
export function buildIndicatorSummary({
  points, frequency, unit, modeType, dataDigits = 2, locale = 'ru', now = new Date(),
}) {
  const valid = finitePoints(points);
  if (!valid.length) return null;
  const last = { value: Number(valid[valid.length - 1].value), date: valid[valid.length - 1].date };
  const prevRow = valid.length > 1 ? valid[valid.length - 2] : null;
  const prev = prevRow ? { value: Number(prevRow.value), date: prevRow.date } : null;
  const kind = unitKind(unit, modeType);
  const shown = formatTileValue(last.value, unit, { dataDigits, locale });
  // Предыдущее значение показываем в тех же единицах, что и текущее: «30,8 трлн» рядом с «29,3 трлн», а не «29 298 млрд».
  const prevShown = prev
    ? (shown.compacted
      ? {
        ...shown,
        text: formatValue(prev.value / shown.div, shown.digits, locale),
      }
      : formatTileValue(prev.value, unit, { dataDigits, locale }))
    : null;
  const fmt = (v) => formatValue(Number(v) / shown.div, shown.digits, locale);
  const changeAbs = prev ? last.value - prev.value : null;
  const changePct = prev && prev.value > 0 && last.value >= 0 ? (last.value / prev.value - 1) * 100 : null;
  const yearGrowth = growthOverYears(valid, 1, { maxGapDays: 120 });
  return {
    kind,
    unit: shown.unit,
    estimate: isEstimateDate(last.date, frequency, now),
    last,
    prev,
    shown,
    prevShown,
    fmt,
    changeAbs,
    changePct,
    yearPct: yearGrowth ? yearGrowth.pct : null,
    growth: kind === 'rate' ? null : bestGrowth(valid),
    stats: kind === 'rate' ? windowStats(valid, 10) : null,
  };
}
