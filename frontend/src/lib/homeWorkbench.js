/**
 * Конфиг и чистые хелперы главной: оперативный срез рынков и карта мира.
 */

import { isCpiIndex } from './format';
import {
  regionHubPath,
  regionRatingPath,
  russiaHomePath,
  russiaIndicatorPath,
  worldHubPath,
} from './sitePaths';

/**
 * Оперативный срез мировых рынков (hero). Одна строка = код + подпись + единица.
 * Индекс Доу-Джонса и индекс DXY поставить нельзя: их значения лицензируются
 * правообладателями индексов. Мировой рынок США показываем официальными рядами —
 * индекс доллара Федеральной резервной системы и доходность гособлигаций.
 * Мировая цена золота в долларах ждёт официального дневного источника; учётная
 * цена ЦБ РФ (руб./г) сюда не идёт — это российская мера, не мировая.
 * Месячные ряды Pink Sheet (медь, серебро и др.) в оперативный срез не ставим —
 * там нужна дневная частота. Крипта, кроме биткоина, в срез не идёт.
 */
export const HOME_MARKET_PULSE = Object.freeze([
  { code: 'btc-usd', labelKey: 'home.pulse.label.btc-usd', unitKey: 'home.pulse.unit.btc-usd' },
  { code: 'brent', labelKey: 'home.pulse.label.brent', unitKey: 'home.pulse.unit.brent' },
  { code: 'usd-index', labelKey: 'home.pulse.label.usd-index', unitKey: 'home.pulse.unit.usd-index' },
  { code: 'ust-10y', labelKey: 'home.pulse.label.ust-10y', unitKey: 'home.pulse.unit.ust-10y' },
  { code: 'natural-gas', labelKey: 'home.pulse.label.natural-gas', unitKey: 'home.pulse.unit.natural-gas' },
]);

/** Коды среза — производные от HOME_MARKET_PULSE (не дублировать вручную). */
export const HOME_TODAY_CODES = Object.freeze(
  HOME_MARKET_PULSE.map((item) => item.code),
);

const HOME_PULSE_BY_CODE = Object.freeze(
  Object.fromEntries(HOME_MARKET_PULSE.map((item) => [item.code, item])),
);

/** Подпись среза через messages; фолбэк — name/name_en с API. */
export function homePulseLabel(code, t, indicator) {
  const item = HOME_PULSE_BY_CODE[code];
  if (item?.labelKey && typeof t === 'function') return t(item.labelKey);
  return indicator?.name || code || '';
}

/** Короткая единица среза через messages; фолбэк — unit из pulse/API. */
export function homePulseUnitShort(code, t, fallback = '') {
  const item = HOME_PULSE_BY_CODE[code];
  if (item?.unitKey && typeof t === 'function') return t(item.unitKey);
  return fallback;
}

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
    labelKey: 'regions.metric.wages',
  },
  { code: 'chislennost-naseleniya', labelKey: 'regions.metric.population' },
  { code: 'uroven-bezrabotitsy', labelKey: 'regions.metric.unemployment', betterIsLow: true },
  { code: 'valovoy-regionalnyy-produkt-na-dushu-naseleniya', labelKey: 'regions.metric.grpPerCapita' },
  { code: 'investitsii-v-osnovnoy-kapital', labelKey: 'regions.metric.investment' },
]);

export const DEFAULT_HOME_REGION_METRIC = HOME_REGION_METRICS[0].code;

/** Message keys for map/rating concept short labels (values live in messages.*.js). */
export const HOME_COUNTRY_CONCEPT_LABEL_KEYS = Object.freeze({
  'hicp-index': 'home.concept.hicp-index',
  'unemployment-rate': 'home.concept.unemployment-rate',
  'gdp-volume-quarterly': 'home.concept.gdp-volume-quarterly',
  'gdp-volume-annual': 'home.concept.gdp-volume-annual',
  'budget-balance-gdp': 'home.concept.budget-balance-gdp',
  population: 'home.concept.population',
  'long-term-interest-rate': 'home.concept.long-term-interest-rate',
  'activity-rate': 'home.concept.activity-rate',
  'gdp-per-capita-eu': 'home.concept.gdp-per-capita-eu',
});

/** @deprecated use HOME_COUNTRY_CONCEPT_LABEL_KEYS + t(); kept for non-UI callers expecting strings. */
export const HOME_COUNTRY_CONCEPT_SHORT = Object.freeze({
  'hicp-index': 'Цены, изменение за год',
  'unemployment-rate': 'Безработица',
  'gdp-volume-quarterly': 'ВВП, квартал',
  'gdp-volume-annual': 'ВВП, год',
  'budget-balance-gdp': 'Баланс бюджета',
  population: 'Население',
  'long-term-interest-rate': 'Долгосрочные ставки',
  'activity-rate': 'Экономическая активность',
  'gdp-per-capita-eu': 'ВВП на душу к ЕС',
});

export const DEFAULT_HOME_COUNTRY_CONCEPT = 'unemployment-rate';

/** Short concept label via messages; falls back to API name / slug. */
export function homeConceptLabel(slug, t, fallback = '') {
  const key = HOME_COUNTRY_CONCEPT_LABEL_KEYS[slug];
  if (key && typeof t === 'function') return t(key);
  return HOME_COUNTRY_CONCEPT_SHORT[slug] || fallback || slug || '';
}

export const HOME_COUNTRY_MACROREGIONS = Object.freeze([
  {
    id: 'europe',
    labelKey: 'home.macro.europe',
    available: true,
    coverageNoteKey: 'home.macro.europeCoverage',
  },
  { id: 'americas', labelKey: 'home.macro.americas', available: false },
  { id: 'asia', labelKey: 'home.macro.asia', available: false },
]);

export const DEFAULT_HOME_COUNTRY_MACROREGION = 'europe';

export function availableCountryMacroregions(macros = HOME_COUNTRY_MACROREGIONS) {
  return macros.filter((m) => m.available);
}

export function resolveCountryMacroregion(id, macros = HOME_COUNTRY_MACROREGIONS) {
  const hit = macros.find((m) => m.id === id && m.available);
  return hit?.id || DEFAULT_HOME_COUNTRY_MACROREGION;
}

export function countryCoverageNoteKey(macroId, macros = HOME_COUNTRY_MACROREGIONS) {
  const hit = macros.find((m) => m.id === macroId);
  return hit?.coverageNoteKey || 'home.macro.defaultCoverage';
}
/**
 * Темы для выбора показателя (карта / рейтинг). Одна точка для пикера —
 * не плодить три ленты чипов. Подписи — labelKey → messages.*.js.
 */
export const WORLD_CONCEPT_GROUPS = Object.freeze([
  { id: 'prices', labelKey: 'home.conceptGroup.prices', slugs: Object.freeze(['hicp-index']) },
  {
    id: 'labor',
    labelKey: 'home.conceptGroup.labor',
    slugs: Object.freeze(['unemployment-rate', 'activity-rate']),
  },
  {
    id: 'gdp',
    labelKey: 'home.conceptGroup.gdp',
    slugs: Object.freeze(['gdp-per-capita-eu']),
  },
  { id: 'budget', labelKey: 'home.conceptGroup.budget', slugs: Object.freeze(['budget-balance-gdp']) },
  { id: 'population', labelKey: 'home.conceptGroup.population', slugs: Object.freeze(['population']) },
  {
    id: 'rates',
    labelKey: 'home.conceptGroup.rates',
    slugs: Object.freeze(['long-term-interest-rate']),
  },
]);

/**
 * World concept → российский ряд только при честной сопоставимости единицы.
 * Значения в рейтинг/карту отдаёт сервер (`world_russia_rank`); здесь — только
 * коды для перелинковки на карточку РФ.
 */
export const HOME_MAP_RUSSIA_CONCEPT_CODES = Object.freeze({
  'unemployment-rate': 'unemployment',
  'hicp-index': 'cpi-yoy',
  population: 'population',
});

/** World concept → код регионального рейтинга того же смысла (если есть). */
export const WORLD_CONCEPT_REGION_RATING = Object.freeze({
  'unemployment-rate': 'uroven-bezrabotitsy',
  population: 'chislennost-naseleniya',
  'hicp-index': 'indeksy-potrebitelskih-tsen',
  'activity-rate': 'uroven-zanyatosti-naseleniya',
});

/**
 * Фоллбэк оговорки (RU), если нет t() / ключа.
 * Канон текстов — backend `world_concept_russia.py`; EN — messages.en.js.
 */
export const WORLD_CONCEPT_RUSSIA_NOTE = Object.freeze({
  'unemployment-rate':
    'Для России в рейтинг входит уровень безработицы по обследованию рабочей силы Росстата. '
    + 'Зарубежные значения — по гармонизированной методологии Евростата. '
    + 'Оба показателя близки по смыслу (доля безработных среди экономически активного населения), '
    + 'но возрастная база и детали обследования могут отличаться.',
  'hicp-index':
    'Для России сравнивается изменение потребительских цен за год по данным Росстата '
    + '(индекс потребительских цен), для зарубежных стран — гармонизированный индекс Евростата '
    + 'или национальный индекс цен. Составы потребительских корзин различаются; сравнивается '
    + 'именно относительное изменение за год, а не уровень индекса и не изменение к предыдущему месяцу.',
  population:
    'Численность населения России — по данным Росстата (в публикации ведомства ряд ведётся '
    + 'в миллионах человек; в таблице приведена численность в человеках). Для зарубежных стран — '
    + 'данные их статистических ведомств или Евростата.',
});

export const WORLD_CONCEPT_RUSSIA_NOTE_KEYS = Object.freeze({
  'unemployment-rate': 'world.rating.russiaNote.unemployment-rate',
  'hicp-index': 'world.rating.russiaNote.hicp-index',
  population: 'world.rating.russiaNote.population',
});

/** Родительный падеж для заголовка «Рейтинг стран по …» — зеркало backend (RU). */
export const WORLD_RATING_QUERY_NAMES = Object.freeze({
  'hicp-index': 'изменению потребительских цен за год',
  'unemployment-rate': 'уровню безработицы',
  'budget-balance-gdp': 'сальдо бюджета',
  population: 'численности населения',
  'long-term-interest-rate': 'доходности долгосрочных государственных облигаций',
  'activity-rate': 'уровню экономической активности',
  'gdp-per-capita-eu': 'ВВП на душу относительно среднего по ЕС',
});

export const WORLD_RATING_QUERY_NAME_KEYS = Object.freeze({
  'hicp-index': 'world.rating.query.hicp-index',
  'unemployment-rate': 'world.rating.query.unemployment-rate',
  'budget-balance-gdp': 'world.rating.query.budget-balance-gdp',
  population: 'world.rating.query.population',
  'long-term-interest-rate': 'world.rating.query.long-term-interest-rate',
  'activity-rate': 'world.rating.query.activity-rate',
  'gdp-per-capita-eu': 'world.rating.query.gdp-per-capita-eu',
});

/**
 * Заголовок рейтинга стран. С t() — locale-aware (зеркало SSR EN/RU).
 * Без t — прежний RU-контракт для тестов и non-UI callers.
 */
export function worldRatingTitle(conceptSlug, publicName, year, t) {
  const queryKey = WORLD_RATING_QUERY_NAME_KEYS[conceptSlug];
  const queryName = (queryKey && typeof t === 'function')
    ? t(queryKey)
    : (WORLD_RATING_QUERY_NAMES[conceptSlug]
      || String(publicName || conceptSlug).toLowerCase());

  if (typeof t === 'function') {
    const head = t('world.rating.titleHead', { query: queryName });
    if (year == null) return head;
    const yoyStyle = conceptSlug === 'hicp-index'
      || String(queryName).trimEnd().endsWith('за год')
      || String(queryName).includes('year-over-year');
    if (yoyStyle) return t('world.rating.titleYearComma', { head, year });
    return t('world.rating.titleYearFor', { head, year });
  }

  const head = `Рейтинг стран по ${queryName}`;
  if (year == null) return head;
  if (queryName.trimEnd().endsWith('за год')) return `${head}, ${year}`;
  return `${head} за ${year} год`;
}

export const HOME_MAP_RUSSIA_COUNTRY = Object.freeze({
  code: 'RU',
  slug: 'russia',
  name: 'Россия',
  name_en: 'Russia',
  region: 'Европа',
  indicators_count: 0,
  is_active: true,
});

/**
 * Боковые переходы у карты. «Европа» и «Мир» раньше дублировали /world;
 * отдельный URL-режим Европы на /world пока не поддерживается (карта WorldHome).
 * Подписи — через labelKey/descriptionKey → messages.*.js.
 */
export const HOME_MAP_SIDE_LINKS = Object.freeze([
  {
    id: 'russia-macro',
    labelKey: 'home.side.russiaMacro',
    descriptionKey: 'home.side.russiaMacroDesc',
    to: russiaHomePath(),
  },
  {
    id: 'regions',
    labelKey: 'home.side.regions',
    descriptionKey: 'home.side.regionsDesc',
    to: regionHubPath(),
  },
  {
    id: 'world',
    labelKey: 'home.side.world',
    descriptionKey: 'home.side.worldDesc',
    to: worldHubPath(),
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

/** Доля от пикового покрытия по годам + минимум стран. */
export const MAP_YEAR_COVERAGE_SHARE = 0.5;
export const MAP_YEAR_MIN_COUNTRIES = 8;

export function resolveActiveMapYear(years, preferred, valuesByYear = null) {
  const list = years || [];
  if (!list.length) return null;
  if (preferred != null && list.includes(preferred)) return preferred;
  if (valuesByYear) {
    let peak = 0;
    for (const year of list) {
      const n = Object.keys(valuesByYear[String(year)] || {}).length;
      if (n > peak) peak = n;
    }
    const threshold = Math.max(
      MAP_YEAR_MIN_COUNTRIES,
      Math.ceil(peak * MAP_YEAR_COVERAGE_SHARE),
    );
    for (let i = list.length - 1; i >= 0; i -= 1) {
      const bucket = valuesByYear[String(list[i])] || {};
      if (Object.keys(bucket).length >= threshold) return list[i];
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

export function regionRatingCodeForConcept(conceptSlug) {
  return WORLD_CONCEPT_REGION_RATING[conceptSlug] || null;
}

export function russiaNoteForConcept(conceptSlug, t) {
  const key = WORLD_CONCEPT_RUSSIA_NOTE_KEYS[conceptSlug];
  if (key && typeof t === 'function') return t(key);
  return WORLD_CONCEPT_RUSSIA_NOTE[conceptSlug] || null;
}

/** Ссылки «из рейтинга в российский раздел» — не тупик. */
export function russiaDeepLinksForConcept(conceptSlug) {
  const regionCode = regionRatingCodeForConcept(conceptSlug);
  const indicatorCode = russiaIndicatorCodeForConcept(conceptSlug);
  return {
    countryHref: indicatorCode ? russiaIndicatorPath(indicatorCode) : russiaHomePath(),
    regionsHref: regionHubPath(),
    regionRatingHref: regionCode ? regionRatingPath(regionCode) : null,
  };
}

/**
 * Подмешивает каркас РФ в список стран, если сервер пометил concept.russia.
 * Значения берутся только из map-series/snapshot — клиент их не считает.
 */
export function withRussiaOnHomeMap({
  countries = [],
  yearItems = {},
  mapSeries = null,
} = {}) {
  const items = { ...(yearItems || {}) };
  const russia = mapSeries?.concept?.russia || null;
  const hasRuValue = items.RU?.value != null;
  const eligible = Boolean(russia?.eligible) || hasRuValue;
  const list = [...(countries || [])];
  if (eligible) {
    const hasRu = list.some((c) => c?.code === 'RU' || c?.slug === 'russia');
    if (!hasRu) {
      const shell = russia?.country || HOME_MAP_RUSSIA_COUNTRY;
      list.push({
        code: shell.code || 'RU',
        slug: shell.slug || 'russia',
        name: shell.name || shell.name_en || shell.name_ru || 'Russia',
        name_en: shell.name_en || 'Russia',
        region: shell.region || shell.region_ru || 'Europe',
        indicators_count: shell.indicators_count || 0,
        is_active: true,
      });
    }
  }
  const ruCode = russia?.indicator_code
    || items.RU?.indicator_code
    || null;
  return { countries: list, yearItems: items, russiaIndicatorCode: ruCode };
}
