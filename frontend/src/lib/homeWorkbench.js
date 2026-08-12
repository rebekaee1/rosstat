/**
 * Конфиг и чистые хелперы главной: оперативный срез РФ и карта мира.
 */

import { isCpiIndex } from './format';

/** Шесть оперативных значений блока «Россия сегодня» — из одного листинга. */
export const HOME_TODAY_CODES = Object.freeze([
  'usd-rub',
  'key-rate',
  'cpi',
  'unemployment',
  'imoex',
  'gold-price',
]);

export const HOME_TODAY_LABELS = Object.freeze({
  'usd-rub': 'Доллар',
  'key-rate': 'Ключевая ставка',
  cpi: 'Инфляция',
  unemployment: 'Безработица',
  imoex: 'МосБиржа',
  'gold-price': 'Золото',
});

/** Короткие единицы для плотных карточек «Россия сегодня» (без переносов). */
export const HOME_TODAY_UNIT_SHORT = Object.freeze({
  'usd-rub': '₽',
  'key-rate': '%',
  cpi: '%',
  unemployment: '%',
  imoex: 'пт',
  'gold-price': '₽/г',
});

/** Флагманы (если понадобится отдельный список РФ). */
export const HOME_RUSSIA_FLAGSHIP_CODES = Object.freeze([
  'cpi',
  'key-rate',
  'usd-rub',
  'unemployment',
  'gdp-nominal',
  'ipi',
]);

/** Соответствие slug категории → код для sparklines `/dashboard/sparklines`. */
export const HOME_SPARKLINE_BY_CODE = Object.freeze({
  cpi: 'prices',
  'key-rate': 'rates',
  'usd-rub': 'finance',
  unemployment: 'labor',
  'gdp-nominal': 'gdp',
  population: 'population',
  'current-account': 'trade',
  ipi: 'business',
});

export const HOME_REGION_METRICS = Object.freeze([
  {
    code: 'srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy',
    label: 'Зарплата',
  },
  { code: 'chislennost-naseleniya', label: 'Население' },
  { code: 'uroven-bezrabotitsy', label: 'Безработица', betterIsLow: true },
  { code: 'valovoy-regionalnyy-produkt-na-dushu-naseleniya', label: 'ВРП на душу' },
  { code: 'investitsii-v-osnovnoy-kapital', label: 'Инвестиции' },
]);

export const DEFAULT_HOME_REGION_METRIC = HOME_REGION_METRICS[0].code;

export const HOME_COUNTRY_CONCEPT_SHORT = Object.freeze({
  'hicp-index': 'Потребительские цены',
  'unemployment-rate': 'Безработица',
  'gdp-volume-quarterly': 'ВВП, квартал',
  'gdp-volume-annual': 'ВВП, год',
  'budget-balance-gdp': 'Баланс бюджета',
  population: 'Население',
});

export const DEFAULT_HOME_COUNTRY_CONCEPT = 'unemployment-rate';

/** World concept slug → российский indicator code для оверлея РФ на карте. */
export const HOME_MAP_RUSSIA_CONCEPT_CODES = Object.freeze({
  'unemployment-rate': 'unemployment',
  'hicp-index': 'cpi',
  'gdp-volume-quarterly': 'gdp-real',
  'gdp-volume-annual': 'gdp-real-annual',
  population: 'population',
});

export const HOME_MAP_RUSSIA_COUNTRY = Object.freeze({
  code: 'RU',
  slug: 'russia',
  name: 'Россия',
  name_en: 'Russia',
  region: 'Европа',
  indicators_count: 0,
  is_active: true,
});

export const HOME_MAP_SIDE_LINKS = Object.freeze([
  {
    id: 'russia-macro',
    label: 'Показатели России',
    description: 'Макроэкономика РФ',
    to: '/#russia-categories',
    scrollId: 'russia-categories',
  },
  {
    id: 'regions',
    label: 'Регионы России',
    description: '85 субъектов, 489 показателей',
    to: '/regions',
  },
  {
    id: 'europe',
    label: 'Европа',
    description: 'Каталог стран Европы',
    to: '/world',
  },
  {
    id: 'world',
    label: 'Мир',
    description: 'Все доступные страны',
    to: '/world',
  },
]);

export function indexIndicatorsByCode(indicators) {
  const map = new Map();
  for (const ind of indicators || []) {
    if (ind?.code) map.set(ind.code, ind);
  }
  return map;
}

export function pickIndicatorsByCodes(indicators, codes) {
  const byCode = indexIndicatorsByCode(indicators);
  return (codes || []).map((code) => byCode.get(code)).filter(Boolean);
}

/**
 * Первая цифра карточки: hero (Г/г для индексов) либо уровень;
 * для сырого ИПЦ-индекса без hero — «минус 100», как в IndicatorTile.
 */
export function displayPulseValue(indicator) {
  if (!indicator) return null;
  if (indicator.hero_value != null) {
    return {
      value: indicator.hero_value,
      unit: indicator.hero_unit || '%',
      label: indicator.hero_label || null,
      change: indicator.hero_change ?? null,
    };
  }
  const raw = indicator.current_value;
  if (raw == null) return null;
  const value = isCpiIndex(indicator.code) ? Number(raw) - 100 : Number(raw);
  return {
    value,
    unit: indicator.unit || '',
    label: null,
    change: indicator.change ?? null,
  };
}

export function rankHeatmapValues(values, { betterIsLow = false, limit = 8 } = {}) {
  const rows = [...(values || [])].filter((row) => row && row.value != null);
  rows.sort((a, b) => (betterIsLow ? a.value - b.value : b.value - a.value));
  return rows.slice(0, limit);
}

export function heatmapValuesBySlug(heat) {
  const map = new Map();
  for (const row of heat?.values || []) {
    if (row?.slug != null && row.value != null) map.set(row.slug, row.value);
  }
  return map;
}

export function heatmapNameBySlug(heat) {
  const map = {};
  for (const row of heat?.values || []) {
    if (row?.slug) map[row.slug] = row.name;
  }
  return map;
}

export function resolveActiveMapYear(years, preferred, valuesByYear = null) {
  const list = years || [];
  if (!list.length) return null;
  if (preferred != null && list.includes(preferred)) return preferred;
  if (valuesByYear) {
    for (let i = list.length - 1; i >= 0; i -= 1) {
      const bucket = valuesByYear[String(list[i])] || {};
      if (Object.keys(bucket).length >= 8) return list[i];
    }
  }
  return list[list.length - 1];
}

export function worldYearItems(mapSeries, year) {
  if (!mapSeries || year == null) return {};
  return mapSeries.values_by_year?.[String(year)] || {};
}

export function worldRankingFromYearItems(yearItems, limit = 8) {
  return Object.values(yearItems || {})
    .filter((item) => item && item.value != null)
    .sort((a, b) => b.value - a.value)
    .slice(0, limit);
}

export function russiaIndicatorCodeForConcept(conceptSlug) {
  return HOME_MAP_RUSSIA_CONCEPT_CODES[conceptSlug] || null;
}

/**
 * Добавляет РФ в список стран карты и значение из российского индикатора
 * (Eurostat-plane намеренно не содержит RU).
 */
export function withRussiaOnHomeMap({
  countries = [],
  yearItems = {},
  indicators = [],
  conceptSlug,
  activeYear,
} = {}) {
  const list = [...(countries || [])];
  const hasRu = list.some((c) => c?.code === 'RU' || c?.slug === 'russia');
  if (!hasRu) {
    list.push({ ...HOME_MAP_RUSSIA_COUNTRY });
  }

  const items = { ...(yearItems || {}) };
  const ruCode = russiaIndicatorCodeForConcept(conceptSlug);
  const ind = ruCode
    ? indexIndicatorsByCode(indicators).get(ruCode)
    : null;
  const pulse = displayPulseValue(ind);
  if (pulse?.value != null) {
    const yearHint = activeYear != null ? String(activeYear) : null;
    const date = ind?.current_date
      || (yearHint ? `${yearHint}-01-01` : null);
    items.RU = {
      country_code: 'RU',
      country_slug: 'russia',
      country_name: 'Россия',
      indicator_code: ruCode,
      date,
      value: Number(pulse.value),
      _fromRussia: true,
    };
  }

  return { countries: list, yearItems: items, russiaIndicatorCode: ruCode };
}
