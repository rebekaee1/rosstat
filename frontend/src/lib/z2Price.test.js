import { describe, it, expect } from 'vitest';
import { shortPriceName, unitSuffix, perUnitPrice, guessPriceGroup, parseYm, compareRows, groupSiblings, yearTickPeriods, changeOverMonths, pickField } from './z2Price';

describe('z2Price', () => {
  it('parseYm', () => {
    expect(parseYm(202609)).toEqual({ year: 2026, month: 9 });
    expect(parseYm('2026-09')).toEqual({ year: 2026, month: 9 });
    expect(parseYm(null)).toBeNull();
  });
  it('compareRows: для Москвы без Москвы, без поля пусто', () => {
    const c = { russia: { value: 100, month: 202609 }, moskva: { value: 120, month: 202609 } };
    expect(compareRows(c, 'moskva', 110).map((r) => r.key)).toEqual(['russia']);
    expect(compareRows(c, 'altay', 110).map((r) => r.key)).toEqual(['russia', 'moskva']);
    expect(compareRows(c, 'altay', 110)[0].pct).toBeCloseTo(10);
    expect(compareRows(undefined, 'altay', 110)).toEqual([]);
  });
  it('groupSiblings: текущая группа первой, живые раньше снятых', () => {
    const g = groupSiblings([
      { code: 'a', price_group: 'ЖКХ', is_discontinued: true },
      { code: 'b', price_group: 'ЖКХ' },
      { code: 'c', price_group: 'Продукты' },
      { code: 'd', price_group: 'Топливо' },
    ], 'Топливо');
    expect(g.map((x) => x.group)).toEqual(['Топливо', 'Продукты', 'ЖКХ']);
    expect(g[2].items.map((s) => s.code)).toEqual(['b', 'a']);
    expect(groupSiblings([{ code: 'a' }], null)).toBeNull();
  });
  it('yearTickPeriods: не больше max и последний год включён', () => {
    const pts = [];
    for (let y = 2003; y <= 2026; y += 1) pts.push({ year: y, period: `${y}-01` });
    const t = yearTickPeriods(pts, 5);
    expect(t.length).toBeLessThanOrEqual(5);
    expect(t[t.length - 1]).toBe('2026-01');
  });
  it('запасные короткое имя, единица, цена за штуку, группа', () => {
    expect(shortPriceName('Средняя цена: яйца куриные, рублей за 10 штук', 'рублей за 10 штук')).toBe('Яйца куриные');
    expect(shortPriceName('Средняя цена: ацетилцистеин (АЦЦ), 600 мг, рублей за 10 таблеток', 'рублей за 10 таблеток')).toBe('Ацетилцистеин (АЦЦ), 600 мг');
    expect(unitSuffix('рублей за 10 штук')).toBe('за 10 штук');
    expect(unitSuffix('%')).toBe('');
    expect(perUnitPrice('рублей за 10 штук', 123).value).toBeCloseTo(12.3);
    expect(perUnitPrice('рублей за литр', 50)).toBeNull();
    expect(guessPriceGroup('бензин АИ-98', 'рублей за литр')).toBe('Топливо');
    expect(guessPriceGroup('яйца куриные', 'рублей за 10 штук')).toBe('Продукты');
    expect(guessPriceGroup('аципол', 'рублей за 30 капсул')).toBe('Лекарства');
  });
  it('changeOverMonths и pickField', () => {
    const s = [{ year: 2025, month: 9, value: 100 }, { year: 2026, month: 9, value: 110 }];
    expect(changeOverMonths(s, 12).pct).toBeCloseTo(10);
    expect(changeOverMonths(s, 60)).toBeNull();
    expect(pickField({ indicator: { a: 1 }, b: 2 }, 'b')).toBe(2);
  });
});
