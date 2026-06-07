import { describe, it, expect } from 'vitest';
import { mergeActualForecastChartSeries } from './chartForecastMerge';

describe('mergeActualForecastChartSeries', () => {
  it('заменяет partial actual на прогноз при совпадении даты якоря', () => {
    const points = [
      { date: '2025-12-01', value: 10330.1 },
      { date: '2026-03-01', value: 4767.4 },
    ];
    const forecast = [
      { date: '2026-03-01', value: 9878.92 },
      { date: '2026-06-01', value: 7747.03 },
    ];

    const merged = mergeActualForecastChartSeries(points, forecast);

    expect(merged).toEqual([
      { date: '2025-12-01', actual: 10330.1, forecast: 10330.1 },
      { date: '2026-03-01', forecast: 9878.92 },
      { date: '2026-06-01', forecast: 7747.03 },
    ]);
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
