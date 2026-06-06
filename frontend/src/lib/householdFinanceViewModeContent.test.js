import { describe, it, expect } from 'vitest';
import {
  getHouseholdFinanceViewModeContent,
  isHouseholdFinanceFamily,
} from './householdFinanceViewModeContent';
import { getViewModeContent } from './cpiViewModeContent';
import { isVariantSiblingNavigation } from './indicatorVariants';

describe('householdFinanceViewModeContent', () => {
  it('isHouseholdFinanceFamily only for household finance codes', () => {
    expect(isHouseholdFinanceFamily('consumer-credit')).toBe(true);
    expect(isHouseholdFinanceFamily('deposits-individual')).toBe(true);
    expect(isHouseholdFinanceFamily('business-credit')).toBe(false);
  });

  it('level content mentions units without jargon', () => {
    const credit = getHouseholdFinanceViewModeContent({
      chartMode: 'level',
      indicatorCode: 'consumer-credit',
    });
    expect(credit.methodology).toMatch(/трлн|задолженност/i);
    expect(credit.methodology).not.toMatch(/publicationId|dataservice/i);

    const deposits = getHouseholdFinanceViewModeContent({
      chartMode: 'level',
      indicatorCode: 'deposits-individual',
    });
    expect(deposits.methodology).toMatch(/млрд|вклад/i);
  });

  it('getViewModeContent routes household finance family', () => {
    const { methodology } = getViewModeContent({
      chartMode: 'quarterly',
      safeViewMode: 'quarterly',
      isHouseholdFinanceFamily: true,
      indicator: { code: 'deposits-individual' },
    });
    expect(methodology).toMatch(/квартал/i);
    expect(methodology).toMatch(/отток|приток|отпуск|декабр/i);
  });

  it('agg methodology differs by slice', () => {
    const credit = getHouseholdFinanceViewModeContent({
      chartMode: 'annual',
      indicatorCode: 'consumer-credit',
    }).methodology;
    const deposits = getHouseholdFinanceViewModeContent({
      chartMode: 'annual',
      indicatorCode: 'deposits-individual',
    }).methodology;
    expect(credit).not.toBe(deposits);
  });

  it('quarterly and annual methodology differ', () => {
    const q = getHouseholdFinanceViewModeContent({
      chartMode: 'quarterly',
      indicatorCode: 'consumer-credit',
    }).methodology;
    const y = getHouseholdFinanceViewModeContent({
      chartMode: 'annual',
      indicatorCode: 'consumer-credit',
    }).methodology;
    expect(q).not.toBe(y);
  });
});

describe('variant siblings household finance', () => {
  it('consumer ↔ deposits preserve variant', () => {
    expect(isVariantSiblingNavigation(
      '/indicator/consumer-credit',
      '/indicator/deposits-individual',
    )).toBe(true);
  });
});
