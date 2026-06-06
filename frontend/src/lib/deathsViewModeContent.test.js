import { describe, expect, it } from 'vitest';
import {
  getDeathsChartTitle,
  getDeathsViewModeContent,
  isDeathsDemoFamily,
} from './deathsViewModeContent';
import {
  deathsCanonicalTarget,
  isDeathsVirtualYoyMode,
  normalizeDeathsViewMode,
} from './deathsViewModeResolve';

describe('deathsViewModeContent', () => {
  it('isDeathsDemoFamily for deaths and death-rate', () => {
    expect(isDeathsDemoFamily('deaths')).toBe(true);
    expect(isDeathsDemoFamily('death-rate')).toBe(true);
    expect(isDeathsDemoFamily('births')).toBe(false);
  });

  it('deathsCanonicalTarget is null (no derived URLs)', () => {
    expect(deathsCanonicalTarget('deaths')).toBeNull();
  });

  it('yoy mode is virtual', () => {
    expect(isDeathsVirtualYoyMode('yoy')).toBe(true);
    expect(normalizeDeathsViewMode('unknown')).toBe('level');
  });

  it('content and titles vary by chartMode and slice', () => {
    const deathsLevel = getDeathsViewModeContent({ chartMode: 'level', indicatorCode: 'deaths' });
    const rateYoy = getDeathsViewModeContent({ chartMode: 'yoy', indicatorCode: 'death-rate' });
    expect(deathsLevel.description).not.toEqual(rateYoy.description);
    expect(getDeathsChartTitle('yoy', 'deaths')).toMatch(/смерт/i);
  });
});
