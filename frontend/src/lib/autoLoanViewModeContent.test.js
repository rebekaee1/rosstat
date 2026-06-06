import { describe, it, expect } from 'vitest';
import {
  getAutoLoanViewModeContent,
  isAutoLoanFamily,
} from './autoLoanViewModeContent';
import { getViewModeContent } from './cpiViewModeContent';

describe('autoLoanViewModeContent', () => {
  it('isAutoLoanFamily only for auto-loan-rate', () => {
    expect(isAutoLoanFamily('auto-loan-rate')).toBe(true);
    expect(isAutoLoanFamily('mortgage-rate')).toBe(false);
  });

  it('content explains single chart mode', () => {
    const { description, methodology } = getAutoLoanViewModeContent({
      indicator: { code: 'auto-loan-rate' },
    });
    expect(description).toMatch(/уровень|средневзвешенн/i);
    expect(methodology).toMatch(/единственный режим|уровень ставки/i);
    expect(methodology).not.toMatch(/ипотек|ИПЦ|потребительск/i);
  });

  it('getViewModeContent routes auto-loan away from CPI', () => {
    const content = getViewModeContent({
      chartMode: 'level',
      safeViewMode: 'level',
      isPriceCategory: false,
      isHousingFamily: false,
      isPpiFamily: false,
      isAutoLoanFamily: true,
      indicator: { code: 'auto-loan-rate', description: 'fallback' },
    });
    expect(content.methodology).toMatch(/единственный режим/i);
    expect(content.description).not.toBe('fallback');
  });
});
