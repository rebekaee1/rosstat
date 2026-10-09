import { describe, expect, it } from 'vitest';
import { dataFreshness, freshnessDateFormat, periodEnd } from './dataFreshness';

const NOW = Date.UTC(2026, 9, 9); // 9 октября 2026

describe('periodEnd', () => {
  it('месячная точка относится ко всему месяцу, квартальная ко всему кварталу, годовая ко всему году', () => {
    expect(new Date(periodEnd('2026-08-01', 'monthly')).toISOString().slice(0, 10)).toBe('2026-08-31');
    expect(new Date(periodEnd('2026-04-01', 'quarterly')).toISOString().slice(0, 10)).toBe('2026-06-30');
    expect(new Date(periodEnd('2025-01-01', 'annual')).toISOString().slice(0, 10)).toBe('2025-12-31');
    expect(new Date(periodEnd('2026-10-05', 'weekly')).toISOString().slice(0, 10)).toBe('2026-10-11');
    expect(periodEnd('', 'monthly')).toBeNull();
  });
});

describe('dataFreshness', () => {
  it('август при месячном ряде в октябре свежий, март прошлого года устарел', () => {
    expect(dataFreshness('2026-08-01', 'monthly', NOW).level).toBe('fresh');
    expect(dataFreshness('2026-06-01', 'monthly', NOW).level).toBe('aging');
    expect(dataFreshness('2026-05-01', 'monthly', NOW).level).toBe('stale');
    expect(dataFreshness('2025-03-01', 'monthly', NOW).level).toBe('stale');
  });

  it('у годового ряда опоздание на год нормально, на два года уже нет', () => {
    expect(dataFreshness('2025-01-01', 'annual', NOW).level).toBe('fresh');
    expect(dataFreshness('2024-01-01', 'annual', NOW).level).toBe('aging');
    expect(dataFreshness('2023-01-01', 'annual', NOW).level).toBe('stale');
  });

  it('дневной ряд: вчерашнее значение свежее, трёхнедельное устарело', () => {
    expect(dataFreshness('2026-10-08', 'daily', NOW).level).toBe('fresh');
    expect(dataFreshness('2026-09-18', 'daily', NOW).level).toBe('stale');
  });

  it('возраст не отрицательный, пустая дата даёт null, неизвестная частота читается как месячная', () => {
    expect(dataFreshness('2026-12-01', 'monthly', NOW).ageDays).toBe(0);
    expect(dataFreshness(null, 'monthly', NOW)).toBeNull();
    expect(dataFreshness('2026-08-01', 'unknown', NOW).level).toBe('fresh');
  });
});

describe('freshnessDateFormat', () => {
  it('месяц словом в родительном падеже, у годового ряда год', () => {
    expect(freshnessDateFormat('monthly')).toBe('fullGen');
    expect(freshnessDateFormat('annual')).toBe('annual');
    expect(freshnessDateFormat('quarterly')).toBe('quarterly');
    expect(freshnessDateFormat('daily')).toBe('day');
  });
});
