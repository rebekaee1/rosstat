import { describe, it, expect } from 'vitest';
import { AGE_GROUP_CODES, demographicTotal, latestCompleteStructure, demographicChartRows } from './demographicStructure';
const complete = { year: 2023, ...Object.fromEntries(AGE_GROUP_CODES.map((code, index) => [code, [20, 80, 30][index]])) };
const missing = { year: 2024, [AGE_GROUP_CODES[0]]: 21 };
describe('age structure', () => {
  it('uses the latest complete year and keeps missing observations empty', () => {
    expect(latestCompleteStructure([complete, missing])).toEqual(complete);
    expect(demographicTotal(missing)).toBeNull();
    expect(demographicChartRows([missing], true)[0][AGE_GROUP_CODES[0]]).toBeNull();
    expect(demographicTotal({ ...complete, [AGE_GROUP_CODES[0]]: -1 })).toBeNull();
  });
  it('preserves counts and computes shares only over all three groups', () => {
    expect(demographicChartRows([complete])[0]).toEqual(complete);
    const percentages = demographicChartRows([complete], true)[0];
    expect(AGE_GROUP_CODES.reduce((s, code) => s + percentages[code], 0)).toBeCloseTo(100);
  });
});
