import { describe, expect, it } from 'vitest';
import { visibleRangeStats } from './rangeStats';

const full = Array.from({ length: 24 }, (_, i) => ({ date: `${2013 + Math.floor(i / 2)}-${i % 2 ? '07' : '01'}-01`, value: i + 1 }));
const rowsOf = (points) => points.map((p) => ({ date: p.date, actual: p.value }));

describe('visibleRangeStats', () => {
  it('пока на графике весь ряд, расчёт не вмешивается', () => {
    expect(visibleRangeStats(rowsOf(full), full)).toBeNull();
  });

  it('сужённое окно: максимум, среднее и длина окна в годах считаются по видимому', () => {
    const last = full.slice(-6);
    const stats = visibleRangeStats(rowsOf(last), full);
    expect(stats.highest.value).toBe(24);
    expect(stats.average).toBeCloseTo(21.5, 5);
    expect(stats.years).toBe(2);
    expect(stats.count).toBe(6);
  });

  it('строки прогноза без факта не считаются, малое окно и пустые данные дают null', () => {
    const rows = [...rowsOf(full.slice(-6)), { date: '2027-01-01', actual: null, forecast: 99 }];
    expect(visibleRangeStats(rows, full).highest.value).toBe(24);
    expect(visibleRangeStats(rowsOf(full.slice(-2)), full)).toBeNull();
    expect(visibleRangeStats(null, full)).toBeNull();
    expect(visibleRangeStats(rowsOf(full.slice(-6)), [])).toBeNull();
  });
});
