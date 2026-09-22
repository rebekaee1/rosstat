/**
 * Locale-aware footer columns (sources + home-country).
 * RU keeps the Russia column; EN swaps it for United States.
 */

import {
  calendarPath,
  countryPath,
  countryRegionsPath,
  demographicsPath,
  indicatorPath,
  regionHubPath,
  russiaHomePath,
} from './sitePaths';

export const US_SLUG = 'united-states';

/** Подпись ведомства остаётся, клик ведёт на соответствующий раздел сайта. */
export const FOOTER_SOURCE_LINKS_BY_LOCALE = {
  ru: [
    { to: '/#countries', key: 'footer.eurostat' },
    { to: '/#countries', key: 'footer.imf' },
    { to: '/russia', key: 'footer.rosstat' },
    { to: '/russia/indicator/key-rate', key: 'footer.cbr' },
    { to: '/russia/indicator/budget-deficit', key: 'footer.minfin' },
  ],
  en: [
    { to: '/#countries', key: 'footer.eurostat' },
    { to: '/#countries', key: 'footer.imf' },
    { to: '/united-states/indicator/us-unemployment-rate', key: 'footer.bls' },
    { to: '/united-states/indicator/us-gdp-real', key: 'footer.bea' },
    { to: '/united-states', key: 'footer.fred' },
    { to: '/united-states/regions', key: 'footer.census' },
  ],
};

export function footerSourceLinks(locale) {
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
      { to: regionHubPath(), key: 'footer.regions' },
      { to: calendarPath(), key: 'footer.calendar' },
      { to: demographicsPath(), key: 'footer.demographics' },
    ],
  };
}
