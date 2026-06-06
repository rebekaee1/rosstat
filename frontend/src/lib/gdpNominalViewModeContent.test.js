import { describe, expect, it } from 'vitest';
import {
  getGdpNominalChartTitle,
  getGdpNominalViewModeContent,
  isGdpNominalFamily,
} from './gdpNominalViewModeContent';
import {
  gdpNominalCanonicalTarget,
  gdpNominalDataCodeForMode,
} from './gdpNominalViewModeResolve';

describe('gdpNominalViewModeContent', () => {
  it('isGdpNominalFamily for root and derived codes', () => {
    expect(isGdpNominalFamily('gdp-nominal')).toBe(true);
    expect(isGdpNominalFamily('gdp-yoy')).toBe(true);
    expect(isGdpNominalFamily('gdp-consumption')).toBe(false);
  });

  it('gdpNominalCanonicalTarget redirects derived URLs', () => {
    expect(gdpNominalCanonicalTarget('gdp-yoy')).toEqual({
      parentCode: 'gdp-nominal',
      mode: 'yoy',
    });
    expect(gdpNominalCanonicalTarget('gdp-nominal')).toBeNull();
  });

  it('gdpNominalDataCodeForMode maps modes to DB codes', () => {
    expect(gdpNominalDataCodeForMode('annual')).toBe('gdp-nominal-annual');
    expect(gdpNominalDataCodeForMode('qoq')).toBe('gdp-qoq');
  });

  it('content and titles vary by chartMode', () => {
    const level = getGdpNominalViewModeContent({ chartMode: 'level' });
    const yoy = getGdpNominalViewModeContent({ chartMode: 'yoy' });
    expect(level.description).not.toEqual(yoy.description);
    expect(getGdpNominalChartTitle('yoy')).toMatch(/год к году/i);
  });
});
