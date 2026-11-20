import { describe, it, expect } from 'vitest';
import { isAdditiveUnit, shareOfRussia } from './regionShare';

describe('regionShare', () => {
  it('складываемые единицы: тысячи человек, миллионы рублей', () => {
    expect(isAdditiveUnit('тыс. человек')).toBe(true);
    expect(isAdditiveUnit('миллионов рублей')).toBe(true);
    expect(isAdditiveUnit('thousand people')).toBe(true);
  });
  it('несскладываемые: проценты, годы, на 1000, цены, средние', () => {
    for (const u of ['%', 'процентов', 'лет', 'на 1000 человек', 'рублей за кг', 'рублей', 'в среднем за год', 'индекс']) {
      expect(isAdditiveUnit(u)).toBe(false);
    }
  });
  it('доля региона в России', () => {
    expect(shareOfRussia(1222, 10000)).toBeCloseTo(12.22, 2);
    expect(shareOfRussia(5, 0)).toBeNull();
    expect(shareOfRussia(20000, 10000)).toBeNull();
    expect(shareOfRussia(null, 10000)).toBeNull();
  });
});
