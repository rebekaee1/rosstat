import { describe, it, expect } from 'vitest';
import {
  getCbrTermSliceChartTitle,
  getCbrTermSliceViewModeContent,
  isCbrTermSliceFamily,
} from './cbrTermSliceRateContent';
import { getViewModeContent } from './cpiViewModeContent';

describe('cbrTermSliceRateContent', () => {
  it('covers corp, ind, deposit codes', () => {
    expect(isCbrTermSliceFamily('credit-rate-ind-short')).toBe(true);
    expect(isCbrTermSliceFamily('deposit-rate-long')).toBe(true);
    expect(isCbrTermSliceFamily('auto-loan-rate')).toBe(false);
  });

  it('chart title differs by family', () => {
    expect(getCbrTermSliceChartTitle('level', 'deposit-rate')).toMatch(/вкладам/);
    expect(getCbrTermSliceChartTitle('level', 'credit-rate-ind-short')).toMatch(/физических лиц/);
  });

  it('getViewModeContent routes deposit slice', () => {
    const { methodology } = getViewModeContent({
      chartMode: 'level',
      safeViewMode: 'level',
      isPriceCategory: false,
      isHousingFamily: false,
      isPpiFamily: false,
      isAutoLoanFamily: false,
      isCbrTermSliceFamily: true,
      indicator: { code: 'deposit-rate-medium' },
    });
    expect(methodology).toMatch(/среднесрочный/i);
  });

  it('deposit content mentions привлечение', () => {
    const { description } = getCbrTermSliceViewModeContent({
      chartMode: 'level',
      indicator: { code: 'deposit-rate' },
    });
    expect(description).toMatch(/вклад/i);
  });
});
