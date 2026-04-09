import { describe, it, expect } from 'vitest';
import { CATEGORIES, getCategoryBySlug, countInCategory, HIDDEN_FROM_LISTING } from './categories';

describe('categories', () => {
  it('has 9 categories', () => {
    expect(CATEGORIES).toHaveLength(9);
  });

  it('getCategoryBySlug finds prices', () => {
    expect(getCategoryBySlug('prices')?.slug).toBe('prices');
  });

  it('countInCategory filters by API category', () => {
    const ind = [{ category: 'Цены' }, { category: 'Цены' }, { category: 'Другое' }];
    expect(countInCategory(ind, 'Цены')).toBe(2);
    expect(countInCategory(null, 'Цены')).toBe(0);
  });

  it('HIDDEN_FROM_LISTING is exported and contains expected codes', () => {
    expect(HIDDEN_FROM_LISTING).toBeInstanceOf(Set);
    expect(HIDDEN_FROM_LISTING.has('inflation-annual')).toBe(true);
    expect(HIDDEN_FROM_LISTING.has('inflation-weekly')).toBe(true);
  });

  it('countInCategory excludes hidden indicators', () => {
    const ind = [
      { category: 'Цены', code: 'cpi' },
      { category: 'Цены', code: 'inflation-weekly' },
    ];
    expect(countInCategory(ind, 'Цены')).toBe(1);
  });
});
