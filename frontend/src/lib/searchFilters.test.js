import { describe, expect, it } from 'vitest';
import {
  EMPTY_FILTERS, activeFilterCount, applySearchFilters, buildFilterOptions, searchBasisOf, searchCountryOf, searchSourceOf,
} from './searchFilters';

const world = (over) => ({ kind: 'world', country_slug: 'turkey', country_name: 'Турция', frequency: 'monthly', unit: '%', ...over });

describe('searchSourceOf', () => {
  it('узнаёт МВФ, Евростат, национальные ряды и Россию', () => {
    expect(searchSourceOf(world({ code: 'tr-weo-pcpipch' }))).toBe('imf');
    expect(searchSourceOf(world({ code: 'tr-prc_hicp_midx-cp00-i15' }))).toBe('eurostat');
    expect(searchSourceOf(world({ code: 'tr-tec00118-total-rch-a-avg' }))).toBe('eurostat');
    expect(searchSourceOf(world({ code: 'us-policy-rate' }))).toBe('national');
    expect(searchSourceOf({ kind: 'russia', code: 'cpi-yoy' })).toBe('ru');
    expect(searchSourceOf({ kind: 'subnational_indicator', code: 'unemployment' })).toBe('ru');
  });
  it('доверяет полю source, если сервер его начнёт отдавать', () => {
    expect(searchSourceOf(world({ code: 'x', source: 'Евростат' }))).toBe('eurostat');
    expect(searchSourceOf(world({ code: 'x', source: 'IMF' }))).toBe('imf');
    expect(searchSourceOf(world({ code: 'x', source: 'Росстат' }))).toBe('ru');
  });
});

describe('searchBasisOf', () => {
  it('отличает «в среднем за год» от «год к году»', () => {
    expect(searchBasisOf(world({ code: 'tr-weo-pcpipch', name: 'Инфляция в среднем за год, оценка МВФ' }))).toBe('avg');
    expect(searchBasisOf(world({ code: 'tr-tec00118-total-rch-a-avg', name: 'Темп инфляции, изменение за год' }))).toBe('avg');
    expect(searchBasisOf(world({ code: 'a', name: 'Инфляция, изменение за год' }))).toBe('yoy');
    expect(searchBasisOf(world({ code: 'a', name: 'CPI', path: '/x?mode=yoy-annual' }))).toBe('yoy');
    expect(searchBasisOf(world({ code: 'a', name: 'Безработица' }))).toBe('');
  });
});

describe('searchCountryOf', () => {
  it('собирает Россию и её регионы в одну страну', () => {
    expect(searchCountryOf({ kind: 'russia' }, 'Россия').slug).toBe('russia');
    expect(searchCountryOf({ kind: 'subnational_region', country_slug: '' }, 'Россия').slug).toBe('russia');
    expect(searchCountryOf(world({}), 'Россия')).toEqual({ slug: 'turkey', name: 'Турция' });
    expect(searchCountryOf({ kind: 'country' }, 'Россия').slug).toBe('');
  });
});

const RESULTS = [
  world({ key: '1', code: 'tr-weo-pcpipch', name: 'Инфляция в среднем за год', frequency: 'annual' }),
  world({ key: '2', code: 'tr-prc_hicp_manr', name: 'Инфляция, изменение за год' }),
  world({ key: '3', code: 'de-prc_hicp_manr', name: 'Инфляция, изменение за год', country_slug: 'germany', country_name: 'Германия' }),
  { kind: 'rating', key: 'r', code: 'rating' },
];

describe('buildFilterOptions и applySearchFilters', () => {
  it('предлагает только группы, где есть из чего выбрать, рейтинги не считает', () => {
    const options = buildFilterOptions(RESULTS);
    expect(options.country.map((entry) => entry.value)).toEqual(['turkey', 'germany']);
    expect(options.frequency.map((entry) => entry.value)).toEqual(['monthly', 'annual']);
    expect(options.source.map((entry) => entry.value)).toEqual(['imf', 'eurostat']);
    expect(options.basis.map((entry) => entry.value)).toEqual(['avg', 'yoy']);
    expect(buildFilterOptions([RESULTS[0]]).country).toEqual([]);
    expect(buildFilterOptions([RESULTS[0]]).basis).toEqual([]);
  });
  it('выбранное значение остаётся в списке, даже если в выдаче его уже нет', () => {
    expect(buildFilterOptions([RESULTS[0]], { ...EMPTY_FILTERS, country: 'germany' }).country.map((entry) => entry.value)).toContain('germany');
  });
  it('отбирает по каждой группе и по их сочетанию; рейтинги остаются', () => {
    expect(applySearchFilters(RESULTS, EMPTY_FILTERS)).toBe(RESULTS);
    expect(applySearchFilters(RESULTS, { ...EMPTY_FILTERS, country: 'germany' }).map((item) => item.key)).toEqual(['3', 'r']);
    expect(applySearchFilters(RESULTS, { ...EMPTY_FILTERS, basis: 'avg' }).map((item) => item.key)).toEqual(['1', 'r']);
    expect(applySearchFilters(RESULTS, { ...EMPTY_FILTERS, source: 'eurostat', country: 'turkey' }).map((item) => item.key)).toEqual(['2', 'r']);
    expect(applySearchFilters(RESULTS, { ...EMPTY_FILTERS, frequency: 'annual', country: 'germany' }).map((item) => item.key)).toEqual(['r']);
    expect(activeFilterCount({ ...EMPTY_FILTERS, country: 'x', basis: 'avg' })).toBe(2);
  });
});
