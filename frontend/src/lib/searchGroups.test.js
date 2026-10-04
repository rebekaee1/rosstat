import { describe, expect, it } from 'vitest';
import {
  SEARCH_PRIMARY_LIMIT, friendlySearchName, searchFamilyKey, splitSearchRows,
} from './searchGroups';

const nameOf = (row) => row.name;
const hicp = (key, extra = '') => ({
  key, kind: 'world', country_slug: 'germany', country_name: 'Германия', name: `Гармонизированный индекс потребительских цен${extra}`,
});

describe('splitSearchRows: вариации одного показателя сворачиваются', () => {
  it('пять вариаций «Гармонизированного индекса…» одной страны — одна строка, остальное в «ещё»', () => {
    const rows = [
      hicp('a'), hicp('b', ' (товары)'), hicp('c', ', услуги'), hicp('d', ' — энергия'),
      { key: 'e', kind: 'world', country_slug: 'germany', country_name: 'Германия', name: 'Безработица' },
    ];
    const { primary, more } = splitSearchRows(rows, nameOf);
    expect(primary.map((r) => r.key)).toEqual(['a', 'e']);
    expect(more.map((r) => r.key)).toEqual(['b', 'c', 'd']);
  });

  it('один показатель разных стран — разные семьи, ничего не прячется', () => {
    const rows = ['germany', 'france', 'italy'].map((slug, i) => ({
      key: String(i), kind: 'world', country_slug: slug, country_name: slug, name: 'ВВП',
    }));
    expect(splitSearchRows(rows, nameOf).more).toHaveLength(0);
  });

  it('длинная выдача режется по лимиту, порядок сервера сохраняется', () => {
    const rows = Array.from({ length: SEARCH_PRIMARY_LIMIT + 3 }, (_, i) => ({
      key: String(i), kind: 'world', country_slug: `c${i}`, country_name: `C${i}`, name: 'ВВП',
    }));
    const { primary, more } = splitSearchRows(rows, nameOf);
    expect(primary).toHaveLength(SEARCH_PRIMARY_LIMIT);
    expect(more.map((r) => r.key)).toEqual(['8', '9', '10']);
  });

  it('страны и регионы — каждая своя семья', () => {
    expect(searchFamilyKey({ kind: 'country', key: 'country:de' }, 'Германия'))
      .not.toBe(searchFamilyKey({ kind: 'country', key: 'country:fr' }, 'Франция'));
  });
});

describe('friendlySearchName', () => {
  const t = (key, vars) => `${key}:${vars?.country}`;
  it('индекс потребительских цен страны называет инфляцией', () => {
    expect(friendlySearchName(hicp('a'), hicp('a').name, t)).toBe('shell3.search.inflation:Германия');
    const en = { country_name: 'Germany' };
    expect(friendlySearchName(en, 'Harmonised index of consumer prices', t)).toBe('shell3.search.inflation:Germany');
  });
  it('остальные названия не трогает', () => {
    expect(friendlySearchName({ country_name: 'Германия' }, 'Безработица', t)).toBe('Безработица');
    expect(friendlySearchName({}, 'Гармонизированный индекс потребительских цен', t)).toBe('Гармонизированный индекс потребительских цен');
  });
});
