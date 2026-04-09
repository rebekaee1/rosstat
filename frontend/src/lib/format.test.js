import { describe, it, expect } from 'vitest';
import { formatDate, formatValue, formatChange, formatValueWithUnit, unitSuffix, unitDigits, cn, adjustCpiDisplay } from './format';

describe('format', () => {
  it('formatDate full month in Russian', () => {
    expect(formatDate('2024-01-15', 'full')).toContain('2024');
    expect(formatDate('2024-01-15', 'full')).toContain('январ');
  });

  it('formatDate day format includes day number in genitive', () => {
    expect(formatDate('2024-01-15', 'day')).toBe('15 января 2024');
    expect(formatDate('2024-02-03', 'day')).toBe('3 февраля 2024');
  });

  it('formatDate annual returns year only', () => {
    expect(formatDate('2024-06-15', 'annual')).toBe('2024');
  });

  it('formatDate quarterly returns quarter and year', () => {
    expect(formatDate('2024-01-15', 'quarterly')).toBe('1 кв. 2024');
    expect(formatDate('2024-04-15', 'quarterly')).toBe('2 кв. 2024');
    expect(formatDate('2024-07-15', 'quarterly')).toBe('3 кв. 2024');
    expect(formatDate('2024-10-15', 'quarterly')).toBe('4 кв. 2024');
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
    expect(formatValueWithUnit(17624.3, 'млрд руб.')).toBe('17\u00A0624.3 млрд ₽');
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

describe('adjustCpiDisplay', () => {
  it('subtracts 100 when no code given (backward compat)', () => {
    expect(adjustCpiDisplay(102.5)).toBe(2.5);
  });
  it('subtracts 100 for CPI code', () => {
    expect(adjustCpiDisplay(102.5, 'cpi')).toBe(2.5);
  });
  it('returns value unchanged for non-CPI code', () => {
    expect(adjustCpiDisplay(102.5, 'gdp')).toBe(102.5);
  });
  it('handles null and non-finite', () => {
    expect(adjustCpiDisplay(null)).toBe(null);
    expect(adjustCpiDisplay(Infinity)).toBe(Infinity);
    expect(adjustCpiDisplay(NaN)).toBeNaN();
  });
});
