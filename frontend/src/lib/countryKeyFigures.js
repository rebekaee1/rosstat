/**
 * Человеческая подача цифр на странице страны: крупные суммы в «млрд €», «год назад» для главных цифр,
 * пояснение к изменению словами («на 0,7 пункта ниже, чем в прошлом месяце»), технические пометки
 * («2015 = 100», «в постоянных ценах») отдельно от названия, понятные названия тем и компактные счётчики.
 */
import { formatCount, formatValue } from './format';
import { plural } from './calcFormat';

const SCALES_RU = ['тыс.', 'млн', 'млрд', 'трлн'];
const SCALES_EN = ['thousand', 'million', 'billion', 'trillion'];
const SCALE_SHORT_RU = ['тыс.', 'млн', 'млрд', 'трлн'];
const SCALE_SHORT_EN = ['thousand', 'million', 'billion', 'trillion'];

const CURRENCY_SYMBOL = Object.freeze({
  евро: '€', euro: '€', eur: '€', EUR: '€', доллар: '$', доллара: '$', usd: '$', USD: '$',
  'руб.': '₽', руб: '₽', рублей: '₽', rub: '₽', RUB: '₽',
});

/** «в постоянных ценах 2015 года, млн евро» -> { head: «в постоянных ценах 2015 года», level: 1, token: «евро» }. */
function parseScaledUnit(unitText) {
  const text = String(unitText || '').trim();
  if (!text) return null;
  const comma = text.lastIndexOf(',');
  const head = comma >= 0 ? text.slice(0, comma).trim() : '';
  const tail = (comma >= 0 ? text.slice(comma + 1) : text).trim();
  const match = tail.match(/^(тыс\.|млн|млрд|трлн|thousand|million|billion|trillion|ths)\s+(\S+)$/i);
  if (!match) return null;
  const word = match[1].toLowerCase();
  let level = SCALES_RU.indexOf(word);
  if (level < 0) level = SCALES_EN.indexOf(word);
  if (word === 'ths') level = 0;
  if (level < 0) return null;
  return { head, level, token: match[2] };
}

/**
 * Крупное число с масштабом переводит в следующий разряд: «849 680 млн евро» -> «849,7 млрд €».
 * @returns {{ value: number, unit: string, qualifier: string } | null} null — масштаба в единице нет.
 */
export function scaleMoneyUnit(value, unitText, locale = 'ru') {
  const parsed = parseScaledUnit(unitText);
  const n = Number(value);
  if (!parsed || !Number.isFinite(n)) return null;
  let { level } = parsed;
  let scaled = n;
  while (Math.abs(scaled) >= 1000 && level < 3) {
    scaled /= 1000;
    level += 1;
  }
  const symbol = CURRENCY_SYMBOL[parsed.token] || parsed.token;
  const word = (locale === 'en' ? SCALE_SHORT_EN : SCALE_SHORT_RU)[level];
  return { value: scaled, unit: `${word} ${symbol}`, qualifier: parsed.head };
}

const PLAIN_MONEY_TOKEN = /^(евро|euro|eur|usd|доллар\w*|dollars?|руб\.?|рублей|rub)$/i;

/**
 * Крупная сумма в коротком виде: 56 459 257 590 евро -> «56,5 млрд €» (круг 8, Y5).
 * Работает для единицы-валюты без масштаба («евро») от миллиона; масштабные единицы («млн евро») остаются как были.
 * @returns {{ value: number, unit: string } | null} null — сокращать нечего, показывать как есть.
 */
export function compactMoneyAmount(value, unitText, locale = 'ru') {
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  const text = String(unitText || '').trim();
  const abs = Math.abs(n);
  if (PLAIN_MONEY_TOKEN.test(text)) {
    if (abs < 1e6) return null;
    const words = locale === 'en' ? SCALE_SHORT_EN : SCALE_SHORT_RU;
    // k делений на 1000: 1 — тыс., 2 — млн, 3 — млрд, 4 — трлн.
    let k = 0;
    let scaled = n;
    while (Math.abs(scaled) >= 1000 && k < 4) { scaled /= 1000; k += 1; }
    const symbol = CURRENCY_SYMBOL[text] || CURRENCY_SYMBOL[text.toLowerCase()] || text;
    return { value: scaled, unit: `${words[Math.max(k - 1, 0)]} ${symbol}` };
  }
  return null;
}

/** Знаки после запятой для крупной цифры: 849,7 / 2,3 / 12 345. */
export function figureDigits(value) {
  const abs = Math.abs(Number(value));
  if (abs >= 1000) return 0;
  if (abs >= 1) return 1;
  return 2;
}

/** «в постоянных ценах 2015 года» -> «с поправкой на инфляцию» (без экономического жаргона). */
export function humanizeQualifier(text, t) {
  const raw = String(text || '').trim();
  if (!raw) return '';
  if (/постоянн[а-яё]*\s+цен|constant prices|chain[- ]linked|in \d{4} prices|цены \d{4}/i.test(raw)) {
    return t('z5.qual.real');
  }
  return raw;
}

function toTime(dateText) {
  const time = Date.parse(String(dateText || '').slice(0, 10));
  return Number.isFinite(time) ? time : null;
}

const DAY = 86400000;
const TOLERANCE_DAYS = { daily: 10, weekly: 20, monthly: 25, quarterly: 50, annual: 190 };

/**
 * Значение примерно год назад относительно последней точки ряда.
 * @param {Array<{date: string, value: number|string}>} points точки по возрастанию даты
 * @returns {{ value: number, date: string } | null}
 */
export function yearAgoPoint(points, frequency = 'annual') {
  if (!Array.isArray(points) || points.length < 2) return null;
  const last = points[points.length - 1];
  const lastTime = toTime(last?.date);
  if (lastTime == null) return null;
  const target = new Date(lastTime);
  target.setUTCFullYear(target.getUTCFullYear() - 1);
  const targetTime = target.getTime();
  const tolerance = (TOLERANCE_DAYS[frequency] ?? 45) * DAY;
  let best = null;
  let bestGap = Infinity;
  for (let i = points.length - 2; i >= 0; i -= 1) {
    const time = toTime(points[i]?.date);
    if (time == null) continue;
    const gap = Math.abs(time - targetTime);
    if (gap < bestGap) {
      best = points[i];
      bestGap = gap;
    }
    if (time < targetTime - tolerance) break;
  }
  const value = Number(best?.value);
  if (!best || bestGap > tolerance || !Number.isFinite(value)) return null;
  return { value, date: best.date };
}

/** Знак «минус» вместо дефиса в начале числа: «−0,08», а не «-0,08» (круг 8, Y1). */
export function typographicMinus(text) {
  return typeof text === 'string' ? text.replace(/^-(?=\d)/, '\u2212') : text;
}

/** Изменение без хвоста нулей: 0,7 вместо 0,70, 12 вместо 12,0. */
function tidyNumber(abs, locale) {
  const digits = abs < 1 ? 2 : abs < 100 ? 1 : 0;
  const rounded = Number(abs.toFixed(digits));
  if (rounded === 0) return null;
  const decimals = Number.isInteger(rounded) ? 0 : String(rounded).split('.')[1].length;
  return formatValue(rounded, decimals, locale);
}

function pointsWord(number, locale, t) {
  if (locale === 'en') return number === 1 ? t('z5.unit.point.one') : t('z5.unit.point.many');
  if (!Number.isInteger(number)) return t('z5.unit.point.few');
  const abs = Math.abs(number) % 100;
  const last = abs % 10;
  if (abs > 10 && abs < 20) return t('z5.unit.point.many');
  if (last === 1) return t('z5.unit.point.one');
  if (last >= 2 && last <= 4) return t('z5.unit.point.few');
  return t('z5.unit.point.many');
}

const POINT_UNIT = /^(%|индекс|index|пункт|point)/i;

/**
 * Одна строка «что это значит»: «на 0,7 пункта ниже, чем в прошлом месяце».
 * Знак и цвет задаёт вызывающий (DeltaBadge): здесь только слова.
 * @returns {string} пусто, если изменение не выражается (нет числа или оно округляется до нуля)
 */
export function describeChange({ change, unit, frequency, locale = 'ru', t }) {
  const n = Number(change);
  if (change == null || !Number.isFinite(n)) return '';
  const abs = Math.abs(n);
  const unitText = String(unit || '').trim();
  // Суммы в рублях и евро печатаем коротко («11,9 млрд €»), а не двенадцатью цифрами.
  const compact = compactMoneyAmount(abs, unitText, locale);
  const number = tidyNumber(compact ? compact.value : abs, locale);
  if (number == null) return t('z5.chg.none');
  const rounded = Number(abs.toFixed(abs < 1 ? 2 : abs < 100 ? 1 : 0));
  let suffix = '';
  if (compact) suffix = ` ${compact.unit}`;
  else if (!unitText) suffix = '';
  else if (POINT_UNIT.test(unitText)) suffix = ` ${pointsWord(rounded, locale, t)}`;
  else suffix = ` ${unitText}`;
  const amount = `${number}${suffix}`;
  const direction = n > 0 ? t('z5.chg.higher') : t('z5.chg.lower');
  const line = t('z5.chg.line', { amount, direction });
  const key = ['daily', 'weekly', 'monthly', 'quarterly', 'annual'].includes(frequency)
    ? `z5.chg.vs.${frequency}`
    : 'z5.chg.vs.default';
  return `${line}, ${t(key)}`;
}

/**
 * Отделяет от названия и единицы технические пометки: «(2015 = 100)», «цены 2017», «в постоянных ценах».
 * Названия остаются читаемыми, а пометка уходит в подсказку «i».
 * @returns {{ name: string, unit: string, note: string }}
 */
export function splitTechnicalNote(name, unit) {
  const notes = [];
  let cleanName = String(name || '').trim();
  let cleanUnit = String(unit || '').trim();
  const base = /\s*(?:[([]|,\s*)?\s*(?:база\s+|base\s+)?((?:19|20)\d{2})\s*=\s*100\s*[)\]]?/i;
  const prices = /\s*[(,]?\s*(?:(?:в\s+)?(?:постоянных\s+ценах|цены|constant prices)\s*\(?(?:19|20)\d{2}\)?(?:\s+года)?|in\s+(?:19|20)\d{2}\s+prices)\s*\)?/i;
  const strip = (text) => {
    let out = text;
    const b = out.match(base);
    if (b) { notes.push(`${b[1]} = 100`); out = out.replace(base, ''); }
    const p = out.match(prices);
    if (p) { notes.push(p[0].replace(/^[\s(,]+|[\s)]+$/g, '')); out = out.replace(prices, ''); }
    return out.replace(/\s+,/g, ',').replace(/,\s*$/, '').replace(/\s{2,}/g, ' ').trim();
  };
  const nextName = strip(cleanName);
  const nextUnit = strip(cleanUnit);
  if (nextName) cleanName = nextName;
  cleanUnit = nextUnit;
  return { name: cleanName, unit: cleanUnit, note: [...new Set(notes)].join(', ') };
}

/** Счётчик темы мелко и коротко: 499 -> «499», 2197 -> «2 тыс.»; точное число — в подсказке. */
export function compactCount(n, locale = 'ru') {
  const value = Number(n);
  if (!Number.isFinite(value)) return '';
  if (value < 1000) return formatValue(value, 0, locale);
  const thousands = value / 1000;
  const rounded = Number(thousands.toFixed(thousands >= 10 ? 0 : 1));
  const text = formatValue(rounded, Number.isInteger(rounded) ? 0 : 1, locale);
  return locale === 'en' ? `${text}k` : `${text}\u00a0тыс.`;
}

/** Понятные названия тем вместо бухгалтерских («Национальные счета» -> «ВВП и рост»). */
const FRIENDLY_TOPICS = Object.freeze({
  'Национальные счета': { ru: 'ВВП и рост', en: 'GDP and growth' },
  'Государственные финансы': { ru: 'Деньги и бюджет', en: 'Money and budget' },
});

/** Главные темы получают золотую точку. */
export const MAIN_TOPIC_NAMES = Object.freeze(['Национальные счета', 'Цены', 'Рынок труда']);

export function isMainTopic(category) {
  return MAIN_TOPIC_NAMES.includes(category?.name_ru || category?.name);
}

export function topicDisplayName(category, locale = 'ru') {
  const key = category?.name_ru || category?.name;
  const friendly = FRIENDLY_TOPICS[key];
  if (friendly) return locale === 'en' ? friendly.en : friendly.ru;
  if (locale === 'en') return category?.name_en || category?.name || '';
  return category?.name || '';
}

/** Страны того же региона мира для блока «Похожие страны»: самые полные по данным первыми. */
export function similarCountries(catalog, current, limit = 5) {
  const list = Array.isArray(catalog?.countries) ? catalog.countries : [];
  if (!current?.slug) return [];
  const region = current.region;
  return list
    .filter((country) => country?.slug && country.slug !== current.slug && country.region === region)
    .sort((a, b) => Number(b.indicators_count || 0) - Number(a.indicators_count || 0))
    .slice(0, limit);
}

/** «24 показателя» / «1 indicator»: число с правильным словом. */
export function indicatorsCountText(n, locale, t) {
  const value = Number(n) || 0;
  const form = locale === 'en' ? (value === 1 ? 'one' : 'many') : plural(value, 'one', 'few', 'many');
  return `${formatCount(value, locale)} ${t(`w3.count.indicators.${form}`)}`;
}
