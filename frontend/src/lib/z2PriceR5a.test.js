import { describe, it, expect } from 'vitest';
import { bigRub, compareFill, pairKey, pairLabel, pairSiblings, pairsFirst, roundBig, sliceMonths, yearlyCost } from './z2Price';

describe('R5-A: помощники страницы цены', () => {
  it('пары отличаются только числом', () => {
    const sib = [
      { code: 'a', short_name: 'Аренда 2-комнатной квартиры, месяц', value: 28628 },
      { code: 'b', short_name: 'Отопление', value: 1 },
    ];
    expect(pairKey('Аренда 1-комнатной квартиры, месяц')).toBe(pairKey(sib[0].short_name));
    expect(pairSiblings(sib, 'Аренда 1-комнатной квартиры, месяц').map((s) => s.code)).toEqual(['a']);
    expect(pairsFirst([sib[1], sib[0]], 'Аренда 1-комнатной квартиры, месяц')[0].code).toBe('a');
    expect(pairLabel('Аренда 2-комнатной квартиры')).toContain('2');
  });
  it('год, окно, полоска, округление', () => {
    expect(yearlyCost(24856, 'рублей в месяц')).toBe(298272);
    expect(yearlyCost(100, 'рублей за Гкал')).toBeNull();
    expect(sliceMonths([1, 2, 3, 4], 2)).toEqual([3, 4]);
    expect(sliceMonths([1, 2], 0)).toEqual([1, 2]);
    expect(compareFill(-20)).toBeCloseTo(0.8);
    expect(compareFill(50)).toBe(1);
    expect(roundBig(5894.9)).toBe(5895);
    expect(roundBig(21.4)).toBe(21.4);
    expect(bigRub(298272)).toContain('298');
  });
});
