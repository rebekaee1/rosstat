import { describe, expect, it } from 'vitest';
import { priceUnitLabel } from './r9cPriceUnit';

describe('priceUnitLabel', () => {
  it('сохраняет «за кг», «за шт», «за л»', () => {
    expect(priceUnitLabel('рублей за кг')).toBe('₽ за кг');
    expect(priceUnitLabel('рублей за штуку')).toBe('₽ за штуку');
    expect(priceUnitLabel('рублей за 1 л')).toBe('₽ за 1 л');
  });
  it('английская единица', () => {
    expect(priceUnitLabel('rubles per kg')).toBe('₽ per kg');
  });
  it('не ценовая единица — пусто', () => {
    expect(priceUnitLabel('процентов')).toBe('');
    expect(priceUnitLabel('рублей')).toBe('');
    expect(priceUnitLabel(null)).toBe('');
  });
});
