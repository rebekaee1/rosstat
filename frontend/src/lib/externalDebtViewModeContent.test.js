import { describe, it, expect } from 'vitest';
import {
  getExternalDebtViewModeContent,
  isExternalDebtFamily,
} from './externalDebtViewModeContent';
import { getViewModeContent } from './cpiViewModeContent';

describe('externalDebtViewModeContent', () => {
  it('isExternalDebtFamily only for external-debt', () => {
    expect(isExternalDebtFamily('external-debt')).toBe(true);
    expect(isExternalDebtFamily('business-credit')).toBe(false);
  });

  it('level content mentions debt without jargon', () => {
    const { methodology } = getExternalDebtViewModeContent({ chartMode: 'level' });
    expect(methodology).toMatch(/квартал|долг/i);
    expect(methodology).not.toMatch(/debt_new|xlsx|bulk_upsert/i);
  });

  it('getViewModeContent routes external debt family', () => {
    const { methodology } = getViewModeContent({
      chartMode: 'annual',
      safeViewMode: 'annual',
      isExternalDebtFamily: true,
      indicator: { code: 'external-debt' },
    });
    expect(methodology).toMatch(/год/i);
    expect(methodology).toMatch(/средн/i);
  });

  it('level and annual methodology differ', () => {
    const level = getExternalDebtViewModeContent({ chartMode: 'level' }).methodology;
    const annual = getExternalDebtViewModeContent({ chartMode: 'annual' }).methodology;
    expect(level).not.toBe(annual);
  });
});
