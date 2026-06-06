import { describe, it, expect } from 'vitest';
import {
  getBtcUsdViewModeContent,
  isBtcUsdFamily,
} from './btcUsdViewModeContent';
import { getViewModeContent } from './cpiViewModeContent';

describe('btcUsdViewModeContent', () => {
  it('isBtcUsdFamily only for btc-usd', () => {
    expect(isBtcUsdFamily('btc-usd')).toBe(true);
    expect(isBtcUsdFamily('usd-rub')).toBe(false);
  });

  it('level mode describes daily price in USD', () => {
    const { description, methodology } = getBtcUsdViewModeContent({ chartMode: 'level' });
    expect(description).toMatch(/доллар|биткоин|день/i);
    expect(methodology).toMatch(/цена|ежедневн/i);
    expect(methodology).not.toMatch(/BTCUSDT|klines/i);
  });

  it('getViewModeContent routes btc-usd away from CPI', () => {
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
      isBtcUsdFamily: true,
      indicator: { code: 'btc-usd', description: 'fallback' },
    });
    expect(content.methodology).toMatch(/цена|закрыт/i);
    expect(content.description).not.toBe('fallback');
  });
});
