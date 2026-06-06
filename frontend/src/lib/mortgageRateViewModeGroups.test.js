import { describe, it, expect } from 'vitest';
import {
  MORTGAGE_RATE_TOP_GROUPS,
  normalizeMortgageViewMode,
  topGroupForMode,
} from './mortgageRateViewModeGroups';

describe('mortgageRateViewModeGroups', () => {
  it('single top group with leaf level', () => {
    expect(MORTGAGE_RATE_TOP_GROUPS).toHaveLength(1);
    expect(MORTGAGE_RATE_TOP_GROUPS[0].leafMode).toBe('level');
  });

  it('normalize always level', () => {
    expect(normalizeMortgageViewMode(null)).toBe('level');
    expect(normalizeMortgageViewMode('yoy')).toBe('level');
    expect(topGroupForMode('level')).toBe('level');
  });
});
