import { describe, it, expect } from 'vitest';
import {
  CNY_RUB_TOP_GROUPS,
  normalizeCnyRubViewMode,
  topGroupForMode,
} from './cnyRubViewModeGroups';

describe('cnyRubViewModeGroups', () => {
  it('level and agg groups', () => {
    expect(CNY_RUB_TOP_GROUPS[0].label).toMatch(/курс/i);
    expect(CNY_RUB_TOP_GROUPS[1].modes).toHaveLength(4);
  });

  it('normalize invalid to level', () => {
    expect(normalizeCnyRubViewMode('inflation')).toBe('level');
    expect(topGroupForMode('monthly')).toBe('agg');
  });
});
