// Чистая логика раздела «Курсы валют и криптовалют»: названия пар по-человечески, вкладки,
import { numberTag } from './format';
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
  // Рублёвые курсы, которые ищут чаще (08.11.2026): соседи и партнёры, затем мировые резервные.
  'kzt-rub', 'byn-rub', 'try-rub', 'uzs-rub', 'kgs-rub', 'amd-rub', 'tjs-rub', 'gel-rub', 'azn-rub',
  'aed-rub', 'gbp-rub', 'jpy-rub', 'chf-rub', 'inr-rub', 'thb-rub', 'vnd-rub', 'krw-rub', 'egp-rub',
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
/**
 * Сколько единиц валюты в одной точке ряда. У мелких валют Банк России даёт курс за 100, 1 000, 10 000
 * единиц (иена, вона, сум), и ряд хранится так же: единица ряда «руб. за 10 000». Иначе — 1.
 */
export function quoteUnitsOf(unit) {
  // Русская подпись «руб. за 10 000» и английская «RUB per 10,000»: без второй английская версия считала донг и рупию в 10 000 раз мимо.
  const match = /(?:за|per)\s*(\d[\d\s\u00a0\u202f,]*)/i.exec(String(unit || ''));
  if (!match) return 1;
  const n = Number(match[1].replace(/[\s\u00a0\u202f,]/g, ''));
  return Number.isFinite(n) && n > 0 ? n : 1;
}

export function buildEdges(indicators) {
  const edges = [];
  for (const item of indicators || []) {
    const pair = parsePair(item?.code);
    const rate = Number(item?.current_value) / quoteUnitsOf(item?.unit);
    if (!pair || !Number.isFinite(rate) || rate <= 0 || item.is_active === false) continue;
    edges.push({
      from: pair.base, to: pair.quote, rate, date: item.current_date || null, code: item.code, units: quoteUnitsOf(item?.unit),
    });
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

/**
 * Число из поля ввода: пробелы и неразрывные пробелы убираются, запятая = точка.
 * Круг 11 (E): на английской версии запятая отделяет тысячи («10,000»), а не дробь, потому что так её пишет само поле.
 */
export function parseAmountInput(text, locale = 'ru') {
  const raw = String(text ?? '').replace(/\s/g, '');
  const cleaned = locale === 'en' ? raw.replace(/,/g, '') : raw.replace(',', '.');
  if (!cleaned || !/^\d*\.?\d*$/.test(cleaned)) return null;
  const value = Number(cleaned);
  return Number.isFinite(value) ? value : null;
}

/** Валюты «в дорогу»: сначала то, что берут с собой или переводят чаще всего. Показываются быстрыми кнопками в конвертере. */
export const TRAVEL_UNITS = ['TJS', 'UZS', 'KGS', 'KZT', 'AMD', 'BYN', 'AED', 'TRY', 'GEL', 'THB'];
/** Для раздела курсов: те же валюты «в дорогу» плюс те, что берут в отпуск (донг, египетский фунт). Главная остаётся на TRAVEL_UNITS. */
export const TRIP_UNITS = [...TRAVEL_UNITS, 'VND', 'EGP'];

// Страны и названия на двух языках: по ним валюта находится в поиске («узбекистан», «uzbek», «дубай», «dirham»).
const SEARCH_ALIASES = {
  KZT: 'казахстан kazakhstan тенге tenge алматы астана almaty astana',
  BYN: 'беларусь белоруссия belarus белорусский рубль',
  UZS: 'узбекистан uzbekistan uzbek сум сумы som ташкент самарканд tashkent',
  TRY: 'турция turkey turkiye turkish лира lira стамбул istanbul анталья antalya аланья бодрум мармарис кемер',
  AMD: 'армения armenia драм dram ереван yerevan',
  KGS: 'киргизия кыргызстан kyrgyzstan kyrgyz сом som',
  AED: 'оаэ эмираты дубай абу-даби абу даби шарджа dubai uae emirates дирхам dirham',
  GEL: 'грузия georgia лари lari тбилиси батуми tbilisi batumi',
  THB: 'таиланд тайланд thailand бат baht пхукет паттайя бангкок самуи phuket pattaya bangkok',
  AZN: 'азербайджан azerbaijan манат manat',
  TJS: 'таджикистан tajikistan сомони somoni',
  MDL: 'молдова moldova лей leu',
  CNY: 'китай china юань yuan renminbi',
  JPY: 'япония japan иена йена yen',
  KRW: 'корея korea вона won',
  INR: 'индия india рупия rupee',
  VND: 'вьетнам vietnam донг dong нячанг фукуок хошимин nha trang phu quoc',
  EGP: 'египет egypt фунт pound хургада шарм эль шейх каир hurghada sharm',
  RSD: 'сербия serbia динар dinar',
  CHF: 'швейцария switzerland франк franc',
  PLN: 'польша poland злотый zloty',
  CZK: 'чехия czech крона koruna',
  HKD: 'гонконг hong kong',
  USD: 'сша америка usa america dollar',
  EUR: 'европа евросоюз europe euro',
  GBP: 'англия великобритания britain england pound стерлингов',
};

/** Строка поиска по валюте (нижний регистр): код, названия, знак, страна. */
export function currencySearchText(unit) {
  const meta = unitMeta(unit);
  return [unit, meta?.ru, meta?.en, meta?.symbol, SEARCH_ALIASES[unit]].filter(Boolean).join(' ').toLowerCase().replace(/ё/g, 'е');
}

// Формы для «10 000 сумов»: одна, две–четыре, пять и больше. Нет в списке: код валюты.
const RU_FORMS = {
  RUB: ['₽', '₽', '₽'], USD: ['$', '$', '$'], EUR: ['€', '€', '€'], GBP: ['£', '£', '£'],
  CNY: ['юань', 'юаня', 'юаней'], UZS: ['сум', 'сума', 'сумов'], KZT: ['тенге', 'тенге', 'тенге'],
  AMD: ['драм', 'драма', 'драмов'], AED: ['дирхам', 'дирхама', 'дирхамов'], KGS: ['сом', 'сома', 'сомов'],
  GEL: ['лари', 'лари', 'лари'], TRY: ['лира', 'лиры', 'лир'], BYN: ['бел. рубль', 'бел. рубля', 'бел. рублей'],
  THB: ['бат', 'бата', 'бат'], JPY: ['иена', 'иены', 'иен'], KRW: ['вона', 'воны', 'вон'],
  INR: ['рупия', 'рупии', 'рупий'], AZN: ['манат', 'маната', 'манатов'], MDL: ['лей', 'лея', 'леев'],
  TJS: ['сомони', 'сомони', 'сомони'], VND: ['донг', 'донга', 'донгов'], CHF: ['франк', 'франка', 'франков'],
  PLN: ['злотый', 'злотых', 'злотых'], CZK: ['крона', 'кроны', 'крон'], EGP: ['фунт', 'фунта', 'фунтов'],
  RSD: ['динар', 'динара', 'динаров'],
};

/** Единица рядом с числом: «сумов», «сума», «₽». Английская версия: знак или код. */
export function unitWord(count, unit, locale = 'ru') {
  if (locale === 'en') return ['RUB', 'USD', 'EUR', 'GBP'].includes(unit) ? unitMeta(unit).symbol : unit;
  const forms = RU_FORMS[unit];
  if (!forms) return unit;
  const n = Math.abs(Number(count));
  if (!Number.isInteger(n)) return forms[1];
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return forms[1];
  return forms[2];
}

const HEAD_UNITS = ['RUB', 'USD', 'EUR', 'CNY', 'GBP', 'BTC', 'ETH', 'SOL'];

/**
 * За сколько единиц показывать курс: у мелких валют, как у Банка России, за 100, 1 000, 10 000 (чтобы число было не меньше 10).
 * У привычных валют (рубль, доллар, евро…) и у курса от одной единицы и выше: 1.
 */
export function nominalFor(unit, perOne) {
  const r = Math.abs(Number(perOne));
  if (HEAD_UNITS.includes(unit) || !(r > 0) || r >= 1) return 1;
  let n = 1;
  while (n * r < 10 && n < 1e9) n *= 10;
  return n;
}

/** Пресеты суммы под валюту «Из»: у мелких валют (сум, тенге) круглые суммы на сотни и тысячи рублей, а не «1» и «100». */
export function amountPresets(from, edges) {
  const legacy = { list: [1, 100, 1000, 10000], initial: 100 };
  // Рубли в руках: отправить семье или поменять в дорогу — тысячи, а не «100 ₽».
  if (from === 'RUB') return { list: [1000, 5000, 10000, 50000], initial: 10000 };
  if (!from || HEAD_UNITS.includes(from)) return legacy;
  const rub = convert(1, from, 'RUB', edges)?.value;
  if (!(rub > 0) || rub >= 0.3) return legacy;
  const e = Math.max(2, Math.ceil(Math.log10(100 / rub) - 1e-9));
  const list = [10 ** e, 10 ** (e + 1), 10 ** (e + 2)];
  return { list, initial: list[1] };
}

/**
 * Строки курса для конвертера. Привычные пары: «1 USD = 80,00 RUB». Мелкие валюты по-человечески:
 * «10 000 сумов = 68,60 ₽» и «1 ₽ = 145,77 сума». Нет пути между валютами: null.
 */
export function describeRate(from, to, edges, locale = 'ru') {
  const forward = convert(1, from, to, edges);
  const back = convert(1, to, from, edges);
  if (!forward || !back) return null;
  const nA = nominalFor(from, forward.value);
  const nB = nominalFor(to, back.value);
  if (nA === 1 && nB === 1) {
    return { lines: [`1 ${from} = ${formatRate(forward.value, locale)} ${to}`], nominal: 1 };
  }
  const tag = numberTag(locale);
  const money = (v) => new Intl.NumberFormat(tag, {
    minimumFractionDigits: v >= 1000 ? 0 : 2, maximumFractionDigits: v >= 1000 ? 0 : 2,
  }).format(v);
  const line = (a, b, n, rate) => {
    const left = new Intl.NumberFormat(tag).format(n).replace(/\u202f/g, '\u00a0');
    const value = rate * n;
    return `${left}\u00a0${unitWord(n, a, locale)} = ${money(value)}\u00a0${unitWord(value, b, locale)}`;
  };
  return { lines: [line(from, to, nA, forward.value), line(to, from, nB, back.value)], nominal: Math.max(nA, nB) };
}

/** Курс в строке «1 USD = …»: знаков по величине (80,00; 0,0117; 0,000012), без «0,01169849». */
export function formatRate(value, locale = 'ru') {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  const abs = Math.abs(n);
  let digits = 2;
  if (abs >= 1000) digits = 0;
  else if (abs >= 1) digits = 2;
  else if (abs >= 0.01) digits = 4;
  else if (abs >= 0.0001) digits = 6;
  else digits = 8;
  return new Intl.NumberFormat(numberTag(locale), {
    minimumFractionDigits: digits === 8 ? 0 : digits, maximumFractionDigits: digits,
  }).format(n);
}

/** Результат пересчёта по правилам языка: крупные суммы целыми, обычные с копейками, доли монеты с точностью. */
export function formatConverted(value, locale = 'ru', { money = false } = {}) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  const abs = Math.abs(n);
  let min = 2;
  let max = 2;
  if (abs >= 1000) { min = 0; max = 0; } else if (abs > 0 && abs < 1) { min = 2; max = money ? (abs >= 0.01 ? 2 : 4) : 8; }
  return new Intl.NumberFormat(numberTag(locale), {
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
