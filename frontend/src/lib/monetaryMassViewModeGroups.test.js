import { describe, expect, it } from 'vitest';
import {
  MONETARY_MASS_TOP_GROUPS,
  defaultSubModeForGroup,
  topGroupForMode,
} from './monetaryMassViewModeGroups';

describe('monetaryMassViewModeGroups', () => {
  it('has monthly level and quarterly/annual agg', () => {
    expect(MONETARY_MASS_TOP_GROUPS[0].label).toMatch(/помесяч/i);
    expect(MONETARY_MASS_TOP_GROUPS[1].modes).toHaveLength(2);
  });

  it('defaultSubModeForGroup returns quarterly for agg', () => {
    expect(defaultSubModeForGroup('agg')).toBe('quarterly');
  });

  it('topGroupForMode maps agg modes', () => {
    expect(topGroupForMode('annual')).toBe('agg');
  });
});
