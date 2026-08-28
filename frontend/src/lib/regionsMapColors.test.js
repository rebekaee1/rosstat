import { describe, it, expect } from 'vitest';
import {
  buildQuantiles, colorsBySlug, valueExtent, MAP_NO_DATA, MAP_SCALE,
} from './regionsMapColors';

describe('regionsMapColors', () => {
  it('buildQuantiles красит по рангу внутри среза', () => {
    const q = buildQuantiles([10, 20, 30, 40, 50]);
    expect(q(10)).toBe(MAP_SCALE[0]);
    expect(q(50)).toBe(MAP_SCALE[MAP_SCALE.length - 1]);
    expect(q(null)).toBe(MAP_NO_DATA);
  });

  it('colorsBySlug принимает Map и plain object', () => {
    const fromMap = colorsBySlug(new Map([['a', 1], ['b', 100]]));
    const fromObj = colorsBySlug({ a: 1, b: 100 });
    expect(fromMap.get('a')).toBe(fromObj.get('a'));
    expect(fromMap.get('b')).toBe(fromObj.get('b'));
    expect(fromMap.get('a')).not.toBe(fromMap.get('b'));
  });

  it('valueExtent отдаёт min/max среза', () => {
    expect(valueExtent({ a: 10, b: 40, c: 25 })).toEqual({ min: 10, max: 40 });
    expect(valueExtent(new Map([['a', 3], ['b', 1]]))).toEqual({ min: 1, max: 3 });
    expect(valueExtent({})).toBeNull();
    expect(valueExtent(null)).toBeNull();
  });

  it('buildQuantiles инвертирует шкалу при направлении asc', () => {
    const q = buildQuantiles([10, 20, 30, 40, 50], { direction: 'asc' });
    expect(q(10)).toBe(MAP_SCALE[MAP_SCALE.length - 1]);
    expect(q(50)).toBe(MAP_SCALE[0]);
  });

  it('colorsBySlug переворачивает раскраску при смене направления', () => {
    const values = { a: 10, b: 50 };
    const desc = colorsBySlug(values, { direction: 'desc' });
    const asc = colorsBySlug(values, { direction: 'asc' });
    // Лидер (максимум) при desc акцентный; при asc — бледный, и наоборот.
    expect(asc.get('a')).toBe(desc.get('b'));
    expect(asc.get('b')).toBe(desc.get('a'));
  });
});
