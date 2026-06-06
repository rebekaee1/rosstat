import { describe, it, expect } from 'vitest';
import {
  EXTERNAL_DEBT_TOP_GROUPS,
  defaultSubModeForGroup,
} from './externalDebtViewModeGroups';

describe('externalDebtViewModeGroups', () => {
  it('has quarterly level and annual agg', () => {
    expect(EXTERNAL_DEBT_TOP_GROUPS[0].label).toMatch(/поквартал/i);
    expect(EXTERNAL_DEBT_TOP_GROUPS[1].modes).toHaveLength(1);
    expect(EXTERNAL_DEBT_TOP_GROUPS[1].modes[0].mode).toBe('annual');
  });

  it('defaultSubModeForGroup returns annual for agg', () => {
    expect(defaultSubModeForGroup('agg')).toBe('annual');
  });
});
