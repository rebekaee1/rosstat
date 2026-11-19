import { describe, expect, it } from 'vitest';
import { citeText, citeUrl } from './citeLine';

describe('citeText', () => {
  it('ru: название, источник, дата, адрес — как в SSR', () => {
    expect(citeText({
      name: 'Дизельное топливо', source: 'Росстат', asOf: '2026-11-09',
      url: 'https://ru.forecasteconomy.com/russia/indicator/fuel-diesel', locale: 'ru',
    })).toBe('Forecast Economy. Дизельное топливо: источник данных — Росстат, на 9 ноября 2026. https://ru.forecasteconomy.com/russia/indicator/fuel-diesel');
  });

  it('en и без даты/источника', () => {
    expect(citeText({ name: 'Key rate', source: 'Bank of Russia', asOf: '2026-11-18', url: 'https://forecasteconomy.com/x', locale: 'en' }))
      .toBe('Forecast Economy. Key rate: data from Bank of Russia, as of 18 November 2026. https://forecasteconomy.com/x');
    expect(citeText({ name: 'X', url: 'https://a/b', locale: 'ru' })).toBe('Forecast Economy. X. https://a/b');
  });

  it('адрес без параметров', () => {
    expect(citeUrl({ origin: 'https://ru.forecasteconomy.com', pathname: '/russia/indicator/cpi' }))
      .toBe('https://ru.forecasteconomy.com/russia/indicator/cpi');
    expect(citeUrl(null)).toBe('');
  });
});
