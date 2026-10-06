import { describe, expect, it } from 'vitest';
import { changeMessageKey, chartGeometry, digitsFor, percentSign } from './forecastShowcase';

const item = {
  kind: 'level',
  history: [
    { date: '2026-06-01', value: 100 },
    { date: '2026-07-01', value: 101 },
    { date: '2026-08-01', value: 102 },
  ],
  forecast: [
    { date: '2026-09-01', value: 103 },
    { date: '2027-08-01', value: 108 },
  ],
};

describe('chartGeometry', () => {
  it('держит все точки внутри рамки, прогноз стартует в последнем факте', () => {
    const g = chartGeometry(item, { width: 320, height: 132 });
    expect(g).not.toBeNull();
    const nums = `${g.histPath} ${g.forePath}`.match(/-?\d+(\.\d+)?/g).map(Number);
    expect(Math.min(...nums)).toBeGreaterThanOrEqual(0);
    expect(g.now.x).toBeLessThan(g.end.x);
    expect(g.forePath.startsWith(`M${g.now.x} ${g.now.y}`)).toBe(true);
    expect(g.end.y).toBeLessThan(g.now.y); // прогноз выше факта: меньший y
  });

  it('диапазона нет: даже если в данных есть границы, полосы нет и ось по ним не растягивается', () => {
    const plain = chartGeometry(item);
    const withBounds = chartGeometry({
      ...item,
      forecast: item.forecast.map((row) => ({ ...row, lower: row.value - 50, upper: row.value + 50 })),
    });
    expect(withBounds.bandPath).toBeUndefined();
    expect(withBounds).toEqual(plain);
    expect(Object.keys(withBounds)).not.toContain('bandPath');
  });

  it('плоский ряд не делит на ноль', () => {
    const flat = {
      history: [{ date: '2026-01-01', value: 5 }, { date: '2026-02-01', value: 5 }],
      forecast: [{ date: '2027-01-01', value: 5 }],
    };
    const g = chartGeometry(flat);
    expect(Number.isFinite(g.now.y)).toBe(true);
  });

  it('короткий ряд даёт null, а не пустой график', () => {
    expect(chartGeometry({ history: [{ date: '2026-01-01', value: 1 }], forecast: [] })).toBeNull();
    expect(chartGeometry({})).toBeNull();
  });
});

describe('подписи чисел', () => {
  it('знаки после запятой по величине и смыслу', () => {
    expect(digitsFor({ kind: 'percent' }, 3.21)).toBe(1);
    expect(digitsFor({ kind: 'level' }, 127.4)).toBe(1);
    expect(digitsFor({ kind: 'level' }, 12.5)).toBe(2);
    expect(digitsFor({ kind: 'level' }, 1234567)).toBe(0);
  });

  it('знак процента только у процентных единиц', () => {
    expect(percentSign('% рабочей силы')).toBe(' %');
    expect(percentSign('индекс 2015=100')).toBe('');
    expect(percentSign(undefined)).toBe('');
  });

  it('ключ фразы про изменение', () => {
    expect(changeMessageKey({ unit: 'points', direction: 'down' })).toBe('zb.change.points.down');
    expect(changeMessageKey({ unit: 'percent', direction: 'up' })).toBe('zb.change.percent.up');
    expect(changeMessageKey({ unit: 'percent', direction: 'flat' })).toBe('zb.change.flat');
    expect(changeMessageKey(null)).toBe('zb.change.flat');
  });
});
