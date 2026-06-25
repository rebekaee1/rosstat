import { describe, it, expect } from 'vitest';
import {
  CATEGORIES,
  getCategoryBySlug,
  countInCategory,
  isIndicatorListed,
} from './categories';

describe('categories', () => {
  it('has 12 categories (+«Индексы» MOEX, +«Товарные рынки» сырьё)', () => {
    expect(CATEGORIES).toHaveLength(12);
  });

  it('currencies category exists and points to apiCategory="Валюты"', () => {
    const cur = getCategoryBySlug('currencies');
    expect(cur?.apiCategory).toBe('Валюты');
    expect(cur?.status).toBe('active');
  });

  it('indices + commodities categories exist with right apiCategory', () => {
    expect(getCategoryBySlug('indices')?.apiCategory).toBe('Индексы');
    expect(getCategoryBySlug('commodities')?.apiCategory).toBe('Товарные рынки');
  });

  it('getCategoryBySlug finds prices', () => {
    expect(getCategoryBySlug('prices')?.slug).toBe('prices');
  });

  it('isIndicatorListed: API is_listed=false → hidden', () => {
    expect(isIndicatorListed({ code: 'cpi', is_listed: false })).toBe(false);
  });

  it('isIndicatorListed: API is_listed=true → visible', () => {
    expect(isIndicatorListed({ code: 'cpi', is_listed: true })).toBe(true);
  });

  it('isIndicatorListed: missing is_listed defaults to visible', () => {
    expect(isIndicatorListed({ code: 'cpi' })).toBe(true);
  });

  it('isIndicatorListed: null/undefined → hidden', () => {
    expect(isIndicatorListed(null)).toBe(false);
    expect(isIndicatorListed(undefined)).toBe(false);
  });

  it('countInCategory filters by API category and is_listed', () => {
    const ind = [
      { category: 'Цены', code: 'cpi', is_listed: true },
      { category: 'Цены', code: 'cpi-food-annual', is_listed: false },
      { category: 'Другое', code: 'x', is_listed: true },
    ];
    expect(countInCategory(ind, 'Цены')).toBe(1);
    expect(countInCategory(null, 'Цены')).toBe(0);
  });
});
