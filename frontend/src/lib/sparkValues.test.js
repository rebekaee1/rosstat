import { describe, expect, it } from 'vitest';
import { sparkValues } from './sparkValues';

const year = (y, value) => ({ date: `${y}-01-01`, value });

describe('sparkValues', () => {
  it('берёт последние десять лет', () => {
    const points = Array.from({ length: 30 }, (_, i) => year(1996 + i, i));
    const out = sparkValues(points);
    expect(out[out.length - 1]).toBe(29);
    expect(out.length).toBe(11);
  });

  it('короткий ряд берёт целиком, меньше трёх точек не рисует', () => {
    expect(sparkValues([year(2024, 1), year(2025, 2)])).toEqual([]);
    expect(sparkValues([year(2023, 1), year(2024, 2), year(2025, 3)])).toEqual([1, 2, 3]);
  });

  it('длинный ряд прореживает до 120 точек и сохраняет последнюю', () => {
    const points = Array.from({ length: 3000 }, (_, i) => ({
      date: new Date(Date.UTC(2020, 0, 1) + i * 86400000).toISOString().slice(0, 10),
      value: i,
    }));
    const out = sparkValues(points);
    expect(out.length).toBe(120);
    expect(out[out.length - 1]).toBe(2999);
  });

  it('пропускает пустые значения', () => {
    expect(sparkValues([year(2022, 1), { date: '2023-01-01', value: null }, year(2024, 2), year(2025, 3)])).toEqual([1, 2, 3]);
  });
});
