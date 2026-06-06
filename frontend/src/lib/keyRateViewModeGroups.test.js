import { describe, it, expect } from 'vitest';
import {
  KEY_RATE_TOP_GROUPS,
  normalizeKeyRateViewMode,
  topGroupForMode,
  expandedGroupForMode,
  defaultSubModeForGroup,
} from './keyRateViewModeGroups';

describe('keyRateViewModeGroups', () => {
  it('two top groups: level and agg', () => {
    expect(KEY_RATE_TOP_GROUPS).toHaveLength(2);
    expect(KEY_RATE_TOP_GROUPS[0].leafMode).toBe('level');
    expect(KEY_RATE_TOP_GROUPS[1].modes).toHaveLength(4);
  });

  it('normalize invalid to level', () => {
    expect(normalizeKeyRateViewMode(null)).toBe('level');
    expect(normalizeKeyRateViewMode('yoy')).toBe('level');
    expect(normalizeKeyRateViewMode('monthly')).toBe('monthly');
  });

  it('top and expanded groups', () => {
    expect(topGroupForMode('level')).toBe('level');
    expect(topGroupForMode('monthly')).toBe('agg');
    expect(expandedGroupForMode('monthly')).toBe('agg');
    expect(expandedGroupForMode('level')).toBeNull();
  });

  it('default sub-mode for agg is weekly', () => {
    expect(defaultSubModeForGroup('agg')).toBe('weekly');
  });
});
