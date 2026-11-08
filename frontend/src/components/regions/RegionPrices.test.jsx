import { describe, it, expect } from 'vitest';
import { splitShortName, formatPrice, collectPriceItems } from './RegionPrices';

describe('RegionPrices helpers', () => {
  it('splits short name into title and unit', () => {
    expect(splitShortName('Яйца куриные, 10 шт.')).toEqual({ title: 'Яйца куриные', per: '10 шт.' });
    expect(splitShortName('Женская стрижка')).toEqual({ title: 'Женская стрижка', per: '' });
  });
  it('formats prices by magnitude', () => {
    expect(formatPrice(98.4, 'ru').replace(/\s/g, '')).toBe('98,4');
    expect(formatPrice(22345, 'ru').replace(/\s/g, '')).toBe('22345');
  });
  it('collects only priced items', () => {
    const got = collectPriceItems([{ indicators: [{ code: 'a' }, { code: 'b', price_group: 'Продукты' }] }]);
    expect(got.map((i) => i.code)).toEqual(['b']);
  });
});
