import { filterSearchOptions } from './searchSynonyms';
import { POPULAR_COUNTRY_SLUGS } from './countryFlag';

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

/** Страны для чипов «Сравнить с:»: на первых местах те, что чаще всего сравнивают, остальные в порядке списка. */
export function suggestedCompareOptions(options, locale, limit = 5) {
  const popular = POPULAR_COUNTRY_SLUGS[locale === 'en' ? 'en' : 'ru'] || [];
  const real = (options || []).filter((item) => item.code !== 'average' && item.country_slug);
  const rank = (item) => {
    const index = popular.indexOf(item.country_slug);
    return index < 0 ? 999 : index;
  };
  return [...real]
    .sort((a, b) => rank(a) - rank(b))
    .slice(0, limit);
}
