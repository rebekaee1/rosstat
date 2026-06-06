import { describe, expect, it } from 'vitest';
import {
  UNEMPLOYMENT_TOP_GROUPS,
  defaultSubModeForGroup,
  expandedGroupForMode,
} from './unemploymentViewModeGroups';

describe('unemploymentViewModeGroups', () => {
  it('has level and agg groups', () => {
    expect(UNEMPLOYMENT_TOP_GROUPS.map((g) => g.id)).toEqual(['level', 'agg']);
    const agg = UNEMPLOYMENT_TOP_GROUPS.find((g) => g.id === 'agg');
    expect(agg.modes.map((m) => m.mode)).toEqual(['quarterly', 'annual']);
  });

  it('expandedGroupForMode for annual', () => {
    expect(expandedGroupForMode('annual')).toBe('agg');
    expect(defaultSubModeForGroup('agg')).toBe('quarterly');
  });
});
