/**
 * Блок «Мир сейчас» на главной: четыре крупных факта из срезов, которые главная и так уже загрузила
 * (ВВП, инфляция, безработица): крупнейшая экономика, самая быстрая инфляция, самая низкая безработица
 * и «домашняя» страна (Россия на русском сайте, США на английском). Новых запросов нет, всё считается из `items`.
 *
 * Для каждого факта считаем «лесенку»: столбики всех стран каталога в порядке рейтинга, чтобы человек
 * видел, где эта страна стоит среди остальных, а не просто число.
 */
import { billionsOf } from './countryFacts';
import { formatValue } from './format';

const NBSP = ' ';
/** Сколько столбиков рисуем в лесенке: больше не нужно, а лёгкая разметка важнее. */
const MAX_BARS = 64;

function finiteItems(snapshot, pick = (value) => value) {
  const out = [];
  for (const item of snapshot?.items || []) {
    const raw = item?.value;
    if (raw == null || raw === '' || !item?.country_code) continue;
    const value = pick(Number(raw), item);
    if (Number.isFinite(value)) out.push({ item, value });
  }
  return out;
}

/** Год из даты наблюдения («2025-12-31» → 2025); пусто, если даты нет. */
export function yearOfItem(item) {
  const match = /^(\d{4})/.exec(String(item?.date || ''));
  return match ? Number(match[1]) : null;
}

/**
 * Высоты столбиков 0..1 по значениям в порядке рейтинга. Масштаб логарифмический для денег (США и Тувалу
 * иначе несравнимы) и линейный с «потолком» для процентов (одна страна с инфляцией 200 % не сплющит остальных).
 */
export function ladderHeights(values, { log = false } = {}) {
  const list = values.filter(Number.isFinite);
  if (!list.length) return [];
  const prepared = log ? list.map((v) => Math.log10(Math.max(v, 1e-6))) : list;
  const sorted = [...prepared].sort((a, b) => a - b);
  const low = sorted[0];
  const capIndex = Math.min(sorted.length - 1, Math.floor(sorted.length * 0.94));
  const high = Math.max(sorted[capIndex], low + 1e-9);
  return prepared.map((v) => {
    const share = (Math.min(v, high) - low) / (high - low);
    return Math.round((0.14 + 0.86 * Math.max(0, Math.min(1, share))) * 1000) / 1000;
  });
}

/** Разбивка суммы на крупное число и единицу: «30,8» + «трлн $», в английском «$30.8» + «trillion». */
export function splitEconomy(valueBn, locale = 'ru') {
  const bn = Number(valueBn);
  if (!Number.isFinite(bn) || bn <= 0) return null;
  const en = locale === 'en';
  if (bn >= 1000) {
    const num = formatValue(bn / 1000, 1, locale);
    return en ? { num: `$${num}`, unit: 'trillion' } : { num, unit: `трлн${NBSP}$` };
  }
  if (bn >= 1) {
    const num = formatValue(bn, bn >= 10 ? 0 : 1, locale);
    return en ? { num: `$${num}`, unit: 'billion' } : { num, unit: `млрд${NBSP}$` };
  }
  const num = formatValue(bn * 1000, 0, locale);
  return en ? { num: `$${num}`, unit: 'million' } : { num, unit: `млн${NBSP}$` };
}

/** «3,4» + «%». */
export function splitPercent(value, locale = 'ru') {
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return { num: formatValue(n, 1, locale), unit: '%' };
}

/**
 * Лесенка и положение страны в ней. `entries` уже отсортированы по рейтингу (место 1 слева).
 * @returns {{ bars: number[], mark: number, rank: number, total: number } | null}
 */
function buildLadder(entries, code, { log = false } = {}) {
  const at = entries.findIndex((entry) => entry.item.country_code === code);
  if (at < 0) return null;
  let heights = ladderHeights(entries.map((entry) => entry.value), { log });
  let mark = at;
  if (heights.length > MAX_BARS) {
    // Лишних стран в каталоге нет, но лесенка не должна расти без границ: берём каждую k-ю, выбранную сохраняем.
    const step = Math.ceil(heights.length / MAX_BARS);
    const kept = heights.map((height, index) => ({ height, index }))
      .filter(({ index }) => index % step === 0 || index === at);
    heights = kept.map((entry) => entry.height);
    mark = kept.findIndex((entry) => entry.index === at);
  }
  return { bars: heights, mark, rank: at + 1, total: entries.length };
}

function nameOf(item, countriesByCode, localeName) {
  const catalog = countriesByCode?.get(item.country_code);
  return (catalog && localeName(catalog)) || item.country_name || item.country_code;
}

/**
 * @param {object} args
 * @param {object} args.gdp срез «ВВП, $» (compare/snapshot/gdp-usd)
 * @param {object} args.inflation срез инфляции (hicp-index)
 * @param {object} args.unemployment срез безработицы
 * @param {string} args.locale 'ru' | 'en'
 * @param {Map} [args.countriesByCode] каталог стран по коду: даёт название на языке сайта
 * @param {(country: object) => string} [args.localeName] как назвать страну каталога
 * @returns {object[]} до четырёх плиток; пустой массив, если данных не хватает
 */
export function buildTodayTiles({
  gdp, inflation, unemployment, locale = 'ru', countriesByCode = null, localeName = (country) => country?.name || '',
} = {}) {
  const tiles = [];

  const sizes = finiteItems(gdp, (value, item) => billionsOf(value, item.unit))
    .filter((entry) => entry.value > 0)
    .sort((a, b) => b.value - a.value);
  if (sizes.length >= 3) {
    const top = sizes[0];
    const ladder = buildLadder(sizes, top.item.country_code, { log: true });
    const shown = splitEconomy(top.value, locale);
    if (ladder && shown) {
      tiles.push({
        id: 'economy', concept: 'gdp-usd', item: top.item, value: shown, year: yearOfItem(top.item),
        country: nameOf(top.item, countriesByCode, localeName), ladder,
      });
    }
  }

  const prices = finiteItems(inflation).sort((a, b) => b.value - a.value);
  if (prices.length >= 3) {
    const top = prices[0];
    const ladder = buildLadder(prices, top.item.country_code);
    const shown = splitPercent(top.value, locale);
    if (ladder && shown) {
      tiles.push({
        id: 'prices', concept: 'hicp-index', item: top.item, value: shown, year: yearOfItem(top.item),
        country: nameOf(top.item, countriesByCode, localeName), ladder,
      });
    }
  }

  const jobs = finiteItems(unemployment).filter((entry) => entry.value > 0).sort((a, b) => a.value - b.value);
  if (jobs.length >= 3) {
    const top = jobs[0];
    const ladder = buildLadder(jobs, top.item.country_code);
    const shown = splitPercent(top.value, locale);
    if (ladder && shown) {
      tiles.push({
        id: 'jobs', concept: 'unemployment-rate', item: top.item, value: shown, year: yearOfItem(top.item),
        country: nameOf(top.item, countriesByCode, localeName), ladder,
      });
    }
  }

  // Домашняя страна: Россия на русском сайте, США на английском. Нет в срезе: «обычная страна» (середина рейтинга).
  if (prices.length >= 3) {
    const homeCode = locale === 'en' ? 'US' : 'RU';
    const home = prices.find((entry) => entry.item.country_code === homeCode);
    if (home) {
      const ladder = buildLadder(prices, homeCode);
      const shown = splitPercent(home.value, locale);
      if (ladder && shown) {
        tiles.push({
          id: 'home', concept: 'hicp-index', item: home.item, value: shown, year: yearOfItem(home.item),
          country: nameOf(home.item, countriesByCode, localeName), ladder,
        });
      }
    } else {
      const middle = prices[Math.floor(prices.length / 2)];
      const ladder = buildLadder(prices, middle.item.country_code);
      const shown = splitPercent(middle.value, locale);
      if (ladder && shown) {
        tiles.push({
          id: 'median', concept: 'hicp-index', item: middle.item, value: shown, year: yearOfItem(middle.item),
          country: null, ladder, total: prices.length,
        });
      }
    }
  }
  return tiles;
}

/**
 * Цвет-маркер рядом с цифрой в карточке страны: зелёный «в норме», янтарный «внимание», красный «тревожно».
 * Пороги простые и общепринятые: инфляция до 4 % за год спокойна, выше 10 % тревожна, дефляция настораживает;
 * безработица до 5 % низкая, выше 9 % высокая. Нет числа, нет и маркера.
 * @returns {'good'|'warn'|'bad'|null}
 */
export function metricTone(kind, value) {
  if (value == null || value === '') return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  if (kind === 'inflation') {
    if (n < 0) return 'warn';
    if (n <= 4) return 'good';
    return n <= 10 ? 'warn' : 'bad';
  }
  if (kind === 'unemployment') {
    if (n <= 5) return 'good';
    return n <= 9 ? 'warn' : 'bad';
  }
  return null;
}

/** Направление линии истории для спарклайна карточки: последняя точка против точки пять шагов назад (±2 % считается «ровно»). */
export function sparkTrend(points) {
  const list = (points || []).map(Number).filter(Number.isFinite);
  if (list.length < 3) return 'flat';
  const last = list[list.length - 1];
  const before = list[Math.max(0, list.length - 6)];
  if (!before) return last > 0 ? 'up' : 'flat';
  const change = (last - before) / Math.abs(before);
  if (change > 0.02) return 'up';
  return change < -0.02 ? 'down' : 'flat';
}
