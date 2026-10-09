import { filterSearchOptions } from './searchSynonyms';
import { POPULAR_COUNTRY_SLUGS } from './countryFlag';
import { neighborsOf } from './countryNeighbors';
import { gdpRank } from './countryOrder';

export function filterSearchCountries(options, query) {
  return filterSearchOptions(options, query, {
    searchKind: 'country',
    getSearchItem: (option) => ({
      ...option,
      name: option.country_name || option.name || option.label,
      name_en: option.country_name_en || option.name_en,
      slug: option.country_slug || option.slug || option.key,
      code: option.country_code || option.code,
    }),
  });
}

export function countryMatchesQuery(option, query) {
  return filterSearchCountries([option], query).length > 0;
}

/**
 * Страны для чипов «Сравнить с:». Без `currentSlug` на первых местах те, что чаще всего сравнивают.
 * С `currentSlug` (страница страны): сама страна не предлагается, дальше до трёх соседей по региону,
 * остальное места заполняют страны, ближайшие по размеру ВВП (круг 11: у Турции были Германия, Франция, Австрия, Албания, Бельгия).
 */
export function suggestedCompareOptions(options, locale, limit = 5, { currentSlug } = {}) {
  const popular = POPULAR_COUNTRY_SLUGS[locale === 'en' ? 'en' : 'ru'] || [];
  const real = (options || []).filter((item) => item.code !== 'average' && item.country_slug && item.country_slug !== currentSlug);
  if (!currentSlug) {
    const rank = (item) => {
      const index = popular.indexOf(item.country_slug);
      return index < 0 ? 999 : index;
    };
    return [...real]
      .sort((a, b) => rank(a) - rank(b))
      .slice(0, limit);
  }
  const bySlug = new Map(real.map((item) => [item.country_slug, item]));
  const near = neighborsOf(currentSlug).map((slug) => bySlug.get(slug)).filter(Boolean).slice(0, Math.min(3, Math.max(0, limit - 2)));
  const taken = new Set(near.map((item) => item.country_slug));
  const own = gdpRank(currentSlug);
  const close = real
    .filter((item) => !taken.has(item.country_slug))
    .sort((a, b) => Math.abs(gdpRank(a.country_slug) - own) - Math.abs(gdpRank(b.country_slug) - own)
      || gdpRank(a.country_slug) - gdpRank(b.country_slug));
  return [...near, ...close].slice(0, limit);
}
