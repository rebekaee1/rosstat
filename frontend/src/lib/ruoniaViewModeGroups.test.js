import { describe, it, expect } from 'vitest';
import {
  RUONIA_TOP_GROUPS,
  normalizeRuoniaViewMode,
  topGroupForMode,
  expandedGroupForMode,
  defaultSubModeForGroup,
} from './ruoniaViewModeGroups';

describe('ruoniaViewModeGroups', () => {
  it('two top groups: level and agg', () => {
    expect(RUONIA_TOP_GROUPS).toHaveLength(2);
    expect(RUONIA_TOP_GROUPS[1].modes).toHaveLength(4);
  });

  it('normalize invalid to level', () => {
    expect(normalizeRuoniaViewMode('inflation')).toBe('level');
    expect(normalizeRuoniaViewMode('monthly')).toBe('monthly');
  });

  it('agg group expands for monthly', () => {
    expect(topGroupForMode('monthly')).toBe('agg');
    expect(expandedGroupForMode('monthly')).toBe('agg');
    expect(defaultSubModeForGroup('agg')).toBe('weekly');
  });
});
