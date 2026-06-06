import { describe, it, expect } from 'vitest';
import {
  USD_RUB_TOP_GROUPS,
  normalizeUsdRubViewMode,
  topGroupForMode,
} from './usdRubViewModeGroups';

describe('usdRubViewModeGroups', () => {
  it('level and agg groups', () => {
    expect(USD_RUB_TOP_GROUPS[0].label).toMatch(/курс/i);
    expect(USD_RUB_TOP_GROUPS[1].modes).toHaveLength(4);
  });

  it('normalize invalid to level', () => {
    expect(normalizeUsdRubViewMode('inflation')).toBe('level');
    expect(topGroupForMode('weekly')).toBe('agg');
  });
});
