import { describe, expect, it } from 'vitest';
import {
  getLaborMarketChartTitle,
  getLaborMarketViewModeContent,
  isLaborMarketFamily,
} from './laborMarketViewModeContent';

describe('laborMarketViewModeContent', () => {
  it('isLaborMarketFamily for labor-force and employment only', () => {
    expect(isLaborMarketFamily('employment')).toBe(true);
    expect(isLaborMarketFamily('labor-force')).toBe(true);
    expect(isLaborMarketFamily('unemployment')).toBe(false);
  });

  it('employment chart titles differ from labor-force', () => {
    expect(getLaborMarketChartTitle('level', 'employment')).toMatch(/Занятое/i);
    expect(getLaborMarketChartTitle('level', 'labor-force')).toMatch(/Рабочая сила/i);
  });

  it('quarterly methodology mentions Росстат', () => {
    const { methodology } = getLaborMarketViewModeContent({
      chartMode: 'quarterly',
      indicatorCode: 'employment',
    });
    expect(methodology).toMatch(/Росстат/);
    expect(methodology).not.toMatch(/средний М2/i);
  });

  it('labor-force level description differs from employment', () => {
    const emp = getLaborMarketViewModeContent({
      chartMode: 'level',
      indicatorCode: 'employment',
    });
    const lf = getLaborMarketViewModeContent({
      chartMode: 'level',
      indicatorCode: 'labor-force',
    });
    expect(lf.description).toMatch(/ищет работу|рабочей силы/i);
    expect(emp.description).not.toEqual(lf.description);
  });
});
