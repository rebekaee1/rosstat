import { describe, it, expect } from 'vitest';
import {
  getBankCreditViewModeContent,
  isBankCreditFamily,
} from './bankCreditViewModeContent';
import { getViewModeContent } from './cpiViewModeContent';

describe('bankCreditViewModeContent', () => {
  it('isBankCreditFamily only for business credit', () => {
    expect(isBankCreditFamily('business-credit')).toBe(true);
    expect(isBankCreditFamily('consumer-credit')).toBe(false);
    expect(isBankCreditFamily('deposits-individual')).toBe(false);
  });

  it('level content mentions portfolio without jargon', () => {
    const { methodology } = getBankCreditViewModeContent({ chartMode: 'level' });
    expect(methodology).toMatch(/задолженност|выдач/i);
    expect(methodology).not.toMatch(/publicationId|dataservice/i);
  });

  it('getViewModeContent routes bank credit family', () => {
    const { methodology } = getViewModeContent({
      chartMode: 'quarterly',
      safeViewMode: 'quarterly',
      isBankCreditFamily: true,
      indicator: { code: 'business-credit' },
    });
    expect(methodology).toMatch(/квартал/i);
    expect(methodology).toMatch(/корпоратив/i);
  });

  it('quarterly and annual methodology differ', () => {
    const q = getBankCreditViewModeContent({ chartMode: 'quarterly' }).methodology;
    const y = getBankCreditViewModeContent({ chartMode: 'annual' }).methodology;
    expect(q).not.toBe(y);
  });
});
