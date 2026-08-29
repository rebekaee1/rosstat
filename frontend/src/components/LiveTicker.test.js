import { describe, expect, it } from 'vitest';
import { tickerLaneForLocale } from '../lib/tickerLane';

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
