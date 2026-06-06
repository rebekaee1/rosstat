import { describe, expect, it } from 'vitest';
import {
  GDP_USE_TOP_GROUPS,
  defaultSubModeForGroup,
  getTopGroup,
} from './gdpUseViewModeGroups';

describe('gdpUseViewModeGroups', () => {
  it('has quarterly leaf and annual under agg', () => {
    expect(GDP_USE_TOP_GROUPS).toHaveLength(2);
    expect(getTopGroup('level')?.leafMode).toBe('level');
    expect(defaultSubModeForGroup('agg')).toBe('annual');
  });
});
