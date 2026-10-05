import { describe, expect, it } from 'vitest';
import { tickerLaneFor, tickerLaneForLocale } from '../lib/tickerLane';

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

describe('tickerLaneFor: состав ленты зависит только от языка', () => {
  it('en всегда world', () => {
    expect(tickerLaneFor('en', '/russia')).toBe('world');
    expect(tickerLaneFor('en', '/')).toBe('world');
  });

  it('ru: один и тот же российский набор на любой странице, включая страны мира и рейтинг', () => {
    const paths = ['/', '/russia', '/currencies', '/compare', '/united-states', '/india/indicator/x', '/germany', '/world/rating/gdp-usd'];
    for (const path of paths) {
      expect(tickerLaneFor('ru', path)).toBe('russia');
    }
  });
});
