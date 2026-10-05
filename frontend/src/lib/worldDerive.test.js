import { describe, expect, it } from 'vitest';
import { deriveWorldMode } from './worldDerive';

const annual = [
  { date: '2020-01-01', value: 100 },
  { date: '2021-01-01', value: 110 },
  { date: '2022-01-01', value: 99 },
];

describe('deriveWorldMode', () => {
  it('год к году в процентах', () => {
    const r = deriveWorldMode(annual, 'yoy');
    expect(r.unit).toBe('percent');
    expect(r.points.map((p) => Math.round(p.value * 10) / 10)).toEqual([10, -10]);
  });

  it('к прошлому периоду', () => {
    const r = deriveWorldMode(annual, 'step');
    expect(r.points).toHaveLength(2);
    expect(r.points[0].value).toBeCloseTo(10, 6);
  });

  it('разница в единицах', () => {
    const r = deriveWorldMode(annual, 'yoyabs');
    expect(r.unit).toBe('same');
    expect(r.points.map((p) => p.value)).toEqual([10, -11]);
  });

  it('индекс от первого положительного значения', () => {
    const r = deriveWorldMode(annual, 'index');
    expect(r.unit).toBe('index');
    expect(r.points[0].value).toBe(100);
    expect(r.points[1].value).toBeCloseTo(110, 6);
  });

  it('помесячный ряд: база берётся ровно год назад', () => {
    const monthly = [];
    for (let m = 0; m < 14; m += 1) {
      const date = new Date(Date.UTC(2024, m, 1)).toISOString().slice(0, 10);
      monthly.push({ date, value: 100 + m });
    }
    const r = deriveWorldMode(monthly, 'yoy');
    expect(r.points).toHaveLength(2);
    expect(r.points[0].date).toBe('2025-01-01');
    expect(r.points[0].value).toBeCloseTo(12, 6);
  });

  it('без положительной базы режим посчитать нельзя', () => {
    expect(deriveWorldMode([{ date: '2020-01-01', value: 0 }, { date: '2021-01-01', value: 0 }], 'index')).toBeNull();
    expect(deriveWorldMode([{ date: '2020-01-01', value: 5 }], 'yoy')).toBeNull();
  });
});
