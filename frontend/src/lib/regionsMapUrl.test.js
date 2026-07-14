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

  it('парсит канон /regions/map/{code}?year=', () => {
    expect(parseRegionsMapLocation(
      '/regions/map/uroven-bezrabotitsy',
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
      pathname: '/regions/map/chislennost-naseleniya',
      search: '?year=2020',
    });
    expect(buildRegionsMapHref({
      view: 'map',
      indicator: 'chislennost-naseleniya',
      year: 2020,
    })).toBe('/regions/map/chislennost-naseleniya?year=2020');
  });

  it('для overview не пишет year; дефолт без indicator → DEFAULT_MAP_CODE', () => {
    expect(buildRegionsMapLocation({
      view: 'map',
      indicator: MAP_OVERVIEW,
      year: 2020,
    })).toEqual({ pathname: '/regions/map/overview', search: '' });
    expect(buildRegionsMapLocation({ view: 'map', year: 2018 })).toEqual({
      pathname: `/regions/map/${DEFAULT_MAP_CODE}`,
      search: '?year=2018',
    });
  });

  it('list — /regions без query', () => {
    expect(buildRegionsMapLocation({ view: 'list' })).toEqual({
      pathname: '/regions',
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
      { pathname: '/regions/map/x', search: '?year=1' },
      { pathname: '/regions/map/x', search: '?year=1' },
    )).toBe(true);
  });
});
