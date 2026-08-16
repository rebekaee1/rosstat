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
  { code: 'btc-usd', label: 'Биткоин', unitShort: '$' },
  { code: 'brent', label: 'Нефть Brent', unitShort: '$/барр.' },
  { code: 'usd-index', label: 'Индекс доллара', unitShort: 'пунктов' },
  { code: 'ust-10y', label: 'Гособлигации США', unitShort: '%, 10 лет' },
  { code: 'natural-gas', label: 'Природный газ', unitShort: '$/млн БТЕ' },
]);

/** Коды среза — производные от HOME_MARKET_PULSE (не дублировать вручную). */
export const HOME_TODAY_CODES = Object.freeze(
  HOME_MARKET_PULSE.map((item) => item.code),
);

export const HOME_TODAY_LABELS = Object.freeze(
  Object.fromEntries(HOME_MARKET_PULSE.map((item) => [item.code, item.label])),
);

export const HOME_TODAY_UNIT_SHORT = Object.freeze(
  Object.fromEntries(HOME_MARKET_PULSE.map((item) => [item.code, item.unitShort])),
);

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

/**
 * Темы для выбора показателя (карта / рейтинг). Одна точка для пикера —
 * не плодить три ленты чипов.
 */
export const WORLD_CONCEPT_GROUPS = Object.freeze([
  { id: 'prices', label: 'Цены', slugs: Object.freeze(['hicp-index']) },
  {
    id: 'labor',
    label: 'Рынок труда',
    slugs: Object.freeze(['unemployment-rate', 'activity-rate']),
  },
  {
    id: 'gdp',
    label: 'ВВП',
    slugs: Object.freeze(['gdp-per-capita-eu']),
  },
  { id: 'budget', label: 'Бюджет', slugs: Object.freeze(['budget-balance-gdp']) },
  { id: 'population', label: 'Население', slugs: Object.freeze(['population']) },
  {
    id: 'rates',
    label: 'Ставки',
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
 * Фоллбэк оговорки, если API ещё не отдал concept.russia.note.
 * Канон текстов — backend `world_concept_russia.py`.
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

/** Родительный падеж для заголовка «Рейтинг стран по …» — зеркало backend. */
export const WORLD_RATING_QUERY_NAMES = Object.freeze({
  'hicp-index': 'изменению потребительских цен за год',
  'unemployment-rate': 'уровню безработицы',
  'budget-balance-gdp': 'сальдо бюджета',
  population: 'численности населения',
  'long-term-interest-rate': 'доходности долгосрочных государственных облигаций',
  'activity-rate': 'уровню экономической активности',
  'gdp-per-capita-eu': 'ВВП на душу относительно среднего по ЕС',
});

export function worldRatingTitle(conceptSlug, publicName, year) {
  const queryName = WORLD_RATING_QUERY_NAMES[conceptSlug]
    || String(publicName || conceptSlug).toLowerCase();
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
 */
export const HOME_MAP_SIDE_LINKS = Object.freeze([
  {
    id: 'russia-macro',
    label: 'Показатели России',
    description: 'Макроэкономика РФ',
    to: russiaHomePath(),
  },
  {
    id: 'regions',
    label: 'Регионы России',
    description: '85 субъектов, 489 показателей',
    to: regionHubPath(),
  },
  {
    id: 'world',
    label: 'Страны',
    description: 'Каталог стран и показателей',
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

export function russiaNoteForConcept(conceptSlug) {
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
        name: shell.name_ru || shell.name || 'Россия',
        name_en: shell.name_en || 'Russia',
        region: shell.region_ru || shell.region || 'Европа',
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
