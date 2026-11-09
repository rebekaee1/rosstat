import { describe, expect, it } from 'vitest';
import {
  deflateSeries, eventPeriods, fillMonthGaps, keyYearRows, monthGaps, timesText, yearlyRows,
} from './z2PriceHistory';

const mk = (y, m, value) => ({ year: y, month: m, value, label: `${y}-${String(m).padStart(2, '0')}` });

describe('z2PriceHistory', () => {
  it('keyYearRows берёт Россию, когда у региона года нет, и оставляет пустую строку без данных', () => {
    const region = [mk(2008, 9, 20), mk(2026, 9, 80)];
    const russia = [mk(2000, 9, 8), mk(2008, 9, 22), mk(2026, 9, 76)];
    const rows = keyYearRows(region, russia, region[1], null);
    const r2000 = rows.find((r) => r.year === 2000);
    expect(r2000.source).toBe('russia');
    expect(r2000.times).toBeCloseTo(9.5, 1);
    expect(rows.find((r) => r.year === 2008).source).toBe('region');
    expect(rows.find((r) => r.year === 2014).point).toBeNull();
  });

  it('инфляция и «без инфляции» считаются из индекса ИПЦ', () => {
    const s = [mk(2008, 9, 20), mk(2026, 9, 80)];
    const cpi = [[200809, 100], [202609, 200]];
    const [row] = keyYearRows(s, null, s[1], cpi, [2008]);
    expect(row.times).toBe(4);
    expect(row.infl).toBe(2);
    expect(row.real).toBe(2);
  });

  it('deflateSeries приводит цены к рублям последнего месяца', () => {
    const s = [mk(2020, 1, 10), mk(2020, 2, 10), mk(2020, 3, 10)];
    const cpi = [[202001, 100], [202002, 110], [202003, 200]];
    const out = deflateSeries(s, cpi, 202003);
    expect(out.map((p) => p.value)).toEqual([20, 18.18, 10]);
  });

  it('monthGaps и fillMonthGaps находят дыру и рвут линию пустыми месяцами', () => {
    const s = [mk(2010, 1, 1), mk(2010, 2, 2), mk(2010, 5, 5)];
    expect(monthGaps(s)).toEqual([{ from: 201002, to: 201005, months: 2 }]);
    const f = fillMonthGaps(s);
    expect(f.length).toBe(5);
    expect(f[2].value).toBeNull();
  });

  it('timesText склоняет «раз/раза»', () => {
    expect(timesText(2.7)).toContain('раза');
    expect(timesText(5)).toContain('раз');
    expect(timesText(5)).not.toContain('раза');
    expect(timesText(3)).toContain('раза');
  });

  it('eventPeriods отдаёт только годы внутри периода, yearlyRows идёт от нового к старому', () => {
    const pts = [];
    for (let y = 2003; y <= 2026; y++) for (let m = 1; m <= 12; m++) pts.push(mk(y, m, y));
    expect(eventPeriods(pts).map((e) => e.year)).toEqual([2008, 2014, 2022]);
    expect(eventPeriods(pts.slice(-30))).toEqual([]);
    const rows = yearlyRows(pts, pts[pts.length - 1]);
    expect(rows[0].year).toBe(2025);
    expect(rows[rows.length - 1].yoy).toBeNull();
  });
});
