import { describe, it, expect } from 'vitest';
import {
  getGoldPriceViewModeContent,
  isGoldPriceFamily,
} from './goldPriceViewModeContent';
import { getViewModeContent } from './cpiViewModeContent';

describe('goldPriceViewModeContent', () => {
  it('isGoldPriceFamily only for gold-price', () => {
    expect(isGoldPriceFamily('gold-price')).toBe(true);
    expect(isGoldPriceFamily('brent')).toBe(false);
  });

  it('level content mentions rub per gram without jargon', () => {
    const { methodology } = getGoldPriceViewModeContent({ chartMode: 'level' });
    expect(methodology).toMatch(/руб|грамм|золот/i);
    expect(methodology).not.toMatch(/cbr_gold|metall_base|bulk_upsert/i);
  });

  it('getViewModeContent routes gold price family', () => {
    const { methodology } = getViewModeContent({
      chartMode: 'monthly',
      safeViewMode: 'monthly',
      isGoldPriceFamily: true,
      indicator: { code: 'gold-price' },
    });
    expect(methodology).toMatch(/месяц/i);
    expect(methodology).toMatch(/средн/i);
  });

  it('level and monthly methodology differ', () => {
    const level = getGoldPriceViewModeContent({ chartMode: 'level' }).methodology;
    const monthly = getGoldPriceViewModeContent({ chartMode: 'monthly' }).methodology;
    expect(level).not.toBe(monthly);
  });
});
