import { describe, expect, it } from 'vitest';
import {
  getGdpUseChartTitle,
  getGdpUseViewModeContent,
  isGdpUseFamily,
} from './gdpUseViewModeContent';
import { gdpUseAggGranularity } from './gdpUseViewModeResolve';

describe('gdpUseViewModeContent', () => {
  it('isGdpUseFamily for consumption and government', () => {
    expect(isGdpUseFamily('gdp-consumption')).toBe(true);
    expect(isGdpUseFamily('gdp-government')).toBe(true);
    expect(isGdpUseFamily('gdp-investment')).toBe(false);
  });

  it('annual mode uses year aggregation', () => {
    expect(gdpUseAggGranularity('annual')).toBe('year');
    expect(gdpUseAggGranularity('level')).toBeNull();
  });

  it('chart titles differ by slice', () => {
    expect(getGdpUseChartTitle('level', 'gdp-consumption')).toMatch(/домохозяй/i);
    expect(getGdpUseChartTitle('level', 'gdp-government')).toMatch(/государ/i);
  });

  it('government annual mode explains averaging', () => {
    const { methodology } = getGdpUseViewModeContent({
      chartMode: 'annual',
      indicatorCode: 'gdp-government',
    });
    expect(methodology).toMatch(/средн/i);
    expect(methodology).toMatch(/прогноз/i);
  });
});
