import { describe, it, expect } from 'vitest';
import {
  EUR_RUB_TOP_GROUPS,
  normalizeEurRubViewMode,
  topGroupForMode,
} from './eurRubViewModeGroups';

describe('eurRubViewModeGroups', () => {
  it('level and agg groups', () => {
    expect(EUR_RUB_TOP_GROUPS[0].label).toMatch(/курс/i);
    expect(EUR_RUB_TOP_GROUPS[1].modes).toHaveLength(4);
  });

  it('normalize invalid to level', () => {
    expect(normalizeEurRubViewMode('inflation')).toBe('level');
    expect(topGroupForMode('quarterly')).toBe('agg');
  });
});
