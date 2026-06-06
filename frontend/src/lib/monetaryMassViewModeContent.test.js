import { describe, expect, it } from 'vitest';
import {
  getMonetaryMassChartTitle,
  getMonetaryMassViewModeContent,
  isMonetaryMassFamily,
} from './monetaryMassViewModeContent';

describe('monetaryMassViewModeContent', () => {
  it('isMonetaryMassFamily for m0 m1 m2 only', () => {
    expect(isMonetaryMassFamily('m0')).toBe(true);
    expect(isMonetaryMassFamily('m1')).toBe(true);
    expect(isMonetaryMassFamily('m2')).toBe(true);
    expect(isMonetaryMassFamily('m3')).toBe(false);
  });

  it('chart titles differ by aggregate', () => {
    expect(getMonetaryMassChartTitle('level', 'm0')).toMatch(/М0/i);
    expect(getMonetaryMassChartTitle('level', 'm2')).toMatch(/М2/i);
  });

  it('m1 content mentions transferable deposits concept', () => {
    const { description } = getMonetaryMassViewModeContent({
      chartMode: 'level',
      indicatorCode: 'm1',
    });
    expect(description).toMatch(/переводн|М0/i);
  });

  it('content avoids implementation jargon', () => {
    const { methodology } = getMonetaryMassViewModeContent({
      chartMode: 'quarterly',
      indicatorCode: 'm2',
    });
    expect(methodology).not.toMatch(/parser|bulk_upsert|ADR/i);
    expect(methodology).toMatch(/Банк России|Банка России/);
  });
});
