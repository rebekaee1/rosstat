import { filterSearchOptions } from './searchSynonyms';

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
