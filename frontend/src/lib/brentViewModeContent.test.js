import { describe, it, expect } from 'vitest';
import {
  getBrentViewModeContent,
  isBrentFamily,
} from './brentViewModeContent';
import { getViewModeContent } from './cpiViewModeContent';

describe('brentViewModeContent', () => {
  it('isBrentFamily only for brent', () => {
    expect(isBrentFamily('brent')).toBe(true);
    expect(isBrentFamily('btc-usd')).toBe(false);
  });

  it('level mode describes Brent price in USD per barrel', () => {
    const { description, methodology } = getBrentViewModeContent({ chartMode: 'level' });
    expect(description).toMatch(/Brent|нефт|баррел/i);
    expect(methodology).toMatch(/цена|ежедневн/i);
    expect(methodology).not.toMatch(/MOEX|FORTS|BZ=/i);
  });

  it('getViewModeContent routes brent away from CPI', () => {
    const content = getViewModeContent({
      chartMode: 'level',
      safeViewMode: 'level',
      isPriceCategory: false,
      isHousingFamily: false,
      isPpiFamily: false,
      isAutoLoanFamily: false,
      isMortgageFamily: false,
      isCbrTermSliceFamily: false,
      isKeyRateFamily: false,
      isRuoniaFamily: false,
      isBtcUsdFamily: false,
      isBrentFamily: true,
      isUsdRubFamily: false,
      isEurRubFamily: false,
      isCnyRubFamily: false,
      indicator: { code: 'brent', description: 'fallback' },
    });
    expect(content.methodology).toMatch(/цена|баррел/i);
    expect(content.description).not.toBe('fallback');
  });
});
