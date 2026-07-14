// URL-схема карты регионов:
//   Канон:  /regions/map/{code}           — показатель на карте
//           /regions/map/{code}?year=YYYY — выбранный год ползунка
//           /regions/map/overview         — режим «Обзор»
//   Список: /regions
//
// Legacy (prod 9226c77, SSR 301 → канон):
//   /regions?view=map&indicator=<code|overview>&year=YYYY
//
// /region-rating/{code} — другая поверхность (таблица мест), не путать.

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
 * Парсит канон /regions/map/:code и legacy query на /regions.
 * @param {string} pathname
 * @param {URLSearchParams} searchParams
 */
export function parseRegionsMapLocation(pathname, searchParams) {
  const year = parseYear(searchParams);
  const m = pathname.match(/^\/regions\/map\/([a-z0-9-]+)\/?$/i);
  if (m) {
    return { view: 'map', indicator: m[1], year };
  }
  if (pathname === '/regions' || pathname === '/regions/') {
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
    return { pathname: '/regions', search: '' };
  }
  const code = indicator || DEFAULT_MAP_CODE;
  const p = new URLSearchParams();
  if (code !== MAP_OVERVIEW && year != null) {
    p.set('year', String(year));
  }
  const qs = p.toString();
  return {
    pathname: `/regions/map/${code}`,
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
