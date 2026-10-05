import { describe, it, expect } from 'vitest';
import {
  countrySeries, rankMap, rankShifts, shareOf, valueAt, yearOverYear,
} from './ratingInsights';

const years = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025];
function build(table) {
  const out = {};
  for (const [year, values] of Object.entries(table)) {
    out[year] = {};
    for (const [code, value] of Object.entries(values)) out[year][code] = { country_code: code, value };
  }
  return out;
}

describe('ratingInsights', () => {
  const byYear = build({
    2019: { A: 10, B: 8, C: 6 },
    2020: { A: 11, B: 9, C: 6 },
    2024: { A: 12, B: 15, C: 7 },
    2025: { A: 13, B: 16 },
  });

  it('valueAt ignores empty and non-numeric values', () => {
    expect(valueAt(byYear, 2025, 'A')).toBe(13);
    expect(valueAt(byYear, 2025, 'C')).toBeNull();
    expect(valueAt(build({ 2025: { A: null } }), 2025, 'A')).toBeNull();
  });

  it('yearOverYear compares with the nearest previous year with data, within three years', () => {
    expect(yearOverYear(byYear, years, 2025, 'A')).toMatchObject({ year: 2024, abs: 1 });
    expect(yearOverYear(byYear, years, 2025, 'A').pct).toBeCloseTo(8.333, 2);
    expect(yearOverYear(byYear, years, 2025, 'C')).toBeNull();
    // 2020 -> 2025 is further than three years: no change is claimed.
    expect(yearOverYear(build({ 2020: { A: 5 }, 2025: { A: 7 } }), years, 2025, 'A')).toBeNull();
  });

  it('yearOverYear leaves pct empty for a non-positive base', () => {
    const data = build({ 2024: { A: -2 }, 2025: { A: 1 } });
    expect(yearOverYear(data, years, 2025, 'A')).toMatchObject({ abs: 3, pct: null });
  });

  it('countrySeries returns ascending points up to the active year', () => {
    expect(countrySeries(byYear, years, 2025, 'A').map((p) => p.year)).toEqual([2019, 2020, 2024, 2025]);
    expect(countrySeries(byYear, years, 2020, 'A').map((p) => p.value)).toEqual([10, 11]);
    expect(countrySeries(byYear, years, 2025, 'A', 2)).toHaveLength(2);
  });

  it('rankMap honours the direction', () => {
    expect([...rankMap(byYear, 2019, 'desc').entries()]).toEqual([['A', 1], ['B', 2], ['C', 3]]);
    expect([...rankMap(byYear, 2019, 'asc').entries()]).toEqual([['C', 1], ['B', 2], ['A', 3]]);
  });

  it('rankShifts lists the biggest risers and fallers for five years back', () => {
    const rows = {};
    const codes = 'ABCDEFGHIJ'.split('');
    // 2020: A is best, J is worst. 2025: order is reversed for the last two.
    rows[2020] = Object.fromEntries(codes.map((c, i) => [c, 100 - i * 5]));
    rows[2025] = Object.fromEntries(codes.map((c, i) => [c, 100 - i * 5]));
    rows[2025].J = 99.5; // J climbs to second place
    const data = build(rows);
    const shifts = rankShifts(data, [2020, 2025], 2025, 'desc');
    expect(shifts.fromYear).toBe(2020);
    expect(shifts.risers[0]).toMatchObject({ code: 'J', then: 10, now: 2, change: 8 });
    expect(shifts.fallers[0].code).toBe('B');
  });

  it('rankShifts returns null when there is nothing to compare with', () => {
    expect(rankShifts(byYear, years, 2025, 'desc')).toBeNull();
    expect(rankShifts({}, [], 2025, 'desc')).toBeNull();
  });

  it('shareOf is zero for negative data and clamps to 2..100', () => {
    expect(shareOf(50, 100)).toBe(50);
    expect(shareOf(0.1, 100)).toBe(2);
    expect(shareOf(5, 100, false)).toBe(0);
    expect(shareOf(-1, 100)).toBe(0);
    expect(shareOf(200, 100)).toBe(100);
  });
});
