import { describe, expect, it } from 'vitest';
import { formatOfficialVintage } from './officialForecast';

describe('formatOfficialVintage', () => {
  it('форматирует дату выпуска на двух языках', () => {
    expect(formatOfficialVintage('2025-09-25', 'en')).toBe('25 September 2025');
    expect(formatOfficialVintage('2025-09-25', 'ru')).toMatch(/^25 сентября 2025/);
  });
  it('без даты не падает', () => {
    expect(formatOfficialVintage(null, 'ru')).toBe('последний выпуск');
    expect(formatOfficialVintage('мусор', 'en')).toBe('the latest release');
  });
});
