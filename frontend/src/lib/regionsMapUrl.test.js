import { describe, it, expect } from 'vitest';
import {
  parseRegionsMapParams,
  buildRegionsMapSearchParams,
  searchParamsEqual,
  MAP_OVERVIEW,
} from './regionsMapUrl';

describe('regionsMapUrl', () => {
  it('парсит view=map, indicator и year', () => {
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

  it('собирает shareable query для кастомного показателя', () => {
    const p = buildRegionsMapSearchParams({
      view: 'map',
      indicator: 'chislennost-naseleniya',
      year: 2020,
    });
    expect(p.toString()).toBe('view=map&indicator=chislennost-naseleniya&year=2020');
  });

  it('для overview не пишет year', () => {
    const p = buildRegionsMapSearchParams({
      view: 'map',
      indicator: MAP_OVERVIEW,
      year: 2020,
    });
    expect(p.toString()).toBe('view=map&indicator=overview');
  });

  it('для дефолтного пресета пишет year без indicator', () => {
    const p = buildRegionsMapSearchParams({ view: 'map', indicator: null, year: 2018 });
    expect(p.toString()).toBe('view=map&year=2018');
  });

  it('list — пустой query', () => {
    expect(buildRegionsMapSearchParams({ view: 'list' }).toString()).toBe('');
  });

  it('searchParamsEqual сравнивает сериализацию', () => {
    const a = new URLSearchParams('view=map&year=2020');
    const b = buildRegionsMapSearchParams({ view: 'map', year: 2020 });
    expect(searchParamsEqual(a, b)).toBe(true);
  });
});
