import { describe, expect, it } from 'vitest';
import { leadersAndTrailers, leadersDirection, rankRegions } from './regionLeaders';

const names = { a: 'А', b: 'Б', c: 'В', d: 'Г', e: 'Д', f: 'Е', g: 'Ж', h: 'З' };
const values = new Map([['a', 5], ['b', 1], ['c', 9], ['d', null], ['e', 'x'], ['f', 3], ['g', 7], ['h', 2]]);

describe('rankRegions', () => {
  it('пропускает регионы без числа и сортирует по направлению', () => {
    expect(rankRegions(values, names).map((r) => r.slug)).toEqual(['c', 'g', 'a', 'f', 'h', 'b']);
    expect(rankRegions(values, names, { direction: 'asc' }).map((r) => r.slug)).toEqual(['b', 'h', 'f', 'a', 'g', 'c']);
    expect(rankRegions(null, names)).toEqual([]);
  });

  it('читает и обычный объект', () => {
    expect(rankRegions({ a: 2, b: 4 }, names).map((r) => r.slug)).toEqual(['b', 'a']);
  });
});

describe('leadersAndTrailers', () => {
  const ranked = rankRegions(values, names);
  it('первые и последние с настоящими местами, последний первым', () => {
    const { top, bottom, total } = leadersAndTrailers(ranked, 2);
    expect(total).toBe(6);
    expect(top.map((r) => [r.slug, r.place])).toEqual([['c', 1], ['g', 2]]);
    expect(bottom.map((r) => [r.slug, r.place])).toEqual([['b', 6], ['h', 5]]);
  });

  it('при малом числе регионов списки не пересекаются', () => {
    const { top, bottom } = leadersAndTrailers(ranked, 10);
    expect(top).toHaveLength(3);
    expect(bottom).toHaveLength(3);
    expect(new Set([...top, ...bottom].map((r) => r.slug)).size).toBe(6);
  });
});

describe('leadersDirection', () => {
  it('«меньше — лучше» даёт возрастание, остальное убывание', () => {
    expect(leadersDirection({ rank_as_achievement: true, default_sort: 'asc' })).toBe('asc');
    expect(leadersDirection({ rank_as_achievement: false, default_sort: 'asc' })).toBe('desc');
    expect(leadersDirection(null)).toBe('desc');
  });
});
