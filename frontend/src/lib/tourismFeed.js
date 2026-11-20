/**
 * Лента раздела «Туризм»: 8 главных карточек со свежими данными, остальное — в свёрнутых группах.
 * Свежий — ряд с последней точкой не старше года (годовой ряд — за прошлый или текущий год).
 */

export const TOURISM_FEED_MAX = 8;

const DAY = 86400000;

export function isFreshSeries(indicator, now = new Date()) {
  const d = new Date(indicator?.current_date);
  if (Number.isNaN(d.getTime())) return false;
  if (indicator.frequency === 'annual') return d.getFullYear() >= now.getFullYear() - 1;
  return now.getTime() - d.getTime() <= 365 * DAY;
}

/** Группы остальных рядов России; порядок — порядок на экране. */
export const TOURISM_RU_GROUPS = ['trips', 'stay', 'prices', 'transport', 'money'];

export function tourismRuGroup(code) {
  const c = String(code || '');
  if (/^tour-(outbound|inbound|hist|dest)/.test(c)) return 'trips';
  if (/^tour-(air|airport|rail)/.test(c)) return 'transport';
  if (/^tour-(cpi|price|package-price)/.test(c)) return 'prices';
  if (/^tour-(hotel|sanatorium|agencies)/.test(c)) return 'stay';
  return 'money';
}

/**
 * @param {object[]} listed ряды категории в порядке API
 * @param {string[]} leadCodes порядок первых карточек
 * @returns {{ feed: object[], rest: object[] }}
 */
export function splitTourismFeed(listed, leadCodes = [], now = new Date()) {
  const order = new Map(leadCodes.map((code, i) => [code, i]));
  const fresh = listed.filter((ind) => isFreshSeries(ind, now));
  const leads = fresh.filter((ind) => order.has(ind.code)).sort((a, b) => order.get(a.code) - order.get(b.code));
  const others = fresh.filter((ind) => !order.has(ind.code))
    .sort((a, b) => String(b.current_date).localeCompare(String(a.current_date)));
  const feed = [...leads, ...others].slice(0, TOURISM_FEED_MAX);
  const shown = new Set(feed.map((ind) => ind.code));
  return { feed, rest: listed.filter((ind) => !shown.has(ind.code)) };
}

function ruCountriesWord(n) {
  if (n % 10 === 1 && n % 100 !== 11) return 'страна';
  if (n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14)) return 'страны';
  return 'стран';
}

/** Число стран — из `countries_count` ответа, пока поля нет — длина списка. */
export function countriesLabel(world, countries, t, locale) {
  const n = Number.isFinite(Number(world?.countries_count)) && world?.countries_count != null
    ? Number(world.countries_count)
    : countries.length;
  if (world?.russia_included === false) {
    return t('kt3_allCountriesEx', { n, word: locale === 'en' ? '' : ruCountriesWord(n) });
  }
  return t('kt3_allCountries', { n });
}
