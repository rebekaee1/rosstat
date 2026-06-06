import { describe, expect, it } from 'vitest';
import {
  getUnemploymentChartTitle,
  getUnemploymentViewModeContent,
  isUnemploymentFamily,
} from './unemploymentViewModeContent';
import { unemploymentCanonicalTarget, unemploymentDataCodeForMode } from './unemploymentViewModeResolve';

describe('unemploymentViewModeContent', () => {
  it('isUnemploymentFamily for root and derived codes', () => {
    expect(isUnemploymentFamily('unemployment')).toBe(true);
    expect(isUnemploymentFamily('unemployment-quarterly')).toBe(true);
    expect(isUnemploymentFamily('employment')).toBe(false);
  });

  it('canonical target for derived URLs', () => {
    expect(unemploymentCanonicalTarget('unemployment-quarterly')).toEqual({
      parentCode: 'unemployment',
      mode: 'quarterly',
    });
    expect(unemploymentCanonicalTarget('unemployment')).toBeNull();
  });

  it('data codes per mode', () => {
    expect(unemploymentDataCodeForMode('quarterly')).toBe('unemployment-quarterly');
    expect(unemploymentDataCodeForMode('annual')).toBe('unemployment-annual');
  });

  it('chart titles per mode', () => {
    expect(getUnemploymentChartTitle('annual')).toMatch(/12М/i);
    expect(getUnemploymentChartTitle('quarterly')).toMatch(/квартал/i);
  });

  it('annual mode explains rolling window', () => {
    const { methodology } = getUnemploymentViewModeContent({ chartMode: 'annual' });
    expect(methodology).toMatch(/12/i);
    expect(methodology).toMatch(/производный ряд/i);
  });
});
