/**
 * Единая схема хлебных крошек (ADR-0013).
 * Зеркало backend `app/services/breadcrumbs.py`.
 */
import {
  calendarPath,
  countryPath,
  demographicsPath,
  indicatorPath,
  regionHubPath,
  regionIndicatorPath,
  regionPath,
  regionRatingHubPath,
  regionRatingPath,
  russiaCategoriesPath,
  russiaCategoryPath,
  russiaHomePath,
  russiaIndicatorPath,
  russiaIndicatorYearPath,
  todayPath,
  WORLD_RATING_DEFAULT_CONCEPT,
  worldRatingPath,
} from './sitePaths';
import { getSiteOrigin } from './siteOrigin';
import { t } from '../i18n/messages';

/** @typedef {{ path: string, name: string }} Crumb */

export function crumb(path, name) {
  return { path, name };
}

export function homeCrumb() {
  return crumb('/', t('crumb.home'));
}

export function russiaCrumb() {
  return crumb(russiaHomePath(), t('crumb.russia'));
}

export function russiaCategoriesCrumb() {
  return crumb(russiaCategoriesPath(), t('crumb.categories'));
}

export function regionsCrumb() {
  return crumb(regionHubPath(), t('crumb.regions'));
}

export function regionRatingsCrumb() {
  return crumb(regionRatingHubPath(), t('crumb.rating'));
}

/** Рейтинг стран. Ведёт на конкретный показатель: /world/rating без него — 301. */
export function worldRatingsCrumb() {
  return crumb(worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT), t('crumb.worldRating'));
}

export function russiaHomeTrail() {
  return [homeCrumb(), russiaCrumb()];
}

export function russiaCategoriesTrail() {
  return [homeCrumb(), russiaCrumb(), russiaCategoriesCrumb()];
}

export function russiaCategoryTrail(categoryName, categorySlug) {
  return [
    homeCrumb(),
    russiaCrumb(),
    russiaCategoriesCrumb(),
    crumb(russiaCategoryPath(categorySlug), categoryName),
  ];
}

export function russiaIndicatorTrail(categoryName, categorySlug, indicatorName, indicatorCode) {
  const items = [homeCrumb(), russiaCrumb()];
  if (categoryName && categorySlug) {
    items.push(crumb(russiaCategoryPath(categorySlug), categoryName));
  }
  items.push(crumb(russiaIndicatorPath(indicatorCode), indicatorName));
  return items;
}

/** Мировой рыночный ряд: без «Россия» — Главная / [категория] / показатель. */
export function globalMarketIndicatorTrail(
  categoryName,
  categorySlug,
  indicatorName,
  indicatorCode,
) {
  const items = [homeCrumb()];
  if (categoryName && categorySlug) {
    items.push(crumb(russiaCategoryPath(categorySlug), categoryName));
  }
  items.push(crumb(russiaIndicatorPath(indicatorCode), indicatorName));
  return items;
}

export function russiaIndicatorYearTrail(
  categoryName,
  categorySlug,
  indicatorName,
  indicatorCode,
  year,
) {
  return [
    ...russiaIndicatorTrail(categoryName, categorySlug, indicatorName, indicatorCode),
    crumb(russiaIndicatorYearPath(indicatorCode, year), String(year)),
  ];
}

export function globalMarketIndicatorYearTrail(
  categoryName,
  categorySlug,
  indicatorName,
  indicatorCode,
  year,
) {
  return [
    ...globalMarketIndicatorTrail(categoryName, categorySlug, indicatorName, indicatorCode),
    crumb(russiaIndicatorYearPath(indicatorCode, year), String(year)),
  ];
}

export function regionsTrail() {
  return [homeCrumb(), russiaCrumb(), regionsCrumb()];
}

export function regionTrail(regionName, regionSlug) {
  return [
    homeCrumb(),
    russiaCrumb(),
    regionsCrumb(),
    crumb(regionPath(regionSlug), regionName),
  ];
}

export function regionIndicatorTrail(regionName, regionSlug, indicatorName, indicatorCode) {
  return [
    homeCrumb(),
    russiaCrumb(),
    regionsCrumb(),
    crumb(regionPath(regionSlug), regionName),
    crumb(regionIndicatorPath(regionSlug, indicatorCode), indicatorName),
  ];
}

export function regionRatingHubTrail() {
  return [homeCrumb(), russiaCrumb(), regionsCrumb(), regionRatingsCrumb()];
}

export function regionRatingTrail(indicatorName, indicatorCode) {
  return [
    homeCrumb(),
    russiaCrumb(),
    regionsCrumb(),
    regionRatingsCrumb(),
    crumb(regionRatingPath(indicatorCode), indicatorName),
  ];
}

export function regionVsTrail(label, vsPath) {
  return [homeCrumb(), russiaCrumb(), regionsCrumb(), crumb(vsPath, label)];
}

export function todayTrail() {
  return [homeCrumb(), russiaCrumb(), crumb(todayPath(), t('crumb.today'))];
}

export function todayIndicatorTrail(label, code) {
  return [
    homeCrumb(),
    russiaCrumb(),
    crumb(todayPath(), t('crumb.today')),
    crumb(todayPath(code), label),
  ];
}

export function calendarTrail() {
  return [homeCrumb(), russiaCrumb(), crumb(calendarPath(), t('crumb.calendar'))];
}

export function calendarMonthTrail(label, year, month) {
  return [
    homeCrumb(),
    russiaCrumb(),
    crumb(calendarPath(), t('crumb.calendar')),
    crumb(calendarPath(year, month), label),
  ];
}

export function demographicsTrail() {
  return [homeCrumb(), russiaCrumb(), crumb(demographicsPath(), t('crumb.demographics'))];
}

export function worldCountryTrail(countryName, countrySlug) {
  return [homeCrumb(), crumb(countryPath(countrySlug), countryName)];
}

export function worldIndicatorTrail(countryName, countrySlug, indicatorName, indicatorCode) {
  return [
    homeCrumb(),
    crumb(countryPath(countrySlug), countryName),
    crumb(indicatorPath(countrySlug, indicatorCode), indicatorName),
  ];
}

export function worldRatingHubTrail() {
  return [homeCrumb(), worldRatingsCrumb()];
}

export function worldRatingTrail(name, conceptSlug) {
  return [
    homeCrumb(),
    worldRatingsCrumb(),
    crumb(worldRatingPath(conceptSlug), name),
  ];
}

export function toolTrail(name, path) {
  return [homeCrumb(), crumb(path, name)];
}

/** JSON-LD BreadcrumbList из trail (для CSR-страниц без SSR). */
export function breadcrumbJsonLd(items, origin = getSiteOrigin()) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: `${origin.replace(/\/$/, '')}${item.path}`,
    })),
  };
}
