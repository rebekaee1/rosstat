/* eslint-disable no-irregular-whitespace -- проверяем именно неразрывный пробел */
import { describe, it, expect } from 'vitest';
import { groupPriceItems, formatRub } from './R4PriceCompare';

describe('R4PriceCompare helpers', () => {
  it('groups items keeping order of first appearance', () => {
    const got = groupPriceItems([
      { code: 'a', group: 'Продукты', group_label: 'Продукты' },
      { code: 'b', group: 'ЖКХ', group_label: 'ЖКХ' },
      { code: 'c', group: 'Продукты', group_label: 'Продукты' },
    ]);
    expect(got.map((g) => g.group)).toEqual(['Продукты', 'ЖКХ']);
    expect(got[0].items.map((i) => i.code)).toEqual(['a', 'c']);
  });
  it('formats rubles with a non-breaking space', () => {
    expect(formatRub(22345.4, 'ru')).toMatch(/22\s?345 ₽$/);
    expect(formatRub(null, 'ru')).toBe('0 ₽');
    expect(formatRub('x', 'ru')).toBe('—');
  });
});
