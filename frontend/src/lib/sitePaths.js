/**
 * Единая точка построения публичных путей (ADR-0013, path-cut).
 * Зеркало backend `app/services/site_paths.py` — держать синхронно.
 *
 * Тип сущности назван явно: /{country}/indicator/{code}, /russia/region/{slug}.
 * Показатели и регионы не делят одно пространство имён.
 */

export const RUSSIA = 'russia';

/** Первые сегменты, запрещённые как слаг страны/региона. */
export const RESERVED_FIRST_SEGMENTS = Object.freeze([
  'about',
  'methodology',
  'privacy',
  'terms',
  'calculator',
  'compare',
  'widgets',
  'login',
  'register',
  'account',
  'admin',
  'world',
  'api',
  'assets',
  'og',
  'og-proxy',
  'embed',
  'health',
  'fonts',
  'feed.xml',
  'robots.txt',
  'consent.js',
  'sitemap.xml',
  'indicator',
  'category',
  'today',
  'calendar',
  'demographics',
  'regions',
  'region',
  'region-rating',
  'region-vs',
]);

export function isReservedFirstSegment(segment) {
  if (!segment) return true;
  const s = String(segment).toLowerCase().replace(/^\/+|\/+$/g, '');
  if (RESERVED_FIRST_SEGMENTS.includes(s)) return true;
  if (s.startsWith('sitemap') && s.endsWith('.xml')) return true;
  return false;
}

function slug(value) {
  const s = String(value || '').trim().replace(/^\/+|\/+$/g, '');
  if (!s) throw new Error('empty slug');
  return s;
}

function code(value) {
  const s = String(value || '').trim().replace(/^\/+|\/+$/g, '');
  if (!s) throw new Error('empty code');
  return s;
}

export function homePath() {
  return '/';
}

export function comparePath() {
  return '/compare';
}

export function countryPath(countrySlug) {
  return `/${slug(countrySlug)}`;
}

export function indicatorPath(countrySlug, indicatorCode) {
  return `/${slug(countrySlug)}/indicator/${code(indicatorCode)}`;
}

export function indicatorYearPath(countrySlug, indicatorCode, year) {
  return `${indicatorPath(countrySlug, indicatorCode)}/${Number(year)}`;
}

export function categoryPath(countrySlug, categorySlug) {
  return `/${slug(countrySlug)}/category/${slug(categorySlug)}`;
}

export function russiaHomePath() {
  return countryPath(RUSSIA);
}

/** Раздел России: главная страны, регионы, категории, сегодня. */
export function isRussiaSectionPath(pathname) {
  if (!pathname) return false;
  if (pathname === `/${RUSSIA}` || pathname.startsWith(`/${RUSSIA}/`)) return true;
  if (pathname === '/today' || pathname.startsWith('/today/')) return true;
  return false;
}

export function russiaIndicatorPath(indicatorCode) {
  return indicatorPath(RUSSIA, indicatorCode);
}

export function russiaIndicatorYearPath(indicatorCode, year) {
  return indicatorYearPath(RUSSIA, indicatorCode, year);
}

export function russiaCategoryPath(categorySlug) {
  return categoryPath(RUSSIA, categorySlug);
}

export function russiaCategoriesPath() {
  return `/${RUSSIA}/category`;
}

export function regionHubPath() {
  return `/${RUSSIA}/region`;
}

export function regionRatingHubPath() {
  return `/${RUSSIA}/region-rating`;
}

export function regionPath(regionSlug) {
  return `/${RUSSIA}/region/${slug(regionSlug)}`;
}

export function regionIndicatorPath(regionSlug, indicatorCode) {
  return `/${RUSSIA}/region/${slug(regionSlug)}/${code(indicatorCode)}`;
}

export function regionMapPath(indicatorCode) {
  return `/${RUSSIA}/region/map/${code(indicatorCode)}`;
}

export function regionRatingPath(indicatorCode) {
  return `/${RUSSIA}/region-rating/${code(indicatorCode)}`;
}

export function regionVsPath(slugA, slugB) {
  return `/${RUSSIA}/region-vs/${slug(slugA)}-vs-${slug(slugB)}`;
}

export function todayPath(indicatorCode) {
  return indicatorCode ? `/${RUSSIA}/today/${code(indicatorCode)}` : `/${RUSSIA}/today`;
}

export function calendarPath(year, month) {
  if (year == null) return `/${RUSSIA}/calendar`;
  if (month == null) return `/${RUSSIA}/calendar/${Number(year)}`;
  return `/${RUSSIA}/calendar/${Number(year)}/${String(Number(month)).padStart(2, '0')}`;
}

export function demographicsPath() {
  return `/${RUSSIA}/demographics`;
}

/**
 * Каталог стран живёт на главной; отдельная витрина `/world` снята и 301-ится.
 * Путь оставлен для карты легаси-редиректов и тестов — новыми ссылками не пользуемся.
 */
export function worldHubPath() {
  return '/world';
}

/** Показатель рейтинга по умолчанию: `/world/rating` без него 301-ится сюда. */
export const WORLD_RATING_DEFAULT_CONCEPT = 'gdp-usd';

export function worldRatingPath(concept) {
  return concept ? `/world/rating/${slug(concept)}` : '/world/rating';
}

/** @deprecated use countryPath — оставлено для читаемости в world-коде */
export function worldCountryPath(countrySlug) {
  return countryPath(countrySlug);
}

/** @deprecated use indicatorPath */
export function worldIndicatorPath(countrySlug, indicatorCode) {
  return indicatorPath(countrySlug, indicatorCode);
}
