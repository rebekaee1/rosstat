import { describe, it, expect } from 'vitest';
import { normalizeCbrTermSliceViewMode } from './cbrTermSliceRateGroups';
import { CBR_TERM_SLICE_CODES } from './cbrTermSliceRateResolve';

describe('cbrTermSliceRateGroups', () => {
  it('nine term-slice indicators', () => {
    expect(CBR_TERM_SLICE_CODES).toHaveLength(9);
  });

  it('normalize unknown modes to level', () => {
    expect(normalizeCbrTermSliceViewMode('mom')).toBe('level');
  });
});
