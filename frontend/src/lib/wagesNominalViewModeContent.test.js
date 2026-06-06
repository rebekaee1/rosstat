import { describe, expect, it } from 'vitest';
import {
  getWagesNominalChartTitle,
  getWagesNominalViewModeContent,
  isWagesNominalFamily,
} from './wagesNominalViewModeContent';
import {
  wagesNominalCanonicalTarget,
  wagesNominalDataCodeForMode,
} from './wagesNominalViewModeResolve';

describe('wagesNominalViewModeContent', () => {
  it('isWagesNominalFamily for root and derived codes', () => {
    expect(isWagesNominalFamily('wages-nominal')).toBe(true);
    expect(isWagesNominalFamily('wages-yoy')).toBe(true);
    expect(isWagesNominalFamily('unemployment')).toBe(false);
  });

  it('canonical target for derived URLs', () => {
    expect(wagesNominalCanonicalTarget('wages-real')).toEqual({
      parentCode: 'wages-nominal',
      mode: 'real',
    });
    expect(wagesNominalCanonicalTarget('wages-nominal')).toBeNull();
  });

  it('data codes per mode', () => {
    expect(wagesNominalDataCodeForMode('annual')).toBe('wages-nominal-annual');
    expect(wagesNominalDataCodeForMode('yoy')).toBe('wages-yoy');
  });

  it('chart titles per mode', () => {
    expect(getWagesNominalChartTitle('annual')).toMatch(/1991|годов/i);
    expect(getWagesNominalChartTitle('real')).toMatch(/реальн/i);
  });

  it('annual mode explains long history', () => {
    const { methodology } = getWagesNominalViewModeContent({ chartMode: 'annual' });
    expect(methodology).toMatch(/1991/i);
    expect(methodology).toMatch(/годов/i);
  });
});
