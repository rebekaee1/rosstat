import { describe, expect, it } from 'vitest';
import {
  DEATHS_TOP_GROUPS,
  highlightedTopGroup,
  normalizeDeathsViewMode,
  topGroupForMode,
} from './deathsViewModeGroups';

describe('deathsViewModeGroups', () => {
  it('mirrors T10 modes: level, yoy, index', () => {
    expect(DEATHS_TOP_GROUPS.map((g) => [g.id, g.leafMode])).toEqual([
      ['level', 'level'],
      ['yoy', 'yoy'],
      ['index', 'index'],
    ]);
  });

  it('normalizes unknown mode to level', () => {
    expect(normalizeDeathsViewMode(null)).toBe('level');
    expect(normalizeDeathsViewMode('bogus')).toBe('level');
    expect(normalizeDeathsViewMode('yoy')).toBe('yoy');
  });

  it('highlightedTopGroup follows currentMode when expanded is null', () => {
    expect(highlightedTopGroup(null, 'index')).toBe('index');
    expect(topGroupForMode('yoy')).toBe('yoy');
  });
});
