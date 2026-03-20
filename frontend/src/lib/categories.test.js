import { describe, it, expect } from 'vitest';
import { CATEGORIES, getCategoryBySlug, countInCategory } from './categories';

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
});
