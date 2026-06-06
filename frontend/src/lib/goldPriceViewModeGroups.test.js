import { describe, it, expect } from 'vitest';
import {
  GOLD_PRICE_TOP_GROUPS,
  defaultSubModeForGroup,
} from './goldPriceViewModeGroups';

describe('goldPriceViewModeGroups', () => {
  it('has daily level and four agg modes', () => {
    expect(GOLD_PRICE_TOP_GROUPS[0].label).toMatch(/ежедневно/i);
    expect(GOLD_PRICE_TOP_GROUPS[1].modes).toHaveLength(4);
  });

  it('defaultSubModeForGroup returns weekly for agg', () => {
    expect(defaultSubModeForGroup('agg')).toBe('weekly');
  });
});
