// Чистая логика раздела «Курсы валют и криптовалют»: названия пар по-человечески, вкладки,
// конвертер через общий граф курсов и изменения за неделю / месяц / год для страницы курса.

/** Валюты и монеты: название, форма «к чему» (для «Доллар к рублю») и значок. */
export const UNITS = {
  RUB: { ru: 'Рубль', en: 'Ruble', ruTo: 'рублю', enTo: 'ruble', symbol: '₽', flag: '🇷🇺', digits: 2 },
  USD: { ru: 'Доллар США', en: 'US dollar', ruTo: 'доллару США', enTo: 'US dollar', symbol: '$', flag: '🇺🇸', digits: 2 },
  EUR: { ru: 'Евро', en: 'Euro', ruTo: 'евро', enTo: 'euro', symbol: '€', flag: '🇪🇺', digits: 2 },
  CNY: { ru: 'Китайский юань', en: 'Chinese yuan', ruTo: 'китайскому юаню', enTo: 'Chinese yuan', symbol: '¥', flag: '🇨🇳', digits: 2 },
  GBP: { ru: 'Фунт стерлингов', en: 'Pound sterling', ruTo: 'фунту стерлингов', enTo: 'pound sterling', symbol: '£', flag: '🇬🇧', digits: 2 },
  BTC: { ru: 'Биткоин', en: 'Bitcoin', ruTo: 'биткоину', enTo: 'bitcoin', symbol: '₿', flag: '', digits: 8, crypto: true },
  ETH: { ru: 'Эфириум', en: 'Ethereum', ruTo: 'эфириуму', enTo: 'ether', symbol: 'Ξ', flag: '', digits: 6, crypto: true },
  SOL: { ru: 'Солана', en: 'Solana', ruTo: 'солане', enTo: 'solana', symbol: 'SOL', flag: '', digits: 6, crypto: true },
};

// Круг 9 (V1): валюты, которых нет в списке выше (лира, тенге, дирхам, иена…), подхватываются по коду пары из ответа API:
// имя, знак и флаг берутся из системных справочников браузера (Intl), без отдельной записи на каждую валюту.
const derivedCache = new Map();
let displayRu = null;
let displayEn = null;

function currencyNames() {
  if (displayRu === null) {
    try {
      displayRu = new Intl.DisplayNames(['ru'], { type: 'currency', fallback: 'none' });
      displayEn = new Intl.DisplayNames(['en'], { type: 'currency', fallback: 'none' });
    } catch {
      displayRu = false;
      displayEn = false;
    }
  }
  return displayRu ? { ru: displayRu, en: displayEn } : null;
}

function capitalize(text) {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

/** Флаг по первым двум буквам кода валюты (TRY -> TR, KZT -> KZ); у наднациональных кодов (X…) флага нет. */
function flagOfCode(code) {
  if (code.startsWith('X')) return '';
  return String.fromCodePoint(...[...code.slice(0, 2)].map((ch) => 0x1f1e6 + ch.charCodeAt(0) - 65));
}

function symbolOfCode(code) {
  try {
    const part = new Intl.NumberFormat('en', { style: 'currency', currency: code, currencyDisplay: 'narrowSymbol' })
      .formatToParts(0).find((item) => item.type === 'currency');
    return part?.value || code;
  } catch {
    return code;
  }
}

/** Описание единицы: из словаря выше или, для другой настоящей валюты по коду ISO, собранное из справочников. Нет: null. */
export function unitMeta(code) {
  const key = String(code || '').toUpperCase();
  if (UNITS[key]) return UNITS[key];
  if (!/^[A-Z]{3}$/.test(key)) return null;
  if (derivedCache.has(key)) return derivedCache.get(key);
  let meta = null;
  const names = currencyNames();
  const ru = names?.ru.of(key);
  const en = names?.en.of(key);
  if (ru && en) {
    meta = {
      ru: capitalize(ru), en, ruTo: null, enTo: en, symbol: symbolOfCode(key), flag: flagOfCode(key), digits: 2, derived: true,
    };
  }
  derivedCache.set(key, meta);
  return meta;
}

/** Порядок «по популярности»: сначала то, что ищут чаще всего. */
export const POPULARITY = [
  'usd-rub', 'eur-rub', 'cny-rub',
  'btc-usd', 'eth-usd', 'sol-usd',
  'eur-usd', 'gbp-usd', 'usd-cny', 'gbp-eur', 'cny-eur',
];

const PAIR_RE = /^([a-z]{3})-([a-z]{3})$/;

/** `usd-rub` -> { base: 'USD', quote: 'RUB' }; производные ряды (`usd-rub-eop-month`) и прочее -> null. */
export function parsePair(code) {
  const match = PAIR_RE.exec(String(code || ''));
  if (!match) return null;
  const base = match[1].toUpperCase();
  const quote = match[2].toUpperCase();
  return unitMeta(base) && unitMeta(quote) ? { base, quote } : null;
}

/** «Доллар США к рублю», «Биткоин в долларах», «US dollar to ruble». Неизвестная пара: исходное название. */
export function pairTitle(code, locale = 'ru', fallback = '') {
  const pair = parsePair(code);
  if (!pair) return fallback;
  const base = unitMeta(pair.base);
  const quote = unitMeta(pair.quote);
  // Для валюты без готовой формы «к чему» (её нет в словаре) название строим без падежа: «Тенге / Доллар США».
  if (!quote.ruTo && locale !== 'en') return fallback || `${base.ru} / ${quote.ru}`;
  if (locale === 'en') {
    return base.crypto
      ? `${base.en} in ${quote.enTo === 'US dollar' ? 'US dollars' : quote.enTo}`
      : `${base.en} to ${quote.enTo}`;
  }
  return base.crypto
    ? `${base.ru} в ${pair.quote === 'USD' ? 'долларах США' : quote.ruTo}`
    : `${base.ru} к ${quote.ruTo}`;
}

/** Вкладка пары: рубль, крипто или мир. */
export function pairTab(code) {
  const pair = parsePair(code);
  if (!pair) return 'world';
  if (unitMeta(pair.base).crypto) return 'crypto';
  return pair.quote === 'RUB' ? 'rub' : 'world';
}

export const CURRENCY_TABS = ['rub', 'crypto', 'world'];

/** Сортировка «по популярности»; неизвестные коды в конце в исходном порядке. */
export function sortByPopularity(items, getCode = (item) => item.code) {
  const rank = (item) => {
    const index = POPULARITY.indexOf(getCode(item));
    return index === -1 ? POPULARITY.length : index;
  };
  return items
    .map((item, order) => ({ item, order }))
    .sort((a, b) => rank(a.item) - rank(b.item) || a.order - b.order)
    .map((entry) => entry.item);
}

/** Откуда число: курс ЦБ России, курс ЕЦБ или закрытие дня (крипто). Ключ i18n-подписи. */
export function rateBasis(code) {
  const pair = parsePair(code);
  if (!pair) return null;
  if (unitMeta(pair.base).crypto) return 'close';
  return pair.quote === 'RUB' ? 'cb' : 'ecb';
}

/**
 * Курсы из списка показателей раздела: [{ code, current_value, current_date, is_active }].
 * Возвращает рёбра графа: 1 base = rate quote.
 */
export function buildEdges(indicators) {
  const edges = [];
  for (const item of indicators || []) {
    const pair = parsePair(item?.code);
    const rate = Number(item?.current_value);
    if (!pair || !Number.isFinite(rate) || rate <= 0 || item.is_active === false) continue;
    edges.push({ from: pair.base, to: pair.quote, rate, date: item.current_date || null, code: item.code });
  }
  return edges;
}

/**
 * Все единицы, между которыми можно пересчитать: рубль первым, затем привычные валюты, потом остальные
 * (новые валюты из ответа API) в порядке появления пар, монеты в конце.
 */
export function convertibleUnits(edges) {
  const present = new Set();
  const seen = [];
  edges.forEach((edge) => {
    [edge.from, edge.to].forEach((unit) => {
      if (!present.has(unit)) { present.add(unit); seen.push(unit); }
    });
  });
  const head = ['RUB', 'USD', 'EUR', 'CNY', 'GBP'];
  const tail = ['BTC', 'ETH', 'SOL'];
  const extra = seen.filter((unit) => !head.includes(unit) && !tail.includes(unit));
  return [...head, ...extra, ...tail].filter((unit) => present.has(unit));
}

/**
 * Пересчёт суммы по кратчайшей цепочке курсов (например BTC -> USD -> RUB).
 * @returns {{ value: number, path: string[], date: string|null } | null}
 */
export function convert(amount, from, to, edges) {
  const value = Number(amount);
  if (!Number.isFinite(value) || !from || !to) return null;
  if (from === to) return { value, path: [], date: null };
  // Поиск в ширину: рёбра двусторонние (прямой курс и обратный).
  const queue = [{ unit: from, factor: 1, path: [], dates: [] }];
  const seen = new Set([from]);
  while (queue.length) {
    const node = queue.shift();
    for (const edge of edges) {
      let next = null;
      let factor = node.factor;
      if (edge.from === node.unit) { next = edge.to; factor *= edge.rate; }
      else if (edge.to === node.unit) { next = edge.from; factor /= edge.rate; }
      if (!next || seen.has(next)) continue;
      const step = { unit: next, factor, path: [...node.path, edge.code], dates: [...node.dates, edge.date].filter(Boolean) };
      if (next === to) {
        const date = step.dates.length ? [...step.dates].sort()[0] : null;
        return { value: value * factor, path: step.path, date };
      }
      seen.add(next);
      queue.push(step);
    }
  }
  return null;
}

/** Число из поля ввода: пробелы и неразрывные пробелы убираются, запятая = точка. */
export function parseAmountInput(text) {
  const cleaned = String(text ?? '').replace(/\s/g, '').replace(',', '.');
  if (!cleaned || !/^\d*\.?\d*$/.test(cleaned)) return null;
  const value = Number(cleaned);
  return Number.isFinite(value) ? value : null;
}

/** Результат пересчёта по правилам языка: крупные суммы целыми, обычные с копейками, доли монеты с точностью. */
export function formatConverted(value, locale = 'ru') {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  const abs = Math.abs(n);
  let min = 2;
  let max = 2;
  if (abs >= 1000) { min = 0; max = 0; } else if (abs > 0 && abs < 1) { min = 2; max = 8; }
  return new Intl.NumberFormat(locale === 'en' ? 'en-US' : 'ru-RU', {
    minimumFractionDigits: min, maximumFractionDigits: max,
  }).format(n);
}

const DAY = 24 * 60 * 60 * 1000;

function pointAtOrBefore(points, targetMs) {
  let found = null;
  for (const point of points) {
    const ms = Date.parse(point.date);
    if (!Number.isFinite(ms)) continue;
    if (ms <= targetMs) found = point;
    else break;
  }
  return found;
}

/**
 * Для страницы курса: изменение за неделю, месяц и год (в процентах) и размах за последний год.
 * points: [{ date, value }] по возрастанию даты. Нет данных на нужную глубину: поле null.
 */
export function currencyWindows(points) {
  const list = (points || [])
    .filter((p) => p?.date && Number.isFinite(Number(p.value)))
    .map((p) => ({ date: p.date, value: Number(p.value) }))
    .sort((a, b) => (a.date < b.date ? -1 : 1));
  if (list.length < 2) return null;
  const last = list[list.length - 1];
  const lastMs = Date.parse(last.date);
  const change = (days) => {
    const prev = pointAtOrBefore(list, lastMs - days * DAY);
    if (!prev || prev.value === 0) return null;
    return ((last.value / prev.value) - 1) * 100;
  };
  const yearAgo = lastMs - 365 * DAY;
  const lastYear = list.filter((p) => Date.parse(p.date) >= yearAgo);
  let min = null;
  let max = null;
  for (const p of lastYear) {
    if (!min || p.value < min.value) min = p;
    if (!max || p.value > max.value) max = p;
  }
  return {
    last,
    week: change(7),
    month: change(30),
    year: change(365),
    min,
    max,
  };
}

/** «USD/RUB exchange rate»: единый регистр английского названия курса. */
export function normalizeRateNameEn(name) {
  const text = String(name || '').trim();
  if (!text) return text;
  return text.replace(/exchange rate/i, 'exchange rate');
}
