import { describe, expect, it } from 'vitest';
import { countryFlag, POPULAR_COUNTRY_SLUGS } from './countryFlag';

describe('countryFlag', () => {
  it('собирает флаг из двух букв независимо от регистра', () => {
    expect(countryFlag('DE')).toBe('\u{1F1E9}\u{1F1EA}');
    expect(countryFlag(' ru ')).toBe('\u{1F1F7}\u{1F1FA}');
  });

  it('не выдумывает флаг для не-ISO кодов', () => {
    expect(countryFlag('')).toBe('');
    expect(countryFlag('DEU')).toBe('');
    expect(countryFlag('1A')).toBe('');
    expect(countryFlag(null)).toBe('');
  });

  it('списки популярных стран без повторов', () => {
    for (const list of Object.values(POPULAR_COUNTRY_SLUGS)) {
      expect(new Set(list).size).toBe(list.length);
    }
  });
});
