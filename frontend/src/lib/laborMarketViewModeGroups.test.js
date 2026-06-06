import { describe, expect, it } from 'vitest';
import {
  LABOR_MARKET_TOP_GROUPS,
  defaultSubModeForGroup,
  expandedGroupForMode,
} from './laborMarketViewModeGroups';

describe('laborMarketViewModeGroups', () => {
  it('has level and agg groups', () => {
    expect(LABOR_MARKET_TOP_GROUPS.map((g) => g.id)).toEqual(['level', 'agg']);
  });

  it('expandedGroupForMode for quarterly', () => {
    expect(expandedGroupForMode('quarterly')).toBe('agg');
    expect(defaultSubModeForGroup('agg')).toBe('quarterly');
  });
});
