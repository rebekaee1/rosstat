import { describe, expect, it } from 'vitest';
import { citeText, citeUrl, formatAccessDate } from './citeLine';

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

  it('название с точкой на конце — без двух точек', () => {
    expect(citeText({ name: 'Индекс цен.', url: 'https://a/b', locale: 'ru' })).toBe('Forecast Economy. Индекс цен. https://a/b');
  });

  it('адрес без параметров', () => {
    expect(citeUrl({ origin: 'https://ru.forecasteconomy.com', pathname: '/russia/indicator/cpi' }))
      .toBe('https://ru.forecasteconomy.com/russia/indicator/cpi');
    expect(citeUrl(null)).toBe('');
  });

  it('период словами и дата обращения, а не код периода как дата (№2)', () => {
    expect(citeText({
      name: 'Выезд', source: 'Росстат', period: 'за II кв. 2026', accessDate: new Date(2026, 10, 20),
      url: 'https://x/y', locale: 'ru',
    })).toBe('Forecast Economy. Выезд: источник данных — Росстат, данные за II кв. 2026, дата обращения 20.11.2026. https://x/y');
    expect(citeText({
      name: 'Trips', source: 'Rosstat', period: 'for Q2 2026', accessDate: new Date(2026, 10, 20), asOf: '2026-06-01',
      url: 'https://x/y', locale: 'en',
    })).toBe('Forecast Economy. Trips: data from Rosstat, data for Q2 2026, accessed 20.11.2026. https://x/y');
    expect(citeText({ name: 'X', period: 'за II кв. 2026', accessDate: new Date(2026, 10, 20), asOf: '2026-06-01', url: 'u', locale: 'ru' }))
      .not.toMatch(/1 июня/);
    expect(formatAccessDate(new Date(2026, 0, 5))).toBe('05.01.2026');
    expect(formatAccessDate('nope')).toBe('');
  });
});
