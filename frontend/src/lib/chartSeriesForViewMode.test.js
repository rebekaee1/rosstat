import { describe, it, expect } from 'vitest';
import { chartSeriesForViewMode } from './chartSeriesForViewMode';
import { applyAggregateTransform } from './viewModeFamilies';

describe('chartSeriesForViewMode', () => {
  const agg = applyAggregateTransform(
    [{ date: '2024-01-15', value: 16 }, { date: '2024-06-10', value: 18 }],
    'year',
  );
  const emptyWeekly = [];

  it('key-rate uses parent dataPoints for weekly chartMode', () => {
    const series = chartSeriesForViewMode({
      chartMode: 'weekly',
      isKeyRateFamily: true,
      isRuoniaFamily: false,
      isBtcUsdFamily: false,
      isBrentFamily: false,
      isUsdRubFamily: false,
      isEurRubFamily: false,
      isCnyRubFamily: false,
      dataPoints: agg,
      weeklyDataPoints: emptyWeekly,
    });
    expect(series).toBe(agg);
    expect(series.length).toBeGreaterThan(0);
  });

  it('ruonia uses parent dataPoints for quarterly chartMode', () => {
    const series = chartSeriesForViewMode({
      chartMode: 'quarterly',
      isKeyRateFamily: false,
      isRuoniaFamily: true,
      isBtcUsdFamily: false,
      isBrentFamily: false,
      isUsdRubFamily: false,
      isEurRubFamily: false,
      isCnyRubFamily: false,
      dataPoints: agg,
      quarterlyDataPoints: [],
    });
    expect(series).toBe(agg);
  });

  it('btc-usd uses parent dataPoints for monthly chartMode', () => {
    const series = chartSeriesForViewMode({
      chartMode: 'monthly',
      isKeyRateFamily: false,
      isRuoniaFamily: false,
      isBtcUsdFamily: true,
      isBrentFamily: false,
      isUsdRubFamily: false,
      isEurRubFamily: false,
      isCnyRubFamily: false,
      dataPoints: agg,
      periodMonthlyDataPoints: [],
    });
    expect(series).toBe(agg);
  });

  it('brent uses parent dataPoints for monthly chartMode', () => {
    const series = chartSeriesForViewMode({
      chartMode: 'monthly',
      isKeyRateFamily: false,
      isRuoniaFamily: false,
      isBtcUsdFamily: false,
      isBrentFamily: true,
      isUsdRubFamily: false,
      isEurRubFamily: false,
      isCnyRubFamily: false,
      dataPoints: agg,
      periodMonthlyDataPoints: [],
    });
    expect(series).toBe(agg);
  });

  it('usd-rub uses parent dataPoints for monthly chartMode', () => {
    const series = chartSeriesForViewMode({
      chartMode: 'monthly',
      isKeyRateFamily: false,
      isRuoniaFamily: false,
      isBtcUsdFamily: false,
      isBrentFamily: false,
      isUsdRubFamily: true,
      isEurRubFamily: false,
      isCnyRubFamily: false,
      dataPoints: agg,
      periodMonthlyDataPoints: [],
    });
    expect(series).toBe(agg);
  });

  it('eur-rub uses parent dataPoints for monthly chartMode', () => {
    const series = chartSeriesForViewMode({
      chartMode: 'monthly',
      isKeyRateFamily: false,
      isRuoniaFamily: false,
      isBtcUsdFamily: false,
      isBrentFamily: false,
      isUsdRubFamily: false,
      isEurRubFamily: true,
      isCnyRubFamily: false,
      dataPoints: agg,
      periodMonthlyDataPoints: [],
    });
    expect(series).toBe(agg);
  });

  it('cny-rub uses parent dataPoints for monthly chartMode', () => {
    const series = chartSeriesForViewMode({
      chartMode: 'monthly',
      isKeyRateFamily: false,
      isRuoniaFamily: false,
      isBtcUsdFamily: false,
      isBrentFamily: false,
      isUsdRubFamily: false,
      isEurRubFamily: false,
      isCnyRubFamily: true,
      dataPoints: agg,
      periodMonthlyDataPoints: [],
    });
    expect(series).toBe(agg);
  });

  it('non-key-rate weekly still uses weeklyDataPoints', () => {
    const weekly = [{ date: '2024-01-07', value: 1 }];
    const series = chartSeriesForViewMode({
      chartMode: 'weekly',
      isKeyRateFamily: false,
      isRuoniaFamily: false,
      isBtcUsdFamily: false,
      isBrentFamily: false,
      isUsdRubFamily: false,
      isEurRubFamily: false,
      isCnyRubFamily: false,
      dataPoints: agg,
      weeklyDataPoints: weekly,
    });
    expect(series).toBe(weekly);
  });
});
