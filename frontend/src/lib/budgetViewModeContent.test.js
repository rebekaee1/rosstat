import { describe, it, expect } from 'vitest';
import {
  getBudgetViewModeContent,
  isBudgetFamily,
} from './budgetViewModeContent';
import { getViewModeContent } from './cpiViewModeContent';

describe('budgetViewModeContent', () => {
  it('isBudgetFamily only for budget codes', () => {
    expect(isBudgetFamily('budget-revenue')).toBe(true);
    expect(isBudgetFamily('exports')).toBe(false);
  });

  it('level content mentions Minfin without parser jargon', () => {
    const { description, methodology } = getBudgetViewModeContent({
      chartMode: 'level',
      indicatorCode: 'budget-deficit',
    });
    expect(description).toMatch(/дефицит|профицит/i);
    expect(methodology).toMatch(/Минфин/i);
    expect(methodology).not.toMatch(/csv|parser|bulk_upsert/i);
  });

  it('getViewModeContent routes budget family', () => {
    const { methodology } = getViewModeContent({
      chartMode: 'quarterly',
      safeViewMode: 'quarterly',
      isBudgetFamily: true,
      indicator: { code: 'budget-revenue' },
    });
    expect(methodology).toMatch(/квартал/i);
    expect(methodology).toMatch(/поступлен/i);
  });

  it('agg methodology differs by slice', () => {
    const deficit = getBudgetViewModeContent({
      chartMode: 'annual',
      indicatorCode: 'budget-deficit',
    }).methodology;
    const expenditure = getBudgetViewModeContent({
      chartMode: 'annual',
      indicatorCode: 'budget-expenditure',
    }).methodology;
    expect(deficit).not.toBe(expenditure);
  });
});

describe('isVariantSiblingNavigation budget', () => {
  it('budget revenue ↔ deficit preserve variant', async () => {
    const { isVariantSiblingNavigation } = await import('./indicatorVariants');
    expect(isVariantSiblingNavigation(
      '/indicator/budget-revenue',
      '/indicator/budget-deficit',
    )).toBe(true);
  });
});
