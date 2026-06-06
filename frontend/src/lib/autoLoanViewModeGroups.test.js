import { describe, it, expect } from 'vitest';
import {
  AUTO_LOAN_TOP_GROUPS,
  normalizeAutoLoanViewMode,
  topGroupForMode,
} from './autoLoanViewModeGroups';

describe('autoLoanViewModeGroups', () => {
  it('single top group with leaf level', () => {
    expect(AUTO_LOAN_TOP_GROUPS).toHaveLength(1);
    expect(AUTO_LOAN_TOP_GROUPS[0].leafMode).toBe('level');
  });

  it('normalize always level', () => {
    expect(normalizeAutoLoanViewMode(null)).toBe('level');
    expect(normalizeAutoLoanViewMode('yoy')).toBe('level');
    expect(topGroupForMode('level')).toBe('level');
  });
});
