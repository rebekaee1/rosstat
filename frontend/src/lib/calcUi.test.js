import { describe, expect, it } from 'vitest';
import { MONEY_MAX, parseMoneyInput, revealStyle } from './calcUi';

describe('parseMoneyInput', () => {
  it('parses digits with spaces and non-breaking spaces', () => {
    expect(parseMoneyInput('100 000')).toEqual({ value: 100000, error: null });
    expect(parseMoneyInput('1 234 567')).toEqual({ value: 1234567, error: null });
  });

  it('rounds kopecks and understands dot or comma as the decimal separator', () => {
    expect(parseMoneyInput('100,6').value).toBe(101);
    expect(parseMoneyInput('100.4').value).toBe(100);
  });

  it('treats a dot or comma followed by exactly three digits as a thousands separator', () => {
    expect(parseMoneyInput('1.234.567').value).toBe(1234567);
    expect(parseMoneyInput('100,000').value).toBe(100000);
  });

  it('flags letters and symbols instead of silently dropping them', () => {
    expect(parseMoneyInput('12ab')).toEqual({ value: null, error: 'chars' });
    expect(parseMoneyInput('--')).toEqual({ value: null, error: 'chars' });
    expect(parseMoneyInput('1,2,3,4')).toEqual({ value: null, error: 'chars' });
  });

  it('flags empty and zero amounts unless zero is allowed', () => {
    expect(parseMoneyInput('')).toEqual({ value: null, error: 'empty' });
    expect(parseMoneyInput('0')).toEqual({ value: null, error: 'empty' });
    expect(parseMoneyInput('', { allowZero: true })).toEqual({ value: 0, error: null });
    expect(parseMoneyInput('0', { allowZero: true })).toEqual({ value: 0, error: null });
  });

  it('flags amounts above the limit', () => {
    expect(parseMoneyInput(String(MONEY_MAX + 1))).toEqual({ value: null, error: 'max' });
    expect(parseMoneyInput(String(MONEY_MAX)).error).toBeNull();
  });
});

describe('revealStyle', () => {
  it('keeps the total start delay within 0.2 s', () => {
    expect(revealStyle(0)['--fe-delay']).toBe('0.00s');
    expect(revealStyle(3)['--fe-delay']).toBe('0.09s');
    expect(parseFloat(revealStyle(50)['--fe-delay'])).toBeLessThanOrEqual(0.2);
  });
});
