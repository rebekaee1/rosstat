import { describe, expect, it } from 'vitest';
import { countryMatchesQuery, filterSearchCountries } from './worldCompareSearch';

describe('search in a supplied country eligibility pool', () => {
  const options = [
    { country_slug: 'germany', country_name: 'Германия', code: 'peer:de' },
    { country_slug: 'russia', country_name: 'Россия', code: 'peer:ru' },
    { country_slug: 'united-states', country_name: 'США', code: 'peer:us' },
  ];

  it('supports bilingual names, short codes and country aliases', () => {
    expect(filterSearchCountries(options, 'Germany')).toEqual([options[0]]);
    expect(filterSearchCountries(options, 'РФ')).toEqual([options[1]]);
    expect(filterSearchCountries(options, 'USA')).toEqual([options[2]]);
    expect(countryMatchesQuery(options[0], 'герм')).toBe(true);
  });

  it('recovers a typo/layout without adding an unavailable country', () => {
    expect(filterSearchCountries(options, 'Germny')).toEqual([options[0]]);
    expect(filterSearchCountries(options, 'uhtvfybz')).toEqual([options[0]]);
    expect(filterSearchCountries(options, 'France')).toEqual([]);
  });

  it('requires all qualifiers and preserves empty-query ordering', () => {
    expect(filterSearchCountries(options, 'Germany France')).toEqual([]);
    expect(filterSearchCountries(options, '')).toEqual(options);
  });
});
