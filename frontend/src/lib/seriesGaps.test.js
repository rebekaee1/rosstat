import { describe, expect, it } from 'vitest';
import {
  gapIndexes, hasGaps, insertGapRows, seriesCadenceDays, withoutGapRows,
} from './seriesGaps';

const quarters = (y0, n) => Array.from({ length: n }, (_, i) => {
  const q = i % 4;
  return `${y0 + Math.floor(i / 4)}-${String(q * 3 + 1).padStart(2, '0')}-01`;
});

describe('seriesGaps', () => {
  it('частота по медианному шагу: год, квартал, месяц; дни и недели не трогаем', () => {
    expect(seriesCadenceDays(['2019-01-01', '2020-01-01', '2021-01-01'])).toBe(365);
    expect(seriesCadenceDays(quarters(2015, 8))).toBe(91);
    expect(seriesCadenceDays(['2025-01-01', '2025-02-01', '2025-03-01', '2025-04-01'])).toBe(30);
    expect(seriesCadenceDays(['2025-01-01', '2025-01-02', '2025-01-03', '2025-01-06'])).toBe(0);
    expect(seriesCadenceDays(['2025-01-06', '2025-01-13', '2025-01-20'])).toBe(0);
  });

  it('Египет: после IV кв. 2015 сразу I кв. 2019 — один пропуск', () => {
    const rows = [...quarters(2015, 4), ...quarters(2019, 4)].map((date) => ({ date, actual: 5 }));
    expect([...gapIndexes(rows)]).toEqual([4]);
    expect(hasGaps(rows)).toBe(true);
    const withGap = insertGapRows(rows);
    expect(withGap).toHaveLength(9);
    const hole = withGap[4];
    expect(hole._gap).toBe(true);
    expect(hole.actual).toBeNull();
    expect(hole.date > '2015-10-01' && hole.date < '2019-01-01').toBe(true);
    expect(withoutGapRows(withGap)).toEqual(rows);
  });

  it('ряд без пропусков возвращается тем же массивом (вид не меняется)', () => {
    const rows = quarters(2020, 12).map((date) => ({ date, actual: 1 }));
    expect(insertGapRows(rows)).toBe(rows);
    expect(hasGaps(rows)).toBe(false);
    const daily = ['2025-01-01', '2025-01-02', '2025-01-03', '2025-01-06'].map((date) => ({ date, actual: 1 }));
    expect(insertGapRows(daily)).toBe(daily);
  });

  it('прогноз после факта не создаёт пропуск', () => {
    const rows = [...quarters(2024, 4).map((date) => ({ date, actual: 1 })), { date: '2026-01-01', actual: null, forecast: 2 }];
    expect(insertGapRows(rows)).toBe(rows);
  });

  it('годовой ряд с пропущенным годом рвётся', () => {
    const rows = ['2010', '2011', '2012', '2015'].map((y) => ({ date: `${y}-01-01`, actual: 1 }));
    expect([...gapIndexes(rows)]).toEqual([3]);
  });
});
