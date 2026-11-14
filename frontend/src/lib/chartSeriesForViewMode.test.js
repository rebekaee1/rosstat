import { describe, it, expect } from 'vitest';
import { chartSeriesForViewMode, heroDeltaSuffixKey } from './chartSeriesForViewMode';
import ru from '../i18n/messages.ru';
import en from '../i18n/messages.en';

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

describe('heroDeltaSuffixKey — подпись изменения в шапке', () => {
  it('недельный ИПЦ на месячном cpi: «к прошлой неделе», не «к прошлому месяцу» (рассылка 14.11.2026)', () => {
    const key = heroDeltaSuffixKey({ chartMode: 'weekly', frequency: 'monthly' });
    expect(ru[key]).toBe('к прошлой неделе');
    expect(en[key]).toBe('vs previous week');
  });

  it('рост за период по неделям сравнивается с прошлым отчётом', () => {
    expect(heroDeltaSuffixKey({ chartMode: 'period-weekly', frequency: 'monthly' })).toBe('w3.tele.delta.prevReport');
  });

  it('прежние режимы не меняются', () => {
    expect(heroDeltaSuffixKey({ chartMode: 'cpi', frequency: 'monthly' })).toBe('w3.tele.delta.prevMonth');
    expect(heroDeltaSuffixKey({ chartMode: 'qoq', frequency: 'monthly' })).toBe('w3.tele.delta.prevQuarter');
    expect(heroDeltaSuffixKey({ chartMode: 'annual', frequency: 'monthly' })).toBe('w3.tele.delta.prevYear');
    expect(heroDeltaSuffixKey({ chartMode: 'cpi', frequency: 'daily', dailyFromRawSeries: true })).toBe('c12u.delta.prevDay');
    expect(heroDeltaSuffixKey({ chartMode: 'cpi', frequency: 'daily' })).toBe('w3.tele.delta.prevValue');
  });
});
