import { describe, it, expect } from 'vitest';
import {
  VARIANT_GROUPS,
  indicatorDetailHeaderMobileLines,
  isVariantSiblingNavigation,
  relatedIndicatorCardCopy,
} from './indicatorVariants';
import { translate } from '../i18n/messages';

describe('isVariantSiblingNavigation', () => {
  it('cpi → cpi-food is sibling', () => {
    expect(isVariantSiblingNavigation('/russia/indicator/cpi', '/russia/indicator/cpi-food')).toBe(true);
  });

  it('cpi → exports is not sibling', () => {
    expect(isVariantSiblingNavigation('/russia/indicator/cpi', '/russia/indicator/exports')).toBe(false);
  });

  it('same code is not sibling', () => {
    expect(isVariantSiblingNavigation('/russia/indicator/cpi', '/russia/indicator/cpi')).toBe(false);
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
    const card = relatedIndicatorCardCopy('key-rate', 'Ключевая ставка ЦБ РФ', '%');
    expect(card.title).toBe('Ключевая ставка ЦБ РФ');
    expect(card.subtitle).toBe('%');
  });

  it('housing variant: market slice as title', () => {
    const card = relatedIndicatorCardCopy(
      'housing-price-primary',
      'Цены на первичное жильё',
      'индекс',
    );
    expect(card.title).toBe('Первичное жильё');
    expect(card.subtitle).toBe('Рынок жилья');
  });

  it('housing primary ↔ secondary are variant siblings', () => {
    expect(isVariantSiblingNavigation(
      '/russia/indicator/housing-price-primary',
      '/russia/indicator/housing-price-secondary',
    )).toBe(true);
  });

  it('EN locale: housing / IPI / wages group labels via labelKey', () => {
    expect(translate('variant.housing.group', undefined, 'en')).toBe('Housing market');
    expect(translate('variant.ipi.group', undefined, 'en')).toBe('Industrial production composition');
    expect(translate('variant.wages.nominal', undefined, 'en')).toBe('Nominal');
    expect(translate('variant.fuel.ai92', undefined, 'en')).toMatch(/AI-92|gasoline/i);
  });
});

describe('VARIANT_GROUPS i18n keys', () => {
  it('every group and member has labelKey', () => {
    for (const group of VARIANT_GROUPS) {
      expect(group.labelKey, group.label).toBeTruthy();
      for (const member of group.codes) {
        expect(member.labelKey, member.code).toBeTruthy();
      }
    }
  });
});
