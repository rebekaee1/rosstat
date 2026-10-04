import { describe, expect, it } from 'vitest';
import { countryFlag, uniformDigits } from './countryFlag';

describe('countryFlag', () => {
  it('builds regional indicator pairs', () => {
    expect(countryFlag('DE')).toBe('\u{1F1E9}\u{1F1EA}');
    expect(countryFlag('de')).toBe(countryFlag('DE'));
  });

  it('maps catalogue aliases UK and EL', () => {
    expect(countryFlag('UK')).toBe(countryFlag('GB'));
    expect(countryFlag('EL')).toBe(countryFlag('GR'));
  });

  it('returns nothing for unknown input', () => {
    expect(countryFlag('')).toBe('');
    expect(countryFlag(null)).toBe('');
    expect(countryFlag('DEU')).toBe('');
    expect(countryFlag('1A')).toBe('');
  });
});

describe('uniformDigits', () => {
  it('keeps big money values whole and small rates precise', () => {
    expect(uniformDigits([30767, 5048.1, 4.2])).toBe(0);
    expect(uniformDigits([25.4, 3.2, 4])).toBe(1);
    expect(uniformDigits([2.92, 0.5, -1.1])).toBe(2);
  });

  it('ignores empty and non numeric entries', () => {
    expect(uniformDigits([null, '', 'x', 7])).toBe(1);
    expect(uniformDigits(undefined)).toBe(2);
  });
});
