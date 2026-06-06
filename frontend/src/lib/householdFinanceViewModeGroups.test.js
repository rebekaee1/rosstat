import { describe, it, expect } from 'vitest';
import {
  HOUSEHOLD_FINANCE_TOP_GROUPS,
  defaultSubModeForGroup,
  getTopGroup,
} from './householdFinanceViewModeGroups';

describe('householdFinanceViewModeGroups', () => {
  it('has level and agg groups', () => {
    expect(HOUSEHOLD_FINANCE_TOP_GROUPS[0].label).toMatch(/помесячно/i);
    expect(HOUSEHOLD_FINANCE_TOP_GROUPS[1].modes).toHaveLength(2);
  });

  it('defaultSubModeForGroup returns quarterly for agg', () => {
    expect(defaultSubModeForGroup('agg')).toBe('quarterly');
    expect(getTopGroup('agg')?.modes?.[0]?.mode).toBe('quarterly');
  });
});
