import { describe, expect, it } from 'vitest';
import { formatAxisTickCompact, needsCompactAxis, spansManyYears, yearAxisTicks } from './chartAxis';

function monthly(startYear, startMonth, count) {
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(Date.UTC(startYear, startMonth - 1 + i, 1));
    return d.toISOString().slice(0, 10);
  });
}

describe('yearAxisTicks', () => {
  it('подписывает каждый год, пока помещается', () => {
    const dates = monthly(2021, 1, 60);
    expect(yearAxisTicks(dates, 600)).toEqual([
      '2021-01-01', '2022-01-01', '2023-01-01', '2024-01-01', '2025-01-01',
    ]);
  });

  it('на узком экране прореживает до чётных лет', () => {
    const dates = monthly(2010, 1, 15 * 12);
    const ticks = yearAxisTicks(dates, 200);
    expect(ticks.length).toBeLessThanOrEqual(3);
    expect(ticks.every((d) => Number(d.slice(0, 4)) % 5 === 0 || Number(d.slice(0, 4)) % 2 === 0)).toBe(true);
  });

  it('неполный первый год не подписывает', () => {
    const dates = monthly(2021, 5, 40);
    const ticks = yearAxisTicks(dates, 600);
    expect(ticks[0]).toBe('2022-01-01');
  });

  it('для окна меньше двух лет годовую ось не строит', () => {
    expect(yearAxisTicks(monthly(2025, 3, 8), 600)).toBeNull();
  });
});

describe('spansManyYears', () => {
  it('короткое окно не считается длинным', () => {
    expect(spansManyYears(monthly(2025, 1, 12))).toBe(false);
    expect(spansManyYears(monthly(2020, 1, 60))).toBe(true);
  });
});

describe('formatAxisTickCompact', () => {
  it('миллионы и миллиарды сокращает', () => {
    expect(formatAxisTickCompact(24000000, 0, 'ru')).toBe('24 млн');
    expect(formatAxisTickCompact(28500000, 0, 'ru')).toBe('28,5 млн');
    expect(formatAxisTickCompact(3e9, 0, 'ru')).toBe('3 млрд');
    expect(formatAxisTickCompact(24000000, 0, 'en')).toBe('24M');
  });
  it('малые числа оставляет как есть', () => {
    expect(formatAxisTickCompact(1500, 0, 'ru')).toMatch(/^1\s?500$/);
    expect(formatAxisTickCompact(2.5, 1, 'ru')).toBe('2,5');
  });
  it('needsCompactAxis срабатывает от миллиона', () => {
    expect(needsCompactAxis(999999)).toBe(false);
    expect(needsCompactAxis(1e6)).toBe(true);
  });
});
