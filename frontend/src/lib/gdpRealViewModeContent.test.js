import { describe, expect, it } from 'vitest';
import {
  getGdpRealChartTitle,
  getGdpRealViewModeContent,
  isGdpRealFamily,
} from './gdpRealViewModeContent';
import {
  gdpRealCanonicalTarget,
  gdpRealDataCodeForMode,
} from './gdpRealViewModeResolve';

describe('gdpRealViewModeContent', () => {
  it('isGdpRealFamily for root and derived codes', () => {
    expect(isGdpRealFamily('gdp-real')).toBe(true);
    expect(isGdpRealFamily('gdp-real-yoy')).toBe(true);
    expect(isGdpRealFamily('gdp-nominal')).toBe(false);
  });

  it('gdpRealCanonicalTarget redirects derived URLs', () => {
    expect(gdpRealCanonicalTarget('gdp-real-qoq')).toEqual({
      parentCode: 'gdp-real',
      mode: 'qoq',
    });
    expect(gdpRealCanonicalTarget('gdp-real')).toBeNull();
  });

  it('gdpRealDataCodeForMode maps modes to DB codes', () => {
    expect(gdpRealDataCodeForMode('annual')).toBe('gdp-real-annual');
    expect(gdpRealDataCodeForMode('yoy')).toBe('gdp-real-yoy');
  });

  it('content and titles vary by chartMode', () => {
    const level = getGdpRealViewModeContent({ chartMode: 'level' });
    const yoy = getGdpRealViewModeContent({ chartMode: 'yoy' });
    expect(level.description).not.toEqual(yoy.description);
    expect(getGdpRealChartTitle('qoq')).toMatch(/квартал/i);
  });
});
