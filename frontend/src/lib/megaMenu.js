/**
 * Содержимое мега-панели «Страны мира» в шапке: флаги крупнейших экономик и популярные рейтинги.
 * Названия стран — данные, а не тексты интерфейса: русские названия лежат здесь рядом с кодами флагов.
 * Список и порядок совпадают с колонкой стран в подвале английской версии (по размеру экономики).
 */
import { countryFlag } from './countryFlag';
import { FOOTER_TOP_COUNTRIES_EN } from './footerNav';
import { countryPath, worldRatingPath } from './sitePaths';

const COUNTRY_META = {
  'united-states': { code: 'US', ru: 'США' },
  china: { code: 'CN', ru: 'Китай' },
  germany: { code: 'DE', ru: 'Германия' },
  japan: { code: 'JP', ru: 'Япония' },
  'united-kingdom': { code: 'GB', ru: 'Великобритания' },
  india: { code: 'IN', ru: 'Индия' },
  france: { code: 'FR', ru: 'Франция' },
  russia: { code: 'RU', ru: 'Россия' },
  italy: { code: 'IT', ru: 'Италия' },
  canada: { code: 'CA', ru: 'Канада' },
  brazil: { code: 'BR', ru: 'Бразилия' },
  spain: { code: 'ES', ru: 'Испания' },
};

/** Страны для панели: `[{ slug, to, flag, label }]` на языке посетителя. */
export function megaCountries(locale) {
  return FOOTER_TOP_COUNTRIES_EN.map((country) => {
    const meta = COUNTRY_META[country.slug];
    return {
      slug: country.slug,
      to: countryPath(country.slug),
      flag: countryFlag(meta?.code),
      label: locale === 'en' || !meta ? country.label : meta.ru,
    };
  });
}

const POPULAR_CONCEPTS = [
  { slug: 'gdp-usd', labelKey: 'z2.mega.gdp' },
  { slug: 'gdp-per-capita-usd', labelKey: 'z2.mega.gdpPerCapita' },
  { slug: 'unemployment-rate', labelKey: 'z2.mega.unemployment' },
  { slug: 'government-debt-gdp', labelKey: 'z2.mega.debt' },
  { slug: 'population', labelKey: 'z2.mega.population' },
];

/** Популярные рейтинги стран: `[{ slug, to, labelKey }]`. */
export function megaIndicators() {
  return POPULAR_CONCEPTS.map((item) => ({ ...item, to: worldRatingPath(item.slug) }));
}
