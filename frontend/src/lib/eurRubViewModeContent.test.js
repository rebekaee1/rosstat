import { describe, it, expect } from 'vitest';
import {
  getEurRubViewModeContent,
  isEurRubFamily,
} from './eurRubViewModeContent';
import { getViewModeContent } from './cpiViewModeContent';

describe('eurRubViewModeContent', () => {
  it('isEurRubFamily only for eur-rub', () => {
    expect(isEurRubFamily('eur-rub')).toBe(true);
    expect(isEurRubFamily('usd-rub')).toBe(false);
  });

  it('level mode describes official EUR/RUB rate', () => {
    const { description, methodology } = getEurRubViewModeContent({ chartMode: 'level' });
    expect(description).toMatch(/евро|рубл/i);
    expect(methodology).toMatch(/курс|ежедневн/i);
    expect(methodology).not.toMatch(/R01239|XML_dynamic/i);
  });

  it('getViewModeContent routes eur-rub away from CPI', () => {
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
      isUsdRubFamily: false,
      isEurRubFamily: true,
      isCnyRubFamily: false,
      indicator: { code: 'eur-rub', description: 'fallback' },
    });
    expect(content.methodology).toMatch(/курс|Банк России/i);
    expect(content.description).not.toBe('fallback');
  });
});
