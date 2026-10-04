import { describe, expect, it } from 'vitest';
import { compactIndicatorCount, startYear } from './homeStats';

describe('compactIndicatorCount', () => {
  it('округляет вниз до тысяч и не завышает', () => {
    expect(compactIndicatorCount(268003)).toEqual({ value: 268, unit: 'thousand' });
    expect(compactIndicatorCount(268999)).toEqual({ value: 268, unit: 'thousand' });
  });

  it('малые числа показывает полностью, миллионы — в миллионах', () => {
    expect(compactIndicatorCount(5400)).toEqual({ value: 5400, unit: null });
    expect(compactIndicatorCount(2_400_000)).toEqual({ value: 2, unit: 'million' });
  });

  it('нет числа — нет подписи', () => {
    expect(compactIndicatorCount(undefined)).toBeNull();
    expect(compactIndicatorCount(0)).toBeNull();
    expect(compactIndicatorCount('abc')).toBeNull();
  });
});

describe('startYear', () => {
  it('берёт первый год периода', () => {
    expect(startYear('1897–2026')).toBe(1897);
    expect(startYear('—')).toBeNull();
  });
});
