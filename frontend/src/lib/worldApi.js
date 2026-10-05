// API-слой мирового блока (bounded context «Мировая экономика»).
// Отдельно от макро/регионов: своя ось (страна × индикатор × mode).
// Факты и quality-gated прогнозы остаются в отдельном world API.
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import api, { fetchWorldSearch } from './api';
import { formatValue } from './format';
import {
  WORLD_MOCK_COUNTRIES,
  WORLD_MOCK_COUNTRY,
  WORLD_MOCK_INDICATOR,
  getWorldMockData,
  getWorldMockSearch,
} from './worldMocks';
import {
  countryPath,
  indicatorPath,
  worldRatingPath,
} from './sitePaths';
import { currentUiLocale } from '../i18n/locale';
import { useLocale } from '../i18n/localeContext';

/** Лимит выдачи для глобальной палитры ⌘K (Россия + мир). */
export const WORLD_GLOBAL_SEARCH_LIMIT = 100;

const STALE = 10 * 60 * 1000;
const GC = 30 * 60 * 1000;
/** Главная: не крутить RQ retry×2 на тяжёлых world-запросах (скелетон карты, не пустой hero). */
const WORLD_SURFACE_RETRY = 1;

/** Locale in queryKey — иначе preview_locale=en оставляет RU payload в кэше. */
function localeKey() {
  return currentUiLocale();
}

/** В хуках язык берём из контекста: ключ кэша меняется вместе с языком интерфейса, а не читается из глобальной переменной. */
function useLocaleKey() {
  const { locale } = useLocale();
  return locale || localeKey();
}

/** Stable query keys — homeBootstrap seeds the same shapes on cold SSR. */
export function worldCountriesQueryKey(locale = localeKey()) {
  return ['world-countries', locale];
}

export function worldCompareSnapshotQueryKey(conceptSlug, locale = localeKey()) {
  return ['world-compare-snapshot', conceptSlug, locale];
}

export function worldMapSeriesQueryKey(conceptSlug, locale = localeKey()) {
  return ['world-map-series', conceptSlug, locale];
}

/**
 * Фолбэк на фикстуры — ТОЛЬКО в dev, пока backend /world не подключён.
 * В проде выдуманные значения показывать нельзя ни при каких ошибках: это
 * misleading-данные на публичной витрине, а не удобство разработки.
 */
function shouldUseMock(err) {
  if (!import.meta.env.DEV) return false;
  // Abort/timeout/429 без тела — не подменять живой ряд фикстурой HICP.
  if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return false;
  const status = err?.response?.status;
  return status === 404 || status === 502 || status === 503;
}

async function withMockFallback(request, mockFactory) {
  try {
    const { data } = await request();
    return { ...data, _fromMock: false };
  } catch (err) {
    if (shouldUseMock(err)) {
      const mock = mockFactory();
      if (mock != null) return { ...mock, _fromMock: true };
    }
    throw err;
  }
}

/** Cold SQL build can exceed the default 15s Axios timeout; bootstrap +
 * durable Redis usually avoid the hit, but keep headroom when both miss. */
const WORLD_COUNTRIES_TIMEOUT_MS = 45000;

export function useWorldCountries({ enabled = true } = {}) {
  const lk = useLocaleKey();
  return useQuery({
    enabled,
    queryKey: worldCountriesQueryKey(lk),
    queryFn: ({ signal }) =>
      withMockFallback(
        () => api.get('/world/countries', { signal, timeout: WORLD_COUNTRIES_TIMEOUT_MS }),
        () => WORLD_MOCK_COUNTRIES,
      ),
    staleTime: STALE,
    gcTime: GC,
    retry: WORLD_SURFACE_RETRY,
  });
}

/**
 * Страна из уже загруженного каталога (без запроса): нужна, чтобы по нажатию на страну сразу показать
 * её название, флаг и число показателей, пока грузится карточка. null, если каталога в кэше ещё нет.
 */
export function useCachedWorldCountry(slug) {
  const queryClient = useQueryClient();
  const lk = useLocaleKey();
  if (!slug) return null;
  const catalog = queryClient.getQueryData(worldCountriesQueryKey(lk));
  const list = Array.isArray(catalog?.countries) ? catalog.countries : [];
  return list.find((country) => country?.slug === slug) || null;
}

export function useWorldCountry(slug, { enabled = true } = {}) {
  const lk = useLocaleKey();
  return useQuery({
    queryKey: ['world-country', slug, lk],
    queryFn: ({ signal }) =>
      withMockFallback(
        () => api.get(`/world/countries/${slug}`, { signal }),
        () => {
          const mock = WORLD_MOCK_COUNTRY[slug];
          if (!mock) {
            const err = new Error('Страна не найдена');
            err.response = { status: 404 };
            throw err;
          }
          return mock;
        },
      ),
    enabled: enabled && !!slug,
    staleTime: STALE,
    gcTime: GC,
    retry: (count, err) => {
      if (err?.response?.status === 404) return false;
      // Крупные страны: краткий Empty reply при рестарте backend.
      return count < 2;
    },
    retryDelay: (attempt) => 400 * 2 ** attempt,
  });
}

export function useWorldIndicator(slug, code) {
  const lk = useLocaleKey();
  return useQuery({
    queryKey: ['world-indicator', slug, code, lk],
    queryFn: ({ signal }) =>
      withMockFallback(
        () => api.get(`/world/indicators/${slug}/${code}`, { signal }),
        () => {
          const mock = WORLD_MOCK_INDICATOR[`${slug}/${code}`];
          if (!mock) {
            const err = new Error('Индикатор не найден');
            err.response = { status: 404 };
            throw err;
          }
          return mock;
        },
      ),
    enabled: !!slug && !!code,
    staleTime: STALE,
    gcTime: GC,
    retry: (count, err) => {
      if (err?.response?.status === 404) return false;
      return count < 1;
    },
  });
}

/**
 * Данные ряда. `requestCode` — primary или sibling (легаси-фолбэк);
 * `mode` — составной токен или легаси id (бэкенд принимает оба).
 */
export function useWorldIndicatorData(
  slug,
  code,
  mode,
  {
    from, to, requestCode, includeForecast = false,
  } = {},
) {
  const lk = useLocaleKey();
  const dataCode = requestCode || code;
  const FORECAST_SLOT = 4;
  const queryKey = ['world-indicator-data', slug, dataCode, mode, includeForecast, from, to, lk];
  return useQuery({
    queryKey,
    queryFn: ({ signal }) => {
      const params = {};
      if (mode) params.mode = mode;
      if (includeForecast) params.include_forecast = true;
      if (from) params.from = from;
      if (to) params.to = to;
      return withMockFallback(
        () => api.get(`/world/indicators/${slug}/${dataCode}/data`, { signal, params }),
        () => getWorldMockData(slug, dataCode, mode || 'level-monthly'),
      );
    },
    enabled: !!slug && !!dataCode && !!mode,
    // Тоггл «Прогноз» меняет queryKey: без placeholder карточка на refetch
    // на мгновение пустеет (телеметрия и таблица «(0)»). Держим прошлые точки
    // только если отличается один include_forecast — смена ряда/режима/окна
    // не должна на миг показывать чужие точки под новым заголовком.
    placeholderData: (previous, previousQuery) => {
      const prevKey = previousQuery?.queryKey;
      if (!prevKey || prevKey.length !== queryKey.length) return undefined;
      const sameSeries = queryKey.every((part, i) => i === FORECAST_SLOT || part === prevKey[i]);
      return sameSeries ? previous : undefined;
    },
    staleTime: STALE,
    gcTime: GC,
  });
}

export function useWorldSearch(q, { country, limit = 50, enabled = true } = {}) {
  const lk = useLocaleKey();
  const needle = (q || '').trim();
  return useQuery({
    queryKey: ['world-search', needle, country, limit, lk],
    queryFn: ({ signal }) =>
      withMockFallback(
        async () => ({ data: await fetchWorldSearch(needle, { country, limit }, { signal }) }),
        () => getWorldMockSearch(needle, country, limit),
      ),
    enabled: enabled && needle.length >= 1,
    staleTime: 60 * 1000,
    gcTime: GC,
  });
}

export function useWorldCompareCatalog({ enabled = true } = {}) {
  const lk = useLocaleKey();
  return useQuery({
    queryKey: ['world-compare-catalog', lk],
    queryFn: async ({ signal }) => (await api.get('/world/compare/catalog', { signal })).data,
    enabled,
    staleTime: STALE,
    gcTime: GC,
  });
}

/**
 * Показатели рейтинга стран: сервер отдаёт только курируемые понятия.
 * Денежные абсолюты в нацвалютах не входят, пока нет пересчёта.
 * Индексы цен с разными базами ранжируются как изменение за год (%).
 */
export function useWorldRatingConcepts({ enabled = true } = {}) {
  const lk = useLocaleKey();
  return useQuery({
    queryKey: ['world-rating-concepts', lk],
    queryFn: async ({ signal }) => (await api.get('/world/rating/concepts', { signal })).data,
    enabled,
    staleTime: STALE,
    gcTime: GC,
    retry: WORLD_SURFACE_RETRY,
  });
}


/** Ссылка на полный рейтинг, либо null, если показатель в рейтинг не идёт. */
export function ratingHref(conceptSlug, ratingConcepts) {
  if (!conceptSlug || !ratingConcepts?.length) return null;
  return ratingConcepts.some((item) => item.slug === conceptSlug)
    ? worldRatingPath(conceptSlug)
    : null;
}

/** Публичные пути карточки страны / индикатора (ADR-0013). */
export function worldCountryHref(countrySlug) {
  return countryPath(countrySlug);
}

export function worldIndicatorHref(countrySlug, indicatorCode) {
  return indicatorPath(countrySlug, indicatorCode);
}

export async function fetchWorldCompareSeries(countrySlug, conceptSlug, { signal } = {}) {
  return (await api.get(`/world/compare/series/${countrySlug}/${conceptSlug}`, { signal })).data;
}

/**
 * Compare URL is `w:{country}:{key}` where key is either a curated concept
 * (`unemployment-rate`) or a national indicator code (`us-unemployment-rate`).
 * Concept endpoint first; 404/409 fall through to the country card series.
 */
export async function fetchWorldCompareOrCard(countrySlug, seriesKey, { signal } = {}) {
  try {
    return await fetchWorldCompareSeries(countrySlug, seriesKey, { signal });
  } catch (err) {
    const status = err?.response?.status;
    if (status !== 404 && status !== 409) throw err;
  }
  const [metaResp, dataResp] = await Promise.all([
    api.get(`/world/indicators/${countrySlug}/${seriesKey}`, { signal }),
    api.get(`/world/indicators/${countrySlug}/${seriesKey}/data`, { signal }),
  ]);
  const loc = currentUiLocale();
  const country = metaResp.data?.country || {};
  const ind = metaResp.data?.indicator || {};
  const points = dataResp.data?.points || dataResp.data?.data || [];
  const countryName = loc === 'en'
    ? (country.name_en || country.name)
    : country.name;
  const seriesName = loc === 'en'
    ? (ind.name_en || ind.name)
    : ind.name;
  return {
    meta: {
      code: `w:${countrySlug}:${seriesKey}`,
      indicator_code: ind.code || seriesKey,
      country_slug: country.slug || countrySlug,
      country_name: countryName,
      country_name_en: country.name_en,
      concept_slug: ind.concept_slug || seriesKey,
      concept_name: seriesName,
      concept_name_en: ind.name_en,
      frequency: ind.frequency,
      unit: ind.unit,
    },
    data: points.map((point) => ({ date: point.date, value: point.value })),
  };
}

/** Официальный ряд curated-понятия (карточка страны / сравнение / калькулятор). */
export function useWorldCompareSeries(countrySlug, conceptSlug, { enabled = true } = {}) {
  const lk = useLocaleKey();
  return useQuery({
    queryKey: ['world-compare-series', countrySlug, conceptSlug, lk],
    queryFn: ({ signal }) => fetchWorldCompareSeries(countrySlug, conceptSlug, { signal }),
    enabled: enabled && !!countrySlug && !!conceptSlug,
    staleTime: STALE,
    gcTime: GC,
    retry: (count, err) => {
      if (err?.response?.status === 404) return false;
      return count < 1;
    },
  });
}

export async function fetchWorldIndicatorMode(countrySlug, indicatorCode, mode, { signal } = {}) {
  return (
    await api.get(`/world/indicators/${countrySlug}/${indicatorCode}/data`, {
      signal,
      params: { mode },
    })
  ).data;
}

export function useWorldCompareSnapshot(conceptSlug) {
  const lk = useLocaleKey();
  return useQuery({
    queryKey: worldCompareSnapshotQueryKey(conceptSlug, lk),
    queryFn: async ({ signal }) => (
      await api.get(`/world/compare/snapshot/${conceptSlug}`, { signal })
    ).data,
    enabled: !!conceptSlug,
    staleTime: STALE,
    gcTime: GC,
    retry: WORLD_SURFACE_RETRY,
  });
}

function worldMapSeriesOptions(conceptSlug, lk) {
  return {
    queryKey: worldMapSeriesQueryKey(conceptSlug, lk),
    queryFn: async ({ signal }) => (
      await api.get(`/world/compare/map-series/${conceptSlug}`, { signal })
    ).data,
    enabled: !!conceptSlug,
    staleTime: STALE,
    gcTime: GC,
    retry: WORLD_SURFACE_RETRY,
  };
}

/**
 * `keepPrevious`: при смене показателя страница рейтинга держит прежний срез на экране, пока приходит новый,
 * вместо серого каркаса; смену видно по `isPlaceholderData`.
 */
export function useWorldMapSeries(conceptSlug, { keepPrevious = false } = {}) {
  const lk = useLocaleKey();
  return useQuery({
    ...worldMapSeriesOptions(conceptSlug, lk),
    ...(keepPrevious ? { placeholderData: keepPreviousData } : {}),
  });
}

/** Подгрузить срез показателя заранее (наведение, фокус, касание, простой страницы): к нажатию он уже в кэше. */
export function prefetchWorldMapSeries(queryClient, conceptSlug, lk = localeKey()) {
  if (!queryClient || !conceptSlug) return Promise.resolve();
  return queryClient.prefetchQuery(worldMapSeriesOptions(conceptSlug, lk)).catch(() => {});
}

export async function fetchWorldAverageSeries(conceptSlug, mode, { signal } = {}) {
  return (
    await api.get(`/world/compare/average/${conceptSlug}`, {
      signal,
      params: mode ? { mode } : undefined,
    })
  ).data;
}

/**
 * Формат числа для витрины мира: RU — запятая и неразрывный пробел; EN — точка.
 * Переиспользует formatValue из lib/format.js.
 */
export function formatWorldValue(value, digits, locale) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  const abs = Math.abs(Number(value));
  let d = digits;
  if (d == null) {
    if (abs >= 10000) d = 0;
    else if (abs >= 100) d = 1;
    else d = abs < 1 ? 2 : 2;
  }
  return formatValue(value, d, locale);
}

const WORLD_UNIT_EN = Object.freeze({
  'млрд $': 'billion $',
  'млн $': 'million $',
  '$ на человека': '$ per person',
  '% экономически активного населения': '% of the labour force',
  '% эан': '% of the labour force',
  '% ЭАН': '% of the labour force',
  '% населения': '% of population',
  '% ВВП': '% of GDP',
  '% от среднего по ЕС на душу населения': '% of EU average per capita',
  'изменение за год, %': 'year-over-year change, %',
  'тыс. человек': 'ths persons',
  человек: 'people',
  пунктов: 'points',
  'млн чел.': 'million people',
  'млрд долларов США (цены 2017)': 'billion USD (2017 prices)',
});

/** Сокращения и коды, которые не нужны человеку рядом с числом. */
function tidyUnitEn(text) {
  return text
    .replace(/chain[- ]linked volumes,?\s*\(?(\d{4})\)?/i, 'in $1 prices')
    .replace(/\s*\(NSA\)/g, ', not seasonally adjusted')
    .replace(/\s*\(SCA\)/g, ', seasonally and calendar adjusted')
    .replace(/\s*\(SA\)/g, ', seasonally adjusted')
    .replace(/(\d{4})=100/g, '$1 = 100');
}

/** Английские подписи единиц, которые сервер мог отдать к русскому интерфейсу (смена языка, старый кэш). */
const WORLD_UNIT_RU = Object.freeze({
  'billion $': 'млрд $',
  'million $': 'млн $',
  '$ per person': '$ на человека',
  '% of the labour force': '% от рабочей силы',
  '% of population': '% населения',
  '% of gdp': '% ВВП',
  '% of eu average per capita': '% от среднего по ЕС на душу населения',
  'year-over-year change, %': 'изменение за год, %',
  'ths persons': 'тыс. человек',
  people: 'человек',
  persons: 'человек',
  points: 'пунктов',
  'million people': 'млн чел.',
});

function tidyUnitRu(text) {
  const known = WORLD_UNIT_RU[text.toLowerCase()];
  return (known || text)
    .replace(/%\s*ЭАН/gi, '% от рабочей силы')
    .replace(/(\d{4})=100/g, '$1 = 100');
}

/** Единица измерения для человека: на английском без русских подписей, на обоих языках без аббревиатур и кодов. */
export function localizeWorldUnit(unit, locale = 'ru') {
  const text = String(unit || '').trim();
  if (!text) return '';
  if (locale !== 'en') return tidyUnitRu(text);
  return tidyUnitEn(WORLD_UNIT_EN[text] || WORLD_UNIT_EN[text.toLowerCase()] || text);
}

/** Русское склонение (копия логики regionsApi — без кросс-импорта домена). */
export function pluralRu(n, [one, few, many]) {
  const abs = Math.abs(n) % 100;
  const d = abs % 10;
  if (abs > 10 && abs < 20) return many;
  if (d === 1) return one;
  if (d >= 2 && d <= 4) return few;
  return many;
}

/**
 * Стабильный id региона по подписи, которую отдал API. Подпись приходит уже на
 * языке страницы, поэтому карта покрывает оба написания: id нужен только для
 * порядка секций и якорей, наружу показывается сама подпись.
 */
const REGION_ID_BY_LABEL = Object.freeze({
  Европа: 'europe',
  Europe: 'europe',
  Америка: 'americas',
  Americas: 'americas',
  Азия: 'asia',
  Asia: 'asia',
  Африка: 'africa',
  Africa: 'africa',
  Океания: 'oceania',
  Oceania: 'oceania',
});

/** Порядок секций: Европа первой — там наибольшая глубина истории. */
const REGION_ORDER = Object.freeze(['europe', 'americas', 'asia', 'africa', 'oceania']);

/**
 * Закавказье по физической географии отнесено к Азии (в базе стоит «Европа»): страна не должна числиться
 * в Европе только из-за членства в европейских объединениях.
 */
const REGION_ID_BY_CODE = Object.freeze({ AZ: 'asia', AM: 'asia', GE: 'asia' });

export function countryRegionId(country) {
  if (country?.slug === 'russia' || country?.code === 'RU') return 'europe';
  if (REGION_ID_BY_CODE[country?.code]) return REGION_ID_BY_CODE[country.code];
  return REGION_ID_BY_LABEL[String(country?.region || '').trim()] || 'other';
}

/**
 * Страны по регионам в фиксированном порядке. Россия относится к Европе:
 * в мировом каталоге её нет, каркас подмешивается поверх и без явного
 * отнесения попадал бы в «прочие».
 */
export function groupCountriesByRegion(countries, { locale = 'ru' } = {}) {
  const collator = new Intl.Collator(locale === 'en' ? 'en' : 'ru');
  const map = new Map();
  for (const country of countries || []) {
    const id = countryRegionId(country);
    if (!map.has(id)) map.set(id, { id, region: '', countries: [] });
    const bucket = map.get(id);
    if (!bucket.region && country?.region && REGION_ID_BY_LABEL[String(country.region).trim()] === id) {
      bucket.region = country.region;
    }
    bucket.countries.push(country);
  }
  const rank = (id) => {
    const index = REGION_ORDER.indexOf(id);
    return index === -1 ? REGION_ORDER.length : index;
  };
  return [...map.values()]
    .map((group) => ({
      ...group,
      region: group.region || group.id,
      countries: [...group.countries].sort((a, b) => collator.compare(a.name || '', b.name || '')),
    }))
    .sort((a, b) => rank(a.id) - rank(b.id) || collator.compare(a.region, b.region));
}
