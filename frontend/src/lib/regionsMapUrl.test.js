import { describe, it, expect } from 'vitest';
import {
  parseRegionsMapParams,
  parseRegionsMapLocation,
  buildRegionsMapLocation,
  buildRegionsMapHref,
  buildRegionsMapSearchParams,
  searchParamsEqual,
  locationsEqual,
  MAP_OVERVIEW,
  DEFAULT_MAP_CODE,
  resolveRegionsMapPaint,
} from './regionsMapUrl';

describe('regionsMapUrl', () => {
  it('парсит legacy query view=map, indicator и year', () => {
    const p = new URLSearchParams('view=map&indicator=uroven-bezrabotitsy&year=2015');
    expect(parseRegionsMapParams(p)).toEqual({
      view: 'map',
      indicator: 'uroven-bezrabotitsy',
      year: 2015,
    });
  });

  it('отбрасывает битый indicator и year', () => {
    const p = new URLSearchParams('view=map&indicator=../x&year=15');
    expect(parseRegionsMapParams(p)).toEqual({
      view: 'map',
      indicator: null,
      year: null,
    });
  });

  it('парсит канон /russia/region/map/{code}?year=', () => {
    expect(parseRegionsMapLocation(
      '/russia/region/map/uroven-bezrabotitsy',
      new URLSearchParams('year=2015'),
    )).toEqual({
      view: 'map',
      indicator: 'uroven-bezrabotitsy',
      year: 2015,
    });
  });

  it('собирает канон для кастомного показателя', () => {
    expect(buildRegionsMapLocation({
      view: 'map',
      indicator: 'chislennost-naseleniya',
      year: 2020,
    })).toEqual({
      pathname: '/russia/region/map/chislennost-naseleniya',
      search: '?year=2020',
    });
    expect(buildRegionsMapHref({
      view: 'map',
      indicator: 'chislennost-naseleniya',
      year: 2020,
    })).toBe('/russia/region/map/chislennost-naseleniya?year=2020');
  });

  it('для overview не пишет year; дефолт без indicator → DEFAULT_MAP_CODE', () => {
    expect(buildRegionsMapLocation({
      view: 'map',
      indicator: MAP_OVERVIEW,
      year: 2020,
    })).toEqual({ pathname: '/russia/region/map/overview', search: '' });
    expect(buildRegionsMapLocation({ view: 'map', year: 2018 })).toEqual({
      pathname: `/russia/region/map/${DEFAULT_MAP_CODE}`,
      search: '?year=2018',
    });
  });

  it('list — /regions без query', () => {
    expect(buildRegionsMapLocation({ view: 'list' })).toEqual({
      pathname: '/russia/region',
      search: '',
    });
  });

  it('legacy searchParams builder сохраняет старый контракт', () => {
    const p = buildRegionsMapSearchParams({
      view: 'map',
      indicator: 'chislennost-naseleniya',
      year: 2020,
    });
    expect(p.toString()).toBe('view=map&indicator=chislennost-naseleniya&year=2020');
  });

  it('searchParamsEqual и locationsEqual', () => {
    const a = new URLSearchParams('view=map&year=2020');
    const b = buildRegionsMapSearchParams({ view: 'map', year: 2020 });
    expect(searchParamsEqual(a, b)).toBe(true);
    expect(locationsEqual(
      { pathname: '/russia/region/map/x', search: '?year=1' },
      { pathname: '/russia/region/map/x', search: '?year=1' },
    )).toBe(true);
  });

  it('первый кадр карты красится из heatmap, не дожидаясь всех лет', () => {
    const heatmap = {
      year: 2024,
      indicator: { code: 'wages', name: 'Зарплата', unit: 'рублей' },
      values: [
        { slug: 'moskva', value: 100 },
        { slug: 'tatarstan', value: 80 },
      ],
    };
    const first = resolveRegionsMapPaint({ heatmap, series: null, urlYear: null });
    expect(first.year).toBe(2024);
    expect(first.years).toEqual([2024]);
    expect(first.valuesBySlug.get('moskva')).toBe(100);
    expect(first.indicator.name).toBe('Зарплата');
    expect(first.hasHistory).toBe(false);

    const series = {
      years: [2020, 2024],
      last_year: 2024,
      indicator: { code: 'wages', name: 'Зарплата', unit: 'рублей' },
      values_by_year: {
        2020: { moskva: 70 },
        2024: { moskva: 110, tatarstan: 85 },
      },
    };
    const later = resolveRegionsMapPaint({ heatmap, series, urlYear: 2020 });
    expect(later.year).toBe(2020);
    expect(later.years).toEqual([2020, 2024]);
    expect(later.valuesBySlug.get('moskva')).toBe(70);
    expect(later.hasHistory).toBe(true);
  });
});
