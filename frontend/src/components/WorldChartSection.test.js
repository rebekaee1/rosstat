import { describe, expect, it } from 'vitest';
import { rebaseWorldComparison } from '../lib/worldComparison';

describe('rebaseWorldComparison', () => {
  it('uses the first exact date shared by every country', () => {
    const result = rebaseWorldComparison(
      [
        { date: '2020-01-01', value: 10 },
        { date: '2021-01-01', value: 12 },
        { date: '2022-01-01', value: 15 },
      ],
      [
        {
          label: 'A',
          data: [
            { date: '2021-01-01', value: 40 },
            { date: '2022-01-01', value: 44 },
          ],
        },
        {
          label: 'B',
          data: [
            { date: '2021-01-01', value: 5 },
            { date: '2022-01-01', value: 4 },
          ],
        },
      ],
    );

    expect(result.startDate).toBe('2021-01-01');
    expect(result.base.map((point) => point.value)).toEqual([100, 125]);
    expect(result.series[0].data[0].value).toBe(100);
    expect(result.series[0].data[1].value).toBeCloseTo(110);
    expect(result.series[1].data.map((point) => point.value)).toEqual([100, 80]);
  });

  it('fails closed when the series have no common positive date', () => {
    expect(rebaseWorldComparison(
      [{ date: '2020-01-01', value: 10 }],
      [{ label: 'A', data: [{ date: '2021-01-01', value: 20 }] }],
    )).toBeNull();
  });
});
