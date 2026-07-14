import { describe, it, expect } from 'vitest';
import {
  formatDate,
  formatChartAxisDate,
  formatAxisTick,
  pickChartAxisTicks,
  chartAxisTickBudget,
  formatValue,
  formatChange,
  formatValueWithUnit,
  unitSuffix,
  unitDigits,
  cn,
  adjustCpiDisplay,
  adjustCpiForecastDisplay,
  resolveDateFormat,
} from './format';

describe('format', () => {
  it('formatDate full month in Russian', () => {
    expect(formatDate('2024-01-15', 'full')).toContain('2024');
    expect(formatDate('2024-01-15', 'full')).toContain('январ');
  });

  it('formatDate day format includes day number in genitive', () => {
    expect(formatDate('2024-01-15', 'day')).toBe('15 января 2024');
    expect(formatDate('2024-02-03', 'day')).toBe('3 февраля 2024');
  });

  it('formatDate annual returns year only', () => {
    expect(formatDate('2024-06-15', 'annual')).toBe('2024');
  });

  it('formatDate quarterly returns roman quarter and year', () => {
    expect(formatDate('2024-01-15', 'quarterly')).toBe('I кв. 2024');
    expect(formatDate('2024-04-15', 'quarterly')).toBe('II кв. 2024');
    expect(formatDate('2024-07-15', 'quarterly')).toBe('III кв. 2024');
    expect(formatDate('2024-10-15', 'quarterly')).toBe('IV кв. 2024');
  });

  it('formatChartAxisDate shortens daily labels for dense charts', () => {
    expect(formatChartAxisDate('2024-01-15', 'day', { multiYear: false })).toBe('15 янв');
    expect(formatChartAxisDate('2024-01-15', 'day', { multiYear: true })).toBe("15 янв '24");
  });

  it('pickChartAxisTicks returns at most maxTicks evenly spaced', () => {
    const points = Array.from({ length: 200 }, (_, i) => ({
      date: `2024-${String((i % 12) + 1).padStart(2, '0')}-01`,
    }));
    const ticks = pickChartAxisTicks(points, 7);
    expect(ticks.length).toBeGreaterThanOrEqual(5);
    expect(ticks.length).toBeLessThanOrEqual(7);
    expect(ticks[0]).toBe(points[0].date);
    expect(ticks[ticks.length - 1]).toBe(points[points.length - 1].date);
  });

  it('pickChartAxisTicks supports custom dateKey (годовые региональные ряды)', () => {
    const points = Array.from({ length: 24 }, (_, i) => ({ year: 2000 + i }));
    const ticks = pickChartAxisTicks(points, 4, 'year');
    expect(ticks).toEqual([2000, 2008, 2015, 2023]);
  });

  it('pickChartAxisTicks annual cadence: равный шаг лет 2015–2025', () => {
    const points = Array.from({ length: 11 }, (_, i) => ({
      date: `${2015 + i}-12-31`,
    }));
    const ticks = pickChartAxisTicks(points, 6, { cadence: 'annual' });
    expect(ticks).toEqual([
      '2015-12-31',
      '2017-12-31',
      '2019-12-31',
      '2021-12-31',
      '2023-12-31',
      '2025-12-31',
    ]);
  });

  it('pickChartAxisTicks annual year-key cadence (регионы)', () => {
    const points = Array.from({ length: 11 }, (_, i) => ({ year: 2015 + i }));
    const ticks = pickChartAxisTicks(points, 6, { dateKey: 'year', cadence: 'annual' });
    expect(ticks).toEqual([2015, 2017, 2019, 2021, 2023, 2025]);
  });

  it('pickChartAxisTicks quarterly cadence: равный шаг кварталов', () => {
    const points = [];
    for (let y = 2020; y <= 2025; y += 1) {
      for (const m of [0, 3, 6, 9]) {
        points.push({ date: `${y}-${String(m + 1).padStart(2, '0')}-01` });
      }
    }
    // 2020-Q1 … 2025-Q4 = 24 точки; budget 7 → step 4 квартала = 1 год
    const ticks = pickChartAxisTicks(points, 7, { cadence: 'quarterly' });
    expect(ticks[0]).toBe('2020-01-01');
    expect(ticks[ticks.length - 1]).toBe('2025-10-01');
    expect(ticks.length).toBeLessThanOrEqual(7);
    // промежутки в годах должны быть равны (по квартальному индексу)
    const toQ = (s) => {
      const d = new Date(s);
      return d.getUTCFullYear() * 4 + Math.floor(d.getUTCMonth() / 3);
    };
    const gaps = [];
    for (let i = 1; i < ticks.length - 1; i += 1) {
      gaps.push(toQ(ticks[i]) - toQ(ticks[i - 1]));
    }
    expect(new Set(gaps).size).toBe(1);
  });

  it('formatAxisTick digits=0 keeps integer trailing zeros', () => {
    expect(formatAxisTick(10000, 0)).toBe('10\u00A0000');
    expect(formatAxisTick(15000, 0)).toBe('15\u00A0000');
    expect(formatAxisTick(15000.0, 0)).toBe('15\u00A0000');
  });

  it('formatAxisTick still strips fractional trailing zeros', () => {
    expect(formatAxisTick(15.1, 2)).toBe('15,1');
    expect(formatAxisTick(15.0, 2)).toBe('15');
    expect(formatAxisTick(1500.5, 1)).toBe('1\u00A0500,5');
  });

  it('chartAxisTickBudget shrinks on narrow plot (мобилка)', () => {
    expect(chartAxisTickBudget(220, 8)).toBeLessThanOrEqual(4);
    expect(chartAxisTickBudget(700, 8)).toBe(7);
    expect(chartAxisTickBudget(0, 8)).toBe(7);
  });

  it('formatValue handles null', () => {
    expect(formatValue(null)).toBe('—');
  });

  it('formatChange adds sign (русская запятая — В-11)', () => {
    expect(formatChange(1.2)).toBe('+1,20');
    expect(formatChange(-0.5)).toBe('-0,50');
  });

  it('cn joins classes', () => {
    expect(cn('a', false, 'b', undefined)).toBe('a b');
  });
});

describe('formatValueWithUnit (русская типографика — В-11)', () => {
  it('formats percentage', () => {
    expect(formatValueWithUnit(15.3456, '%')).toBe('15,35%');
  });

  it('formats rubles', () => {
    expect(formatValueWithUnit(89.1234, 'руб.')).toBe('89,12 руб.');
  });

  it('formats mlrd rubles', () => {
    expect(formatValueWithUnit(17624.3, 'млрд руб.')).toBe('17\u00A0624,3 млрд ₽');
  });

  it('handles null', () => {
    expect(formatValueWithUnit(null, '%')).toBe('—');
  });

  it('handles unknown unit', () => {
    expect(formatValueWithUnit(42, 'шт.')).toBe('42,00 шт.');
  });
});

describe('unitSuffix', () => {
  it('returns % for percent', () => {
    expect(unitSuffix('%')).toBe('%');
  });
  it('returns руб. for rub', () => {
    expect(unitSuffix('руб.')).toBe('руб.');
  });
});

describe('unitDigits', () => {
  it('returns 2 for %', () => {
    expect(unitDigits('%')).toBe(2);
  });
  it('returns 1 for млрд руб.', () => {
    expect(unitDigits('млрд руб.')).toBe(1);
  });
});

describe('adjustCpiDisplay', () => {
  it('subtracts 100 when no code given (backward compat)', () => {
    expect(adjustCpiDisplay(102.5)).toBe(2.5);
  });
  it('subtracts 100 for CPI code', () => {
    expect(adjustCpiDisplay(102.5, 'cpi')).toBe(2.5);
  });
  it('subtracts 100 for quarterly CPI-derived code', () => {
    expect(adjustCpiDisplay(101.75, 'inflation-quarterly')).toBe(1.75);
    // Единый стандарт точности — два знака (созвон 2026-06-11).
    expect(adjustCpiDisplay(100.1451, 'inflation-weekly')).toBe(0.15);
    expect(adjustCpiDisplay(100.1525, 'inflation-weekly-food')).toBe(0.15);
  });
  it('subtracts 100 for CPI subcategory quarterly derived codes', () => {
    expect(adjustCpiDisplay(102.1, 'cpi-services-quarterly')).toBe(2.1);
  });
  it('returns value unchanged for non-CPI code', () => {
    expect(adjustCpiDisplay(102.5, 'gdp')).toBe(102.5);
  });
  it('handles null and non-finite', () => {
    expect(adjustCpiDisplay(null)).toBe(null);
    expect(adjustCpiDisplay(Infinity)).toBe(Infinity);
    expect(adjustCpiDisplay(NaN)).toBeNaN();
  });
});

describe('adjustCpiForecastDisplay', () => {
  it('normalizes CPI forecast values and bounds from index to display percent', () => {
    const response = {
      indicator: 'inflation-quarterly',
      forecast: {
        model_name: 'CPI-Quarterly-Agg',
        values: [
          {
            date: '2026-06-01',
            value: 101.42,
            lower_bound: 100.9,
            upper_bound: 101.9,
          },
        ],
      },
    };

    expect(adjustCpiForecastDisplay(response, 'inflation-quarterly')).toEqual({
      indicator: 'inflation-quarterly',
      forecast: {
        model_name: 'CPI-Quarterly-Agg',
        values: [
          {
            date: '2026-06-01',
            value: 1.42,
            lower_bound: 0.9,
            upper_bound: 1.9,
          },
        ],
      },
    });
  });

  it('does not clone non-CPI forecasts', () => {
    const response = { forecast: { values: [{ date: '2026-01-01', value: 101.42 }] } };
    expect(adjustCpiForecastDisplay(response, 'gdp-nominal')).toBe(response);
  });
});

describe('resolveDateFormat', () => {
  it('generic family: frequency drives format (chartMode=cpi)', () => {
    expect(resolveDateFormat({ chartMode: 'cpi', frequency: 'quarterly' })).toBe('quarterly');
    expect(resolveDateFormat({ chartMode: 'cpi', frequency: 'annual' })).toBe('annual');
    expect(resolveDateFormat({ chartMode: 'cpi', frequency: 'daily' })).toBe('day');
    expect(resolveDateFormat({ chartMode: 'cpi', frequency: 'monthly' })).toBe('full');
    expect(resolveDateFormat({ chartMode: 'cpi', frequency: 'weekly' })).toBe('weekly');
  });

  it('legacy CPI: mode drives granularity over frequency', () => {
    expect(resolveDateFormat({ chartMode: 'quarterly', frequency: 'monthly' })).toBe('quarterly');
    expect(resolveDateFormat({ chartMode: 'qoq', frequency: 'monthly' })).toBe('quarterly');
    expect(resolveDateFormat({ chartMode: 'annual', frequency: 'monthly' })).toBe('annual');
    expect(resolveDateFormat({ chartMode: 'yoy', frequency: 'monthly' })).toBe('full');
    expect(resolveDateFormat({ safeViewMode: 'index-quarterly', chartMode: 'index' })).toBe('quarterly');
    expect(resolveDateFormat({ safeViewMode: 'index-annual', chartMode: 'index' })).toBe('annual');
  });

  it('quarterly/annual frequency wins over yoy/period modes', () => {
    // Точка г/г на квартальном ряду датируется кварталом, а не месяцем.
    expect(resolveDateFormat({ chartMode: 'yoy', frequency: 'quarterly' })).toBe('quarterly');
    expect(resolveDateFormat({ chartMode: 'yoy', frequency: 'annual' })).toBe('annual');
    expect(resolveDateFormat({ chartMode: 'period-monthly', frequency: 'quarterly' })).toBe('quarterly');
  });

  it('weekly mode and weekly frequency use day-level labels', () => {
    expect(resolveDateFormat({ chartMode: 'weekly', frequency: 'monthly' })).toBe('weekly');
    expect(resolveDateFormat({ chartMode: 'cpi', frequency: 'weekly' })).toBe('weekly');
    expect(resolveDateFormat({ chartMode: 'period-weekly' })).toBe('weekly');
  });

  it('inflation mode never reads daily branch', () => {
    expect(resolveDateFormat({ chartMode: 'inflation', frequency: 'daily' })).toBe('full');
  });

  it('empty input defaults to full', () => {
    expect(resolveDateFormat()).toBe('full');
  });
});
