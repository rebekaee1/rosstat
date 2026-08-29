/**
 * Конфиг и чистые хелперы главной: оперативный срез рынков и карта мира.
 */

import { isCpiIndex } from './format';
import {
  countryPath,
  indicatorPath,
  regionHubPath,
  regionRatingPath,
  russiaHomePath,
  russiaIndicatorPath,
} from './sitePaths';

/**
 * Оперативный срез мировых рынков (hero). Одна строка = код + подпись + единица.
 * Индекс Доу-Джонса и индекс DXY поставить нельзя: их значения лицензируются
 * правообладателями индексов. Мировой рынок США показываем официальными рядами —
 * индекс доллара Федеральной резервной системы и доходность гособлигаций.
 * Мировая цена золота в долларах ждёт лицензии IBA на дневной LBMA-ряд;
 * учётная цена ЦБ РФ (руб./г) сюда не идёт — это российская мера, не мировая.
 * Шестая карточка — справочный курс EUR/USD Европейского центрального банка:
 * единственный официальный дневной ряд из этой панели, который выходит
 * в тот же календарный день (около 16:00 CET).
 * Месячные ряды Pink Sheet (медь, серебро и др.) в оперативный срез не ставим —
 * там нужна дневная частота. Крипта, кроме биткоина, в срез не идёт.
 */
export const HOME_MARKET_PULSE = Object.freeze([
  { code: 'btc-usd', labelKey: 'home.pulse.label.btc-usd', unitKey: 'home.pulse.unit.btc-usd' },
  { code: 'brent', labelKey: 'home.pulse.label.brent', unitKey: 'home.pulse.unit.brent' },
  { code: 'eur-usd', labelKey: 'home.pulse.label.eur-usd', unitKey: 'home.pulse.unit.eur-usd' },
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

/** Message keys for map/rating concept short labels (values live in messages.*.js). */
export const HOME_COUNTRY_CONCEPT_LABEL_KEYS = Object.freeze({
  'gdp-usd': 'home.concept.gdp-usd',
  'gdp-per-capita-usd': 'home.concept.gdp-per-capita-usd',
  'unemployment-rate': 'home.concept.unemployment-rate',
  'hicp-index': 'home.concept.hicp-index',
  population: 'home.concept.population',
  'policy-rate': 'home.concept.policy-rate',
  'budget-balance-gdp': 'home.concept.budget-balance-gdp',
  'government-debt-gdp': 'home.concept.government-debt-gdp',
  'gdp-volume-quarterly': 'home.concept.gdp-volume-quarterly',
  'gdp-volume-annual': 'home.concept.gdp-volume-annual',
  'long-term-interest-rate': 'home.concept.long-term-interest-rate',
  'activity-rate': 'home.concept.activity-rate',
  'gdp-per-capita-eu': 'home.concept.gdp-per-capita-eu',
});

/**
 * Показатели карты и рейтинга на главной, в порядке показа. Список закрытый:
 * главная — витрина, а не каталог; полный набор живёт на странице рейтинга.
 * Отсутствующие в API концепты просто не рисуются, так что порядок можно
 * задавать заранее — до появления ряда.
 */
export const HOME_MAP_CONCEPT_ORDER = Object.freeze([
  'gdp-usd',
  'gdp-per-capita-usd',
  'unemployment-rate',
  'hicp-index',
  'population',
  'policy-rate',
  'budget-balance-gdp',
  'government-debt-gdp',
]);

export const DEFAULT_HOME_COUNTRY_CONCEPT = 'gdp-usd';

/**
 * Оставляет из ответа API только показатели главной и выстраивает их порядком
 * HOME_MAP_CONCEPT_ORDER. Если ни одного из них нет — отдаёт список как есть,
 * чтобы карта не осталась без выбора.
 */
export function homeMapConcepts(concepts = []) {
  const bySlug = new Map((concepts || []).filter((c) => c?.slug).map((c) => [c.slug, c]));
  const picked = HOME_MAP_CONCEPT_ORDER.map((slug) => bySlug.get(slug)).filter(Boolean);
  return picked.length ? picked : (concepts || []).filter((c) => c?.slug);
}

/** Показатель по умолчанию: первый доступный из набора главной. */
export function resolveHomeConcept(concepts = [], preferred = DEFAULT_HOME_COUNTRY_CONCEPT) {
  const list = homeMapConcepts(concepts);
  if (!list.length) return preferred;
  if (list.some((c) => c.slug === preferred)) return preferred;
  return list[0].slug;
}

/** Короткая подпись показателя из словаря; фолбэк — имя с API или слаг. */
export function homeConceptLabel(slug, t, fallback = '') {
  const key = HOME_COUNTRY_CONCEPT_LABEL_KEYS[slug];
  if (key) return t(key);
  return fallback || slug || '';
}

/**
 * Показатели, у которых содержателен знак: центр шкалы — ноль, а не медиана.
 * Единая точка для карты на главной, на странице рейтинга и в SSR-легенде —
 * иначе одна и та же карта окрашивается по-разному в разных местах.
 */
const WORLD_CONCEPT_ZERO_CENTRED = Object.freeze(new Set(['budget-balance-gdp']));

export function conceptColorMode(conceptSlug) {
  return WORLD_CONCEPT_ZERO_CENTRED.has(conceptSlug) ? 'diverging' : 'relative';
}

/**
 * Сколько стран показывает рейтинг рядом с картой. Колонка тянется по высоте
 * карты (~30rem + шкала лет): 32 строки заполняют её без длинного скролла.
 */
export const HOME_RATING_LIMIT = 32;

/**
 * World concept → российский ряд только при честной сопоставимости единицы.
 * Значения в рейтинг/карту отдаёт сервер (`world_russia_rank`); здесь — только
 * коды для перелинковки на карточку РФ. WEO-ряды (МВФ) — карточки каталога
 * /russia/indicator/<code>; с карты главной Россия ведёт туда, а не в
 * «Сегодня», по тем же концептам, что и note-оговорка.
 */
export const HOME_MAP_RUSSIA_CONCEPT_CODES = Object.freeze({
  'unemployment-rate': 'unemployment',
  'hicp-index': 'cpi-yoy',
  population: 'population',
  'gdp-usd': 'weo-gdp-usd',
  'gdp-per-capita-usd': 'weo-gdp-per-capita-usd',
  'budget-balance-gdp': 'weo-budget-balance-gdp',
});

/**
 * Понятия карты, значения которых на срезе опираются на выпуск МВФ WEO
 * (для зарубежных стран — ряд фонда; для России в рейтинге ВВП — мост
 * Росстат × курс Банка России, карточка клика — ряд МВФ).
 */
export const WEO_MAP_CONCEPTS = Object.freeze(new Set([
  'gdp-usd',
  'gdp-per-capita-usd',
  'budget-balance-gdp',
  'government-debt-gdp',
]));

export function isWeoMapConcept(slug) {
  return WEO_MAP_CONCEPTS.has(slug);
}

/**
 * Концепты, для которых сервер считает межстрановой ориентир
 * (`benchmark_by_year` / `/compare/average`). Зеркало backend
 * `_AVERAGE_CONCEPTS`: ВВП — медиана (скошенное распределение), ставки и
 * безработица — среднее. Клиент ориентир не считает.
 */
export const WORLD_RANKING_AVERAGE_CONCEPTS = Object.freeze(new Set([
  'hicp-index',
  'unemployment-rate',
  'budget-balance-gdp',
  'gdp-usd',
  'gdp-per-capita-usd',
]));

export const WORLD_RANKING_MEDIAN_CONCEPTS = Object.freeze(new Set([
  'hicp-index',
  'gdp-usd',
  'gdp-per-capita-usd',
]));

/** World concept → код регионального рейтинга того же смысла (если есть). */
export const WORLD_CONCEPT_REGION_RATING = Object.freeze({
  'unemployment-rate': 'uroven-bezrabotitsy',
  population: 'chislennost-naseleniya',
  'hicp-index': 'indeksy-potrebitelskih-tsen',
  'activity-rate': 'uroven-zanyatosti-naseleniya',
});

export const WORLD_RATING_QUERY_NAME_KEYS = Object.freeze({
  'hicp-index': 'world.rating.query.hicp-index',
  'unemployment-rate': 'world.rating.query.unemployment-rate',
  'budget-balance-gdp': 'world.rating.query.budget-balance-gdp',
  population: 'world.rating.query.population',
  'long-term-interest-rate': 'world.rating.query.long-term-interest-rate',
  'activity-rate': 'world.rating.query.activity-rate',
  'gdp-per-capita-eu': 'world.rating.query.gdp-per-capita-eu',
  'gdp-usd': 'world.rating.query.gdp-usd',
  'gdp-per-capita-usd': 'world.rating.query.gdp-per-capita-usd',
});

/**
 * Заголовок рейтинга стран — зеркало SSR (`seo_world`), locale-aware.
 * Падеж показателя берётся из словаря; для показателей «за год» год
 * присоединяется запятой, иначе — оборотом «за {год} год».
 */
export function worldRatingTitle(conceptSlug, publicName, year, t) {
  const queryKey = WORLD_RATING_QUERY_NAME_KEYS[conceptSlug];
  const queryName = queryKey
    ? t(queryKey)
    : String(publicName || conceptSlug).toLowerCase();
  const head = t('world.rating.titleHead', { query: queryName });
  if (year == null) return head;
  const yoyStyle = conceptSlug === 'hicp-index'
    || String(queryName).trimEnd().endsWith('за год')
    || String(queryName).includes('year-over-year');
  return yoyStyle
    ? t('world.rating.titleYearComma', { head, year })
    : t('world.rating.titleYearFor', { head, year });
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

/**
 * Направление сортировки рейтинга приходит с сервера вместе с каталогом
 * показателей; локальный набор — фолбэк на время загрузки. Одна точка на
 * главную и страницу рейтинга: иначе один и тот же топ-20 идёт в разном порядке.
 */
const SORT_ASC_CONCEPTS = Object.freeze(
  new Set(['unemployment-rate', 'long-term-interest-rate']),
);

export function defaultSortForConcept(slug, concepts) {
  const known = (concepts || []).find((item) => item?.slug === slug);
  if (known?.default_sort === 'asc' || known?.default_sort === 'desc') {
    return known.default_sort;
  }
  return SORT_ASC_CONCEPTS.has(slug) ? 'asc' : 'desc';
}

export function worldRankingFromYearItems(yearItems, limit = 8, direction = 'desc') {
  return Object.values(yearItems || {})
    .filter((item) => item && item.value != null)
    .sort((a, b) => (direction === 'asc' ? a.value - b.value : b.value - a.value))
    .slice(0, limit);
}

export function russiaIndicatorCodeForConcept(conceptSlug) {
  return HOME_MAP_RUSSIA_CONCEPT_CODES[conceptSlug] || null;
}

/**
 * Клик по стране на карте и в рейтинге: карточка ряда, если сервер отдал
 * `indicator_code` в map-series; иначе страница страны. Россия — канон
 * `/russia/indicator/…`.
 */
export function mapSelectHref(country, detail, {
  conceptSlug,
  russiaIndicatorCode = null,
} = {}) {
  const isRussia = country?.code === 'RU' || country?.slug === 'russia';
  if (isRussia) {
    const code = detail?.indicator_code
      || russiaIndicatorCode
      || russiaIndicatorCodeForConcept(conceptSlug);
    return code ? russiaIndicatorPath(code) : russiaHomePath();
  }
  if (detail?.indicator_code && country?.slug) {
    return indicatorPath(country.slug, detail.indicator_code);
  }
  if (country?.slug) return countryPath(country.slug);
  return null;
}

export function regionRatingCodeForConcept(conceptSlug) {
  return WORLD_CONCEPT_REGION_RATING[conceptSlug] || null;
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
 * Страны каталога плюс все коды годового среза map-series.
 * Карта и рейтинг читают один `yearItems`: иначе страны WEO окрашены,
 * но не кликабельны (их нет в `/world/countries`).
 */
export function mapSurfaceCountries(catalogCountries = [], yearItems = {}) {
  const list = [...(catalogCountries || [])];
  const seen = new Set(list.map((country) => country?.code).filter(Boolean));
  for (const item of Object.values(yearItems || {})) {
    const code = item?.country_code;
    if (!code || seen.has(code)) continue;
    seen.add(code);
    list.push({
      code,
      slug: item.country_slug,
      name: item.country_name,
      name_en: item.country_name,
      is_active: true,
    });
  }
  return list;
}

/**
 * Подмешивает каркас РФ в список стран, если сервер пометил concept.russia.
 * Значения берутся только из map-series/snapshot — клиент их не считает.
 * Затем дополняет каталог странами среза, чтобы карта и таблица совпадали.
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
  return {
    countries: mapSurfaceCountries(list, items),
    yearItems: items,
    russiaIndicatorCode: ruCode,
  };
}
