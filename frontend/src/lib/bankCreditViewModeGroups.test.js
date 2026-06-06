import { describe, it, expect } from 'vitest';
import {
  BANK_CREDIT_TOP_GROUPS,
  normalizeBankCreditViewMode,
  topGroupForMode,
} from './bankCreditViewModeGroups';

describe('bankCreditViewModeGroups', () => {
  it('level and agg groups', () => {
    expect(BANK_CREDIT_TOP_GROUPS[0].label).toMatch(/помесячно/i);
    expect(BANK_CREDIT_TOP_GROUPS[1].modes).toHaveLength(2);
  });

  it('normalize invalid to level', () => {
    expect(normalizeBankCreditViewMode('yoy')).toBe('level');
    expect(topGroupForMode('annual')).toBe('agg');
  });
});
