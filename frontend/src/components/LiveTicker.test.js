import { describe, expect, it } from 'vitest';
import { isForeignWorldPath, tickerLaneFor, tickerLaneForLocale } from '../lib/tickerLane';

describe('tickerLaneForLocale', () => {
  it('русская локаль — российская лента независимо от страницы', () => {
    expect(tickerLaneForLocale('ru')).toBe('russia');
  });

  it('английская локаль — мировые тикеры вершины', () => {
    expect(tickerLaneForLocale('en')).toBe('world');
  });

  it('path не участвует: только en даёт world, остальное — russia', () => {
    expect(tickerLaneForLocale(undefined)).toBe('russia');
    expect(tickerLaneForLocale(null)).toBe('russia');
    expect(tickerLaneForLocale('')).toBe('russia');
    expect(tickerLaneForLocale('de')).toBe('russia');
  });
});

describe('tickerLaneFor: язык и регион страницы', () => {
  it('en всегда world', () => {
    expect(tickerLaneFor('en', '/russia')).toBe('world');
    expect(tickerLaneFor('en', '/')).toBe('world');
  });

  it('ru: рубли на главной, в России, в «Валютах» и на служебных страницах', () => {
    for (const path of ['/', '/russia', '/russia/indicator/cpi', '/currencies', '/compare', '/about', '/calculator']) {
      expect(tickerLaneFor('ru', path)).toBe('russia');
    }
  });

  it('ru: на страницах других стран и в мировом рейтинге — мировой набор', () => {
    for (const path of ['/united-states', '/india/indicator/x', '/germany', '/world/rating/gdp-usd']) {
      expect(tickerLaneFor('ru', path)).toBe('world');
    }
    expect(isForeignWorldPath('/russia')).toBe(false);
    expect(isForeignWorldPath('')).toBe(false);
  });
});
