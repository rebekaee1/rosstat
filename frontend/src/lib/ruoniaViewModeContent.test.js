import { describe, it, expect } from 'vitest';
import {
  getRuoniaViewModeContent,
  isRuoniaFamily,
} from './ruoniaViewModeContent';
import { getViewModeContent } from './cpiViewModeContent';

describe('ruoniaViewModeContent', () => {
  it('isRuoniaFamily only for ruonia', () => {
    expect(isRuoniaFamily('ruonia')).toBe(true);
    expect(isRuoniaFamily('key-rate')).toBe(false);
  });

  it('level mode describes daily market rate', () => {
    const { description, methodology } = getRuoniaViewModeContent({ chartMode: 'level' });
    expect(description).toMatch(/межбанк|овернайт|ежедневн/i);
    expect(methodology).not.toMatch(/ключев|ИПЦ/i);
  });

  it('monthly agg mode describes averaging', () => {
    const { methodology } = getRuoniaViewModeContent({ chartMode: 'monthly' });
    expect(methodology).toMatch(/средн|месяц/i);
  });

  it('getViewModeContent routes ruonia away from CPI', () => {
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
      isRuoniaFamily: true,
      indicator: { code: 'ruonia', description: 'fallback' },
    });
    expect(content.methodology).toMatch(/овернайт|официальный ряд/i);
    expect(content.description).not.toBe('fallback');
  });
});
