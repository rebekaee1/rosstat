/**
 * Конфиг и чистые хелперы рабочего стола главной («три плоскости»).
 * Вкладка «Страны» архитектурно готова к макрорегионам; текущее покрытие —
 * европейская статистика — подписывается честно, без привязки id/URL к Европе.
 */

import { isCpiIndex } from './format';

export const WORKBENCH_TABS = Object.freeze([
  { id: 'russia', label: 'Россия' },
  { id: 'regions', label: 'Регионы' },
  { id: 'countries', label: 'Страны' },
]);

export const DEFAULT_WORKBENCH_TAB = 'russia';

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

/** Флагманы вкладки «Россия» (без карты). */
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

/**
 * Макрорегионы для вкладки «Страны». Сейчас доступен только europe;
 * остальные — зарезервированы под будущие официальные источники.
 */
export const HOME_COUNTRY_MACROREGIONS = Object.freeze([
  {
    id: 'europe',
    label: 'Европа',
    available: true,
    coverageNote: 'Текущее покрытие — страны Европы по данным Евростата',
  },
  { id: 'americas', label: 'Америка', available: false },
  { id: 'asia', label: 'Азия', available: false },
]);

export const DEFAULT_HOME_COUNTRY_MACROREGION = 'europe';

export function isWorkbenchTab(id) {
  return WORKBENCH_TABS.some((tab) => tab.id === id);
}

export function resolveWorkbenchTab(id, fallback = DEFAULT_WORKBENCH_TAB) {
  return isWorkbenchTab(id) ? id : fallback;
}

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

export function resolveActiveMapYear(years, preferred) {
  const list = years || [];
  if (!list.length) return null;
  if (preferred != null && list.includes(preferred)) return preferred;
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

export function availableCountryMacroregions(macros = HOME_COUNTRY_MACROREGIONS) {
  return macros.filter((m) => m.available);
}

export function resolveCountryMacroregion(id, macros = HOME_COUNTRY_MACROREGIONS) {
  const hit = macros.find((m) => m.id === id && m.available);
  return hit?.id || DEFAULT_HOME_COUNTRY_MACROREGION;
}

export function countryCoverageNote(macroId, macros = HOME_COUNTRY_MACROREGIONS) {
  const hit = macros.find((m) => m.id === macroId);
  return hit?.coverageNote
    || 'Текущее покрытие — доступные страны официальной статистики';
}
