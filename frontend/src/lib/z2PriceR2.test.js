import { describe, it, expect } from 'vitest';
import { unitSuffix, isRubPerUnit, priceText, perUnitPrice } from './z2Price';

describe('R2-Z2: английские единицы цены', () => {
  it('unitSuffix и isRubPerUnit понимают roubles per …', () => {
    expect(unitSuffix('roubles per 10 eggs')).toBe('per 10 eggs');
    expect(isRubPerUnit('рублей за кг')).toBe(true);
    expect(isRubPerUnit('%')).toBe(false);
  });
  it('priceText даёт «число ₽», perUnitPrice считает за штуку по-английски', () => {
    expect(priceText(101.2, 'roubles per 10 eggs', 'en')).toContain('₽');
    expect(perUnitPrice('roubles per 10 eggs', 101.2).word).toBe('egg');
  });
});
