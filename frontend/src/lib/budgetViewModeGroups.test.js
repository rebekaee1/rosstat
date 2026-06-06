import { describe, it, expect } from 'vitest';
import {
  BUDGET_TOP_GROUPS,
  normalizeBudgetViewMode,
  topGroupForMode,
} from './budgetViewModeGroups';

describe('budgetViewModeGroups', () => {
  it('level and agg groups', () => {
    expect(BUDGET_TOP_GROUPS[0].label).toMatch(/помесячно/i);
    expect(BUDGET_TOP_GROUPS[1].modes).toHaveLength(2);
  });

  it('normalize invalid to level', () => {
    expect(normalizeBudgetViewMode('inflation')).toBe('level');
    expect(topGroupForMode('quarterly')).toBe('agg');
  });
});
