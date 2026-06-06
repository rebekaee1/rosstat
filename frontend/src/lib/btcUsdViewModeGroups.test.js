import { describe, it, expect } from 'vitest';
import {
  BTC_USD_TOP_GROUPS,
  normalizeBtcUsdViewMode,
  topGroupForMode,
} from './btcUsdViewModeGroups';

describe('btcUsdViewModeGroups', () => {
  it('level and agg groups', () => {
    expect(BTC_USD_TOP_GROUPS[0].label).toMatch(/цен/i);
    expect(BTC_USD_TOP_GROUPS[1].modes).toHaveLength(4);
  });

  it('normalize invalid to level', () => {
    expect(normalizeBtcUsdViewMode('inflation')).toBe('level');
    expect(topGroupForMode('annual')).toBe('agg');
  });
});
