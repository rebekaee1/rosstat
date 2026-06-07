import { describe, it, expect } from 'vitest';
import { chartSeriesForViewMode } from './chartSeriesForViewMode';

describe('chartSeriesForViewMode', () => {
  const dataPoints = [{ date: '2024-12-01', value: 16 }];
  const quarterlyDataPoints = [{ date: '2024-12-31', value: 17 }];
  const annualDataPoints = [{ date: '2024-01-01', value: 8 }];
  const weeklyDataPoints = [{ date: '2024-01-07', value: 1 }];

  it('unemployment short-circuits to dataPoints even for quarterly chartMode', () => {
    // Безработица кладёт свой derived-ряд в dataPoints, но chartMode для
    // сглаживания может быть 'quarterly' — ряд всё равно берём из dataPoints.
    const series = chartSeriesForViewMode({
      chartMode: 'quarterly',
      isUnemploymentFamily: true,
      dataPoints,
      quarterlyDataPoints,
    });
    expect(series).toBe(dataPoints);
  });

  it('routes quarterly chartMode to quarterlyDataPoints (CPI/PPI/housing)', () => {
    const series = chartSeriesForViewMode({
      chartMode: 'quarterly',
      isUnemploymentFamily: false,
      dataPoints,
      quarterlyDataPoints,
    });
    expect(series).toBe(quarterlyDataPoints);
  });

  it('routes annual chartMode to annualDataPoints', () => {
    const series = chartSeriesForViewMode({
      chartMode: 'annual',
      dataPoints,
      annualDataPoints,
    });
    expect(series).toBe(annualDataPoints);
  });

  it('routes weekly chartMode to weeklyDataPoints', () => {
    const series = chartSeriesForViewMode({
      chartMode: 'weekly',
      dataPoints,
      weeklyDataPoints,
    });
    expect(series).toBe(weeklyDataPoints);
  });

  it('falls back to dataPoints for generic chartMode (cpi)', () => {
    // Config-движок рендерит generic-семьи с chartMode='cpi' → default-ветка.
    const series = chartSeriesForViewMode({
      chartMode: 'cpi',
      dataPoints,
    });
    expect(series).toBe(dataPoints);
  });
});
