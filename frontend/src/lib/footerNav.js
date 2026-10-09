/**
 * Locale-aware footer columns (sources + home-country).
 * RU keeps the Russia column; EN swaps it for United States.
 */

import { FORECASTS_TO, RATES_TO } from './navItems';
import {
  calendarPath,
  comparePath,
  countryPath,
  countryRegionsPath,
  demographicsPath,
  indicatorPath,
  isRussiaSectionPath,
  regionHubPath,
  regionRatingHubPath,
  russiaHomePath,
  todayPath,
  WORLD_RATING_DEFAULT_CONCEPT,
  worldRatingPath,
} from './sitePaths';

export const US_SLUG = 'united-states';

/**
 * Источники данных в футере и на «О проекте» основного SPA: официальные сайты
 * ведомств (внешние, в новой вкладке). SEO-страницы ведут на разделы сайта
 * отдельно, в backend seo_renderer/seo_world.
 */
export const FOOTER_SOURCE_LINKS_BY_LOCALE = {
  ru: [
    { href: 'https://ec.europa.eu/eurostat', key: 'footer.eurostat' },
    { href: 'https://www.imf.org', key: 'footer.imf' },
    { href: 'https://rosstat.gov.ru', key: 'footer.rosstat' },
    { href: 'https://cbr.ru', key: 'footer.cbr' },
    { href: 'https://minfin.gov.ru', key: 'footer.minfin' },
  ],
  en: [
    { href: 'https://ec.europa.eu/eurostat', key: 'footer.eurostat' },
    { href: 'https://www.imf.org', key: 'footer.imf' },
    { href: 'https://www.bls.gov', key: 'footer.bls' },
    { href: 'https://www.bea.gov', key: 'footer.bea' },
    { href: 'https://fred.stlouisfed.org', key: 'footer.fred' },
    { href: 'https://www.census.gov', key: 'footer.census' },
  ],
};

/**
 * Круг 11, G (U19): английский список (США и Евросоюз) не должен стоять под страницами России и Турции, чьи данные из других источников.
 * Страница страны задаёт своё: Россия — Росстат, Банк России, Минфин и международные МВФ/Евростат; Турция — МВФ, Евростат и Банк России
 * (курс лиры к рублю). Прочие страницы остаются как были. Русский список уже содержит оба набора, он от страницы не зависит.
 */
const EN_CONTEXT_SOURCES = {
  russia: ['footer.rosstat', 'footer.cbr', 'footer.minfin', 'footer.imf', 'footer.eurostat'],
  turkey: ['footer.imf', 'footer.eurostat', 'footer.cbr'],
};

const ALL_SOURCE_ITEMS = Object.fromEntries(
  [...FOOTER_SOURCE_LINKS_BY_LOCALE.ru, ...FOOTER_SOURCE_LINKS_BY_LOCALE.en].map((item) => [item.key, item]),
);

/** Какой страной занята страница: 'russia' (раздел России, валюты), 'turkey' или null. */
export function sourceContextFor(pathname = '') {
  const p = String(pathname || '');
  if (isRussiaSectionPath(p) || p === '/currencies' || p.startsWith('/currencies/')) return 'russia';
  if (p === '/turkey' || p.startsWith('/turkey/')) return 'turkey';
  return null;
}

export function footerSourceLinks(locale, pathname = '') {
  if (locale === 'en') {
    const context = sourceContextFor(pathname);
    if (context) return EN_CONTEXT_SOURCES[context].map((key) => ALL_SOURCE_ITEMS[key]);
  }
  return FOOTER_SOURCE_LINKS_BY_LOCALE[locale] || FOOTER_SOURCE_LINKS_BY_LOCALE.ru;
}

/**
 * EN catalogue column: the Russia category shelf is a Russia-only concept, so the
 * international storefront lists the largest economies instead (order = nominal
 * GDP ranking on the home map). Labels are country names, no i18n key needed.
 */
export const FOOTER_TOP_COUNTRIES_EN = [
  { slug: 'united-states', label: 'United States' },
  { slug: 'china', label: 'China' },
  { slug: 'germany', label: 'Germany' },
  { slug: 'japan', label: 'Japan' },
  { slug: 'united-kingdom', label: 'United Kingdom' },
  { slug: 'india', label: 'India' },
  { slug: 'france', label: 'France' },
  { slug: 'russia', label: 'Russia' },
  { slug: 'italy', label: 'Italy' },
  { slug: 'canada', label: 'Canada' },
  { slug: 'brazil', label: 'Brazil' },
  { slug: 'spain', label: 'Spain' },
];

export function footerCatalogColumn(locale) {
  if (locale === 'en') {
    return {
      kind: 'countries',
      headingKey: 'footer.countries',
      headingTo: '/#countries',
      links: FOOTER_TOP_COUNTRIES_EN.map((c) => ({
        key: c.slug,
        to: countryPath(c.slug),
        label: c.label,
      })),
    };
  }
  return { kind: 'categories', headingKey: 'footer.categories', headingTo: null, links: [] };
}

export function footerHomeCountryColumn(locale) {
  if (locale === 'en') {
    return {
      sectionKey: 'footer.section.unitedStates',
      links: [
        { to: countryPath(US_SLUG), key: 'footer.unitedStates' },
        { to: indicatorPath(US_SLUG, 'us-unemployment-rate'), key: 'footer.usUnemployment' },
        { to: indicatorPath(US_SLUG, 'us-cpi-all'), key: 'footer.usCpi' },
        { to: indicatorPath(US_SLUG, 'us-gdp-real'), key: 'footer.usGdp' },
        { to: indicatorPath(US_SLUG, 'us-policy-rate'), key: 'footer.usFedRate' },
        { to: countryRegionsPath(US_SLUG), key: 'footer.usStates' },
        // `/world` 301 → home; the live catalogue is the home country list.
        { to: '/#countries', key: 'footer.allCountries' },
      ],
    };
  }
  return {
    sectionKey: 'footer.section.russia',
    links: [
      { to: russiaHomePath(), key: 'footer.russia' },
      { to: todayPath(), key: 'footer.economyToday' },
      { to: regionHubPath(), key: 'footer.regions' },
      { to: regionRatingHubPath(), key: 'footer.regionRatings' },
      { to: calendarPath(), key: 'footer.calendar' },
      { to: demographicsPath(), key: 'footer.demographics' },
    ],
  };
}

/**
 * Колонка «Мир». На EN сюда же вынесены российские хабы: в колонке страны
 * там США, а «Сегодня» и рейтинги регионов иначе пропадают из графа после
 * гидрации (в серверной шапке они есть, в клиентском меню — нет).
 */
export function footerWorldLinks(locale) {
  const links = [
    { to: '/#countries', key: 'footer.countries' },
    { to: worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT), key: 'footer.worldRating' },
    { to: comparePath(), key: 'footer.compare' },
    { to: FORECASTS_TO, key: 'w6b.nav.forecasts' },
    { to: RATES_TO, key: 'z2.nav.rates' },
  ];
  if (locale === 'en') {
    links.push(
      { to: todayPath(), key: 'footer.economyToday' },
      { to: regionRatingHubPath(), key: 'footer.regionRatings' },
      { to: calendarPath(), key: 'footer.calendar' },
      { to: demographicsPath(), key: 'footer.demographics' },
    );
  }
  return links;
}

/** Колонка «Инструменты»: конвертер валют первым, затем три калькулятора. */
export function footerToolLinks() {
  return [
    { to: RATES_TO, key: 'z2.tools.converter' },
    { to: '/calculator', key: 'footer.calcInflation' },
    { to: '/calculator/mortgage', key: 'footer.calcMortgage' },
    { to: '/calculator/compound', key: 'footer.calcCompound' },
  ];
}
