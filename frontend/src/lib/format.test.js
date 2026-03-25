import { describe, it, expect } from 'vitest';
import { formatDate, formatValue, formatChange, formatValueWithUnit, unitSuffix, unitDigits, cn } from './format';

describe('format', () => {
  it('formatDate full month in Russian', () => {
    expect(formatDate('2024-01-15', 'full')).toContain('2024');
    expect(formatDate('2024-01-15', 'full')).toContain('январ');
  });

  it('formatDate day format includes day number in genitive', () => {
    expect(formatDate('2024-01-15', 'day')).toBe('15 января 2024');
    expect(formatDate('2024-02-03', 'day')).toBe('3 февраля 2024');
  });

  it('formatValue handles null', () => {
    expect(formatValue(null)).toBe('—');
  });

  it('formatChange adds sign', () => {
    expect(formatChange(1.2)).toBe('+1.20');
    expect(formatChange(-0.5)).toBe('-0.50');
  });

  it('cn joins classes', () => {
    expect(cn('a', false, 'b', undefined)).toBe('a b');
  });
});

describe('formatValueWithUnit', () => {
  it('formats percentage', () => {
    expect(formatValueWithUnit(15.3456, '%')).toBe('15.35%');
  });

  it('formats rubles', () => {
    expect(formatValueWithUnit(89.1234, 'руб.')).toBe('89.12 руб.');
  });

  it('formats mlrd rubles', () => {
    expect(formatValueWithUnit(17624.3, 'млрд руб.')).toBe('17624.3 млрд ₽');
  });

  it('handles null', () => {
    expect(formatValueWithUnit(null, '%')).toBe('—');
  });

  it('handles unknown unit', () => {
    expect(formatValueWithUnit(42, 'шт.')).toBe('42.00 шт.');
  });
});

describe('unitSuffix', () => {
  it('returns % for percent', () => {
    expect(unitSuffix('%')).toBe('%');
  });
  it('returns руб. for rub', () => {
    expect(unitSuffix('руб.')).toBe('руб.');
  });
});

describe('unitDigits', () => {
  it('returns 2 for %', () => {
    expect(unitDigits('%')).toBe(2);
  });
  it('returns 1 for млрд руб.', () => {
    expect(unitDigits('млрд руб.')).toBe(1);
  });
});
