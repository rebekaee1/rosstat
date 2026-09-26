import { describe, it, expect } from 'vitest';
import { buildForecastVisualSeries, mergeActualForecastChartSeries } from './chartForecastMerge';

describe('mergeActualForecastChartSeries', () => {
  it('сохраняет опубликованный II квартал фактом при совпадении с якорем прогноза', () => {
    const points = [
      { date: '2026-01-01', value: -3.93 },
      { date: '2026-04-01', value: 6.4 },
    ];
    const forecast = [
      { date: '2026-04-01', value: 6.4 },
      { date: '2026-07-01', value: 6.36 },
    ];

    expect(mergeActualForecastChartSeries(points, forecast)).toEqual([
      { date: '2026-01-01', actual: -3.93 },
      { date: '2026-04-01', actual: 6.4 },
      { date: '2026-07-01', forecast: 6.36 },
    ]);
  });

  it('заменяет partial actual на прогноз при совпадении даты якоря', () => {
    const points = [
      { date: '2025-12-01', value: 10330.1 },
      { date: '2026-03-01', value: 4767.4 },
    ];
    const forecast = [
      { date: '2026-03-01', value: 9878.92 },
      { date: '2026-06-01', value: 7747.03 },
    ];

    const merged = mergeActualForecastChartSeries(points, forecast, { replacePartialActual: true });

    expect(merged).toEqual([
      { date: '2025-12-01', actual: 10330.1 },
      { date: '2026-03-01', forecast: 9878.92 },
      { date: '2026-06-01', forecast: 7747.03 },
    ]);
  });

  it('не замещает полный факт даже при разрешённой корректировке partial bucket', () => {
    const merged = mergeActualForecastChartSeries(
      [{ date: '2026-04-01', value: 6.4 }],
      [{ date: '2026-04-01', value: 6.4 }, { date: '2026-07-01', value: 6.3 }],
      { replacePartialActual: true },
    );
    expect(merged[0]).toEqual({ date: '2026-04-01', actual: 6.4 });
  });

  it('без прогноза оставляет partial actual', () => {
    const points = [{ date: '2026-03-01', value: 4767.4 }];
    const merged = mergeActualForecastChartSeries(points, [], { showForecast: false });
    expect(merged).toEqual([{ date: '2026-03-01', actual: 4767.4 }]);
  });

  it('добавляет прогнозные даты без факта', () => {
    const points = [{ date: '2025-12-01', value: 100 }];
    const forecast = [{ date: '2026-03-01', value: 300 }];
    const merged = mergeActualForecastChartSeries(points, forecast);
    expect(merged[1]).toEqual({ date: '2026-03-01', forecast: 300 });
  });

  it('не выводит интервал прогноза на график (доверительные интервалы не показываем)', () => {
    const merged = mergeActualForecastChartSeries(
      [{ date: '2025-12-01', value: 100 }],
      [{ date: '2026-03-01', value: 105, lower_bound: 98, upper_bound: 112 }],
    );
    expect(merged[1]).toEqual({ date: '2026-03-01', forecast: 105 });
  });
});

describe('buildForecastVisualSeries', () => {
  it('connects forecast at the last fact without changing the exported series', () => {
    const rows = [
      { date: '2026-01-01', actual: 10.95 },
      { date: '2026-04-01', forecast: 10.62 },
      { date: '2026-07-01', forecast: 9.13 },
    ];

    const visual = buildForecastVisualSeries(rows);
    expect(visual.boundaryDate).toBe('2026-01-01');
    expect(visual.data[0]).toEqual({ date: '2026-01-01', actual: 10.95, forecast: 10.95 });
    expect(rows[0]).toEqual({ date: '2026-01-01', actual: 10.95 });
  });

  it('does not invent an anchor if the visible window contains only forecasts', () => {
    const rows = [{ date: '2026-04-01', forecast: 10.62 }];
    expect(buildForecastVisualSeries(rows)).toEqual({ data: rows, boundaryDate: '2026-04-01' });
  });
});
