import { describe, it, expect } from 'vitest';
import { splitShortName, formatPrice, collectPriceItems, commonPeriod, FAMILY_TABS, familyPicks } from './RegionPrices';

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
  it('picks the most common month for the block caption', () => {
    expect(commonPeriod([{ period_label: 'сентябрь 2026' }, { period_label: 'август 2026' }, { period_label: 'сентябрь 2026' }])).toBe('сентябрь 2026');
    expect(commonPeriod([])).toBe('');
  });
  it('R5-B: family tabs keep curated order, skip discontinued and missing items', () => {
    const all = [
      { code: 'ceni-ibuprofen' },
      { code: 'ceni-paracetamol', is_discontinued: true },
      { code: 'ceni-yod' },
    ];
    const pharm = FAMILY_TABS.find((tb) => tb.key === 'pharm');
    expect(familyPicks(pharm, all, []).map((i) => i.code)).toEqual(['ceni-ibuprofen', 'ceni-yod']);
    const main = FAMILY_TABS.find((tb) => tb.key === 'main');
    expect(familyPicks(main, all, ['ceni-yod', 'nope']).map((i) => i.code)).toEqual(['ceni-yod']);
  });
});
