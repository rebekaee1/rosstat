import { describe, it, expect } from 'vitest';
import { mergeActualForecastChartSeries } from './chartForecastMerge';

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
      { date: '2026-04-01', actual: 6.4, forecast: 6.4 },
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
      { date: '2025-12-01', actual: 10330.1, forecast: 10330.1 },
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
    expect(merged[0]).toEqual({ date: '2026-04-01', actual: 6.4, forecast: 6.4 });
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
});
