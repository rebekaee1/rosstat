import { describe, it, expect } from 'vitest';
import {
  getMortgageViewModeContent,
  isMortgageFamily,
} from './mortgageRateViewModeContent';
import { getViewModeContent } from './cpiViewModeContent';

describe('mortgageRateViewModeContent', () => {
  it('isMortgageFamily only for mortgage-rate', () => {
    expect(isMortgageFamily('mortgage-rate')).toBe(true);
    expect(isMortgageFamily('auto-loan-rate')).toBe(false);
  });

  it('content explains mortgage level mode', () => {
    const { description, methodology } = getMortgageViewModeContent({
      indicator: { code: 'mortgage-rate' },
    });
    expect(description).toMatch(/ипотечн|средневзвешенн/i);
    expect(methodology).toMatch(/единственный режим|уровень ставки/i);
    expect(methodology).not.toMatch(/автокредит|ИПЦ/i);
  });

  it('getViewModeContent routes mortgage away from CPI', () => {
    const content = getViewModeContent({
      chartMode: 'level',
      safeViewMode: 'level',
      isPriceCategory: false,
      isHousingFamily: false,
      isPpiFamily: false,
      isAutoLoanFamily: false,
      isMortgageFamily: true,
      isCbrTermSliceFamily: false,
      isKeyRateFamily: false,
      indicator: { code: 'mortgage-rate', description: 'fallback' },
    });
    expect(content.methodology).toMatch(/ипотечн/i);
    expect(content.description).not.toBe('fallback');
  });
});
