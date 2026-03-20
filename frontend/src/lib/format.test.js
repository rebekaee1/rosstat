import { describe, it, expect } from 'vitest';
import { formatDate, formatValue, formatChange, cn } from './format';

describe('format', () => {
  it('formatDate full month in Russian', () => {
    expect(formatDate('2024-01-15', 'full')).toContain('2024');
    expect(formatDate('2024-01-15', 'full')).toContain('январ');
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
