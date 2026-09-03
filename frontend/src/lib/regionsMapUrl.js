// URL-схема карты регионов (ADR-0013):
//   Канон:  /russia/region/map/{code}
//           /russia/region/map/{code}?year=YYYY
//           /russia/region/map/overview
//   Список: /russia/region
//
// Legacy (клиентский Navigate / nginx 301):
//   /regions, /regions/map/{code}, /regions?view=map&indicator=…
//
// /russia/region-rating/{code} — другая поверхность (таблица мест), не путать.

import { regionHubPath, regionMapPath } from './sitePaths';

export const MAP_OVERVIEW = 'overview';

/** Совпадает с MAP_METRICS[0] и backend DEFAULT_MAP_CODE. */
export const DEFAULT_MAP_CODE =
  'srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy';

function parseYear(searchParams) {
  const yearRaw = searchParams.get('year');
  return yearRaw && /^\d{4}$/.test(yearRaw) ? Number(yearRaw) : null;
}

/**
 * @param {URLSearchParams} searchParams
 * @returns {{ view: 'map'|'list', indicator: string|null, year: number|null }}
 */
export function parseRegionsMapParams(searchParams) {
  const view = searchParams.get('view') === 'map' ? 'map' : 'list';
  const raw = searchParams.get('indicator');
  const indicator = raw && /^[a-z0-9-]+$/i.test(raw) ? raw : null;
  return { view, indicator, year: parseYear(searchParams) };
}

/**
 * Парсит канон /russia/region/map/:code и legacy /regions(/map/:code).
 * @param {string} pathname
 * @param {URLSearchParams} searchParams
 */
export function parseRegionsMapLocation(pathname, searchParams) {
  const year = parseYear(searchParams);
  const canon = pathname.match(/^\/russia\/region\/map\/([a-z0-9-]+)\/?$/i);
  if (canon) {
    return { view: 'map', indicator: canon[1], year };
  }
  const legacyMap = pathname.match(/^\/regions\/map\/([a-z0-9-]+)\/?$/i);
  if (legacyMap) {
    return { view: 'map', indicator: legacyMap[1], year };
  }
  if (
    pathname === '/russia/region'
    || pathname === '/russia/region/'
    || pathname === '/regions'
    || pathname === '/regions/'
  ) {
    return parseRegionsMapParams(searchParams);
  }
  return { view: 'list', indicator: null, year: null };
}

/**
 * Канонический pathname + search для состояния карты.
 * @returns {{ pathname: string, search: string }}
 */
export function buildRegionsMapLocation({
  view = 'list',
  indicator = null,
  year = null,
} = {}) {
  if (view !== 'map') {
    return { pathname: regionHubPath(), search: '' };
  }
  const code = indicator || DEFAULT_MAP_CODE;
  const p = new URLSearchParams();
  if (code !== MAP_OVERVIEW && year != null) {
    p.set('year', String(year));
  }
  const qs = p.toString();
  return {
    pathname: regionMapPath(code),
    search: qs ? `?${qs}` : '',
  };
}

/** Полный path для meta/canonical/share. */
export function buildRegionsMapHref(state) {
  const { pathname, search } = buildRegionsMapLocation(state);
  return `${pathname}${search}`;
}

/**
 * @deprecated legacy query builder — оставлен для тестов миграции; новые
 * шаринги идут через buildRegionsMapLocation / buildRegionsMapHref.
 */
export function buildRegionsMapSearchParams({
  view = 'list',
  indicator = null,
  year = null,
} = {}) {
  const p = new URLSearchParams();
  if (view !== 'map') return p;
  p.set('view', 'map');
  if (indicator) p.set('indicator', indicator);
  if (indicator !== MAP_OVERVIEW && year != null) {
    p.set('year', String(year));
  }
  return p;
}

/** Сравнивает два URLSearchParams по сериализованному виду. */
export function searchParamsEqual(a, b) {
  return a.toString() === b.toString();
}

export function locationsEqual(a, b) {
  return a.pathname === b.pathname && a.search === b.search;
}

/**
 * Первый кадр карты: choropleth из heatmap последнего года.
 * heatmap-series (все годы) нужен ползунку и GIF — его можно догрузить следом.
 * Если в URL уже есть год и он есть в series — берём его, не вспышку последнего.
 */
export function resolveRegionsMapPaint({ heatmap = null, series = null, urlYear = null } = {}) {
  const seriesYears = Array.isArray(series?.years) ? series.years : [];
  const heatYear = heatmap?.year ?? null;
  const lastYear = series?.last_year
    ?? (seriesYears.length ? seriesYears[seriesYears.length - 1] : heatYear);

  let year = lastYear;
  if (urlYear != null && seriesYears.includes(urlYear)) {
    year = urlYear;
  } else if (urlYear != null && heatYear === urlYear) {
    year = urlYear;
  }

  let valuesBySlug = null;
  const seriesSlice = year != null ? series?.values_by_year?.[String(year)] : null;
  if (seriesSlice) {
    valuesBySlug = new Map(Object.entries(seriesSlice));
  } else if (heatmap?.values?.length && (year == null || year === heatYear)) {
    valuesBySlug = new Map();
    for (const row of heatmap.values) {
      if (row?.slug != null && row.value != null) {
        valuesBySlug.set(row.slug, row.value);
      }
    }
    year = heatYear;
  }

  const years = seriesYears.length ? seriesYears : (heatYear != null ? [heatYear] : []);
  return {
    year,
    years,
    valuesBySlug,
    indicator: series?.indicator || heatmap?.indicator || null,
    hasHistory: seriesYears.length > 1,
  };
}
