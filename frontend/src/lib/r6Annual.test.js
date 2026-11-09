import { describe, it, expect } from 'vitest';
import { gapText, isYearsUnit } from './r6Annual';

describe('r6Annual gapText', () => {
  it('years: absolute difference with a proper word', () => {
    expect(gapText(70.94, 73.41, 'число лет', 'ru').text).toBe('−2,5 года');
    expect(gapText(70.94, 70.9, 'лет', 'ru').text).toBe('+0,04 года');
  });
  it('percent unit: points, not percent of percent', () => {
    expect(gapText(5.4, 5.0, '%', 'ru').text).toBe('+0,4 п.п.');
    expect(gapText(5.4, 5.0, '%', 'en').text).toBe('+0.4 p.p.');
  });
  it('levels: relative percent; unsigned for sentences', () => {
    expect(gapText(135, 100, 'рублей', 'ru').text).toBe('+35 %');
    expect(gapText(80, 100, 'рублей', 'ru', { signed: false }).text).toBe('20 %');
    expect(gapText(1, 0, 'рублей', 'ru')).toBeNull();
  });
  it('isYearsUnit', () => {
    expect(isYearsUnit('число лет')).toBe(true);
    expect(isYearsUnit('рублей')).toBe(false);
  });
});
