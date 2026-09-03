// API-слой мирового блока (bounded context «Мировая экономика»).
// Отдельно от макро/регионов: своя ось (страна × индикатор × mode).
// Факты и quality-gated прогнозы остаются в отдельном world API.
import { useQuery } from '@tanstack/react-query';
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
import { resolveBrowserLocale } from '../i18n/locale';

/** Лимит выдачи для глобальной палитры ⌘K (Россия + мир). */
export const WORLD_GLOBAL_SEARCH_LIMIT = 100;

const STALE = 10 * 60 * 1000;
const GC = 30 * 60 * 1000;
/** Главная: не крутить RQ retry×2 на тяжёлых world-запросах (скелетон карты, не пустой hero). */
const WORLD_SURFACE_RETRY = 1;

/** Locale in queryKey — иначе preview_locale=en оставляет RU payload в кэше. */
function localeKey() {
  return resolveBrowserLocale();
}

/**
 * Фолбэк на фикстуры — ТОЛЬКО в dev, пока backend /world не подключён.
 * В проде выдуманные значения показывать нельзя ни при каких ошибках: это
 * misleading-данные на публичной витрине, а не удобство разработки.
 */
function shouldUseMock(err) {
  if (!import.meta.env.DEV) return false;
  const status = err?.response?.status;
  return status === 404 || status === 502 || status === 503 || status == null;
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

export function useWorldCountries() {
  return useQuery({
    queryKey: ['world-countries', localeKey()],
    queryFn: ({ signal }) =>
      withMockFallback(
        () => api.get('/world/countries', { signal }),
        () => WORLD_MOCK_COUNTRIES,
      ),
    staleTime: STALE,
    gcTime: GC,
    retry: WORLD_SURFACE_RETRY,
  });
}

export function useWorldCountry(slug, { enabled = true } = {}) {
  return useQuery({
    queryKey: ['world-country', slug, localeKey()],
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
  return useQuery({
    queryKey: ['world-indicator', slug, code, localeKey()],
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
  const dataCode = requestCode || code;
  return useQuery({
    queryKey: ['world-indicator-data', slug, dataCode, mode, includeForecast, from, to, localeKey()],
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
    staleTime: STALE,
    gcTime: GC,
  });
}

export function useWorldSearch(q, { country, limit = 50, enabled = true } = {}) {
  const needle = (q || '').trim();
  return useQuery({
    queryKey: ['world-search', needle, country, limit, localeKey()],
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
  return useQuery({
    queryKey: ['world-compare-catalog', localeKey()],
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
  return useQuery({
    queryKey: ['world-rating-concepts', localeKey()],
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

/** Официальный ряд curated-понятия (карточка страны / сравнение / калькулятор). */
export function useWorldCompareSeries(countrySlug, conceptSlug, { enabled = true } = {}) {
  return useQuery({
    queryKey: ['world-compare-series', countrySlug, conceptSlug, localeKey()],
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
  return useQuery({
    queryKey: ['world-compare-snapshot', conceptSlug, localeKey()],
    queryFn: async ({ signal }) => (
      await api.get(`/world/compare/snapshot/${conceptSlug}`, { signal })
    ).data,
    enabled: !!conceptSlug,
    staleTime: STALE,
    gcTime: GC,
  });
}

export function useWorldMapSeries(conceptSlug) {
  return useQuery({
    queryKey: ['world-map-series', conceptSlug, localeKey()],
    queryFn: async ({ signal }) => (
      await api.get(`/world/compare/map-series/${conceptSlug}`, { signal })
    ).data,
    enabled: !!conceptSlug,
    staleTime: STALE,
    gcTime: GC,
    retry: WORLD_SURFACE_RETRY,
  });
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
 * Формат числа для витрины мира: русская запятая, неразрывный пробел.
 * Переиспользует formatValue из lib/format.js.
 */
export function formatWorldValue(value, digits) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  const abs = Math.abs(Number(value));
  let d = digits;
  if (d == null) {
    if (abs >= 10000) d = 0;
    else if (abs >= 100) d = 1;
    else d = abs < 1 ? 2 : 2;
  }
  return formatValue(value, d);
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

export function countryRegionId(country) {
  if (country?.slug === 'russia' || country?.code === 'RU') return 'europe';
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
    if (!bucket.region && country?.region) bucket.region = country.region;
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
