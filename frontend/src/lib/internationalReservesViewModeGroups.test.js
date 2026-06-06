import { describe, expect, it } from 'vitest';
import {
  INTERNATIONAL_RESERVES_TOP_GROUPS,
  defaultSubModeForGroup,
  topGroupForMode,
} from './internationalReservesViewModeGroups';

describe('internationalReservesViewModeGroups', () => {
  it('has weekly level and three agg submodes', () => {
    expect(INTERNATIONAL_RESERVES_TOP_GROUPS[0].label).toMatch(/еженедел/i);
    expect(INTERNATIONAL_RESERVES_TOP_GROUPS[1].modes).toHaveLength(3);
  });

  it('defaultSubModeForGroup returns monthly for agg', () => {
    expect(defaultSubModeForGroup('agg')).toBe('monthly');
  });

  it('topGroupForMode maps agg modes', () => {
    expect(topGroupForMode('level')).toBe('level');
    expect(topGroupForMode('annual')).toBe('agg');
  });
});
