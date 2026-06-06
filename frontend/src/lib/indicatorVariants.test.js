import { describe, it, expect } from 'vitest';
import {
  indicatorDetailHeaderMobileLines,
  isVariantSiblingNavigation,
  relatedIndicatorCardCopy,
} from './indicatorVariants';

describe('isVariantSiblingNavigation', () => {
  it('cpi → cpi-food is sibling', () => {
    expect(isVariantSiblingNavigation('/indicator/cpi', '/indicator/cpi-food')).toBe(true);
  });

  it('cpi → exports is not sibling', () => {
    expect(isVariantSiblingNavigation('/indicator/cpi', '/indicator/exports')).toBe(false);
  });

  it('same code is not sibling', () => {
    expect(isVariantSiblingNavigation('/indicator/cpi', '/indicator/cpi')).toBe(false);
  });
});

describe('indicatorDetailHeaderMobileLines', () => {
  it('splits CPI titles at «на» without changing text', () => {
    const name = 'Индекс потребительских цен на товары и услуги';
    const lines = indicatorDetailHeaderMobileLines(name);
    expect(lines).toEqual([
      'Индекс потребительских цен',
      'на товары и услуги',
    ]);
    expect(lines.join(' ')).toBe(name);
  });

  it('returns null for unrelated long names', () => {
    expect(indicatorDetailHeaderMobileLines('Экспорт товаров')).toBeNull();
  });
});

describe('relatedIndicatorCardCopy', () => {
  it('uses short CPI variant labels', () => {
    const card = relatedIndicatorCardCopy(
      'cpi-food',
      'Индекс потребительских цен на продовольственные товары',
      '%',
    );
    expect(card.title).toBe('Продовольствие');
    expect(card.subtitle).toBe('Индекс потребительских цен');
  });

  it('falls back to full name outside variant groups', () => {
    const card = relatedIndicatorCardCopy('exports', 'Экспорт товаров', 'млн USD');
    expect(card.title).toBe('Экспорт товаров');
    expect(card.subtitle).toBe('млн USD');
  });

  it('housing variant: market slice as title', () => {
    const card = relatedIndicatorCardCopy(
      'housing-price-primary',
      'Цены на первичное жильё',
      'индекс',
    );
    expect(card.title).toBe('Первичное');
    expect(card.subtitle).toBe('Рынок жилья');
  });

  it('housing primary ↔ secondary are variant siblings', () => {
    expect(isVariantSiblingNavigation(
      '/indicator/housing-price-primary',
      '/indicator/housing-price-secondary',
    )).toBe(true);
  });

});
