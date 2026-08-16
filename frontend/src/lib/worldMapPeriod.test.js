import { describe, expect, it } from 'vitest';
import {
  formatWorldPeriod, resolveWorldPeriodFormat, worldPeriodDates,
} from './worldMapPeriod';

describe('resolveWorldPeriodFormat', () => {
  it('reads a January-only slice as annual', () => {
    expect(resolveWorldPeriodFormat(['2025-01-01', '2025-01-01', '2024-01-01'])).toBe('annual');
  });

  it('keeps a monthly slice on months', () => {
    expect(resolveWorldPeriodFormat(['2026-06-01', '2026-05-01', '2026-06-01'])).toBe('full');
  });

  it('survives a single foreign-cadence point in an annual slice', () => {
    const dates = ['2025-01-01', '2025-01-01', '2025-01-01', '2025-01-01', '2025-11-01'];
    expect(resolveWorldPeriodFormat(dates)).toBe('annual');
  });

  it('falls back to months when there is nothing to read', () => {
    expect(resolveWorldPeriodFormat([])).toBe('full');
    expect(resolveWorldPeriodFormat(['неизвестно'])).toBe('full');
  });
});

describe('formatWorldPeriod', () => {
  it('renders a monthly point in Russian', () => {
    expect(formatWorldPeriod('2026-06-01', 'full')).toBe('июнь 2026');
  });

  it('renders an annual point as a year', () => {
    expect(formatWorldPeriod('2025-01-01', 'annual')).toBe('2025');
  });

  it('keeps the month of a point that breaks the annual slice', () => {
    expect(formatWorldPeriod('2025-11-01', 'annual')).toBe('ноябрь 2025');
  });

  it('renders a weekly or daily point with the day', () => {
    expect(formatWorldPeriod('2026-06-12', 'full')).toBe('12 июня 2026');
  });

  it('returns nothing for a missing or broken date', () => {
    expect(formatWorldPeriod(null, 'full')).toBe('');
    expect(formatWorldPeriod('—', 'full')).toBe('');
  });
});

describe('worldPeriodDates', () => {
  it('reads dates from a Map and from a plain object', () => {
    const map = new Map([['DE', { date: '2026-06-01' }], ['FR', { value: 1 }]]);
    expect(worldPeriodDates(map)).toEqual(['2026-06-01']);
    expect(worldPeriodDates({ DE: { date: '2025-01-01' } })).toEqual(['2025-01-01']);
    expect(worldPeriodDates(null)).toEqual([]);
  });
});
