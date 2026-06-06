import { describe, it, expect } from 'vitest';
import {
  getCnyRubViewModeContent,
  isCnyRubFamily,
} from './cnyRubViewModeContent';
import { getViewModeContent } from './cpiViewModeContent';

describe('cnyRubViewModeContent', () => {
  it('isCnyRubFamily only for cny-rub', () => {
    expect(isCnyRubFamily('cny-rub')).toBe(true);
    expect(isCnyRubFamily('usd-rub')).toBe(false);
  });

  it('level mode describes official CNY/RUB rate', () => {
    const { description, methodology } = getCnyRubViewModeContent({ chartMode: 'level' });
    expect(description).toMatch(/юан|рубл/i);
    expect(methodology).toMatch(/курс|ежедневн/i);
    expect(methodology).not.toMatch(/R01375|XML_dynamic/i);
  });

  it('getViewModeContent routes cny-rub away from CPI', () => {
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
      isEurRubFamily: false,
      isCnyRubFamily: true,
      indicator: { code: 'cny-rub', description: 'fallback' },
    });
    expect(content.methodology).toMatch(/курс|Банк России/i);
    expect(content.description).not.toBe('fallback');
  });
});
