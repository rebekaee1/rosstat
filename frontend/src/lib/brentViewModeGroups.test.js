import { describe, it, expect } from 'vitest';
import {
  BRENT_TOP_GROUPS,
  normalizeBrentViewMode,
  topGroupForMode,
} from './brentViewModeGroups';

describe('brentViewModeGroups', () => {
  it('level and agg groups', () => {
    expect(BRENT_TOP_GROUPS[0].label).toMatch(/цен/i);
    expect(BRENT_TOP_GROUPS[1].modes).toHaveLength(4);
  });

  it('normalize invalid to level', () => {
    expect(normalizeBrentViewMode('inflation')).toBe('level');
    expect(topGroupForMode('annual')).toBe('agg');
  });
});
