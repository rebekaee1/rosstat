import { describe, it, expect } from 'vitest';
import {
  getUsdRubViewModeContent,
  isUsdRubFamily,
} from './usdRubViewModeContent';
import { getViewModeContent } from './cpiViewModeContent';

describe('usdRubViewModeContent', () => {
  it('isUsdRubFamily only for usd-rub', () => {
    expect(isUsdRubFamily('usd-rub')).toBe(true);
    expect(isUsdRubFamily('eur-rub')).toBe(false);
  });

  it('level mode describes official USD/RUB rate', () => {
    const { description, methodology } = getUsdRubViewModeContent({ chartMode: 'level' });
    expect(description).toMatch(/доллар|рубл/i);
    expect(methodology).toMatch(/курс|ежедневн/i);
    expect(methodology).not.toMatch(/R01235|XML_dynamic/i);
  });

  it('getViewModeContent routes usd-rub away from CPI', () => {
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
      isUsdRubFamily: true,
      isEurRubFamily: false,
      isCnyRubFamily: false,
      indicator: { code: 'usd-rub', description: 'fallback' },
    });
    expect(content.methodology).toMatch(/курс|Банк России/i);
    expect(content.description).not.toBe('fallback');
  });
});
