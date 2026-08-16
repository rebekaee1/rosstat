import { describe, it, expect } from 'vitest';
import { plural, years, loanYearOrdinal } from './calcFormat';

describe('calcFormat — склонения', () => {
  it('годы склоняются по русским правилам, включая второй десяток', () => {
    expect(years(1)).toBe('1 год');
    expect(years(2)).toBe('2 года');
    expect(years(4)).toBe('4 года');
    expect(years(5)).toBe('5 лет');
    expect(years(11)).toBe('11 лет');
    expect(years(12)).toBe('12 лет');
    expect(years(14)).toBe('14 лет');
    expect(years(21)).toBe('21 год');
    expect(years(22)).toBe('22 года');
    expect(years(25)).toBe('25 лет');
    expect(years(31)).toBe('31 год');
    expect(years(40)).toBe('40 лет');
  });

  it('форма выбирается для любого существительного', () => {
    expect(plural(1, 'месяц', 'месяца', 'месяцев')).toBe('месяц');
    expect(plural(3, 'месяц', 'месяца', 'месяцев')).toBe('месяца');
    expect(plural(13, 'месяц', 'месяца', 'месяцев')).toBe('месяцев');
  });
});

describe('loanYearOrdinal', () => {
  it('русская форма с -й', () => {
    expect(loanYearOrdinal(1)).toBe('1-й');
    expect(loanYearOrdinal(3, 'ru')).toBe('3-й');
    expect(loanYearOrdinal(21)).toBe('21-й');
  });

  it('английские ordinal-суффиксы', () => {
    expect(loanYearOrdinal(1, 'en')).toBe('1st');
    expect(loanYearOrdinal(2, 'en')).toBe('2nd');
    expect(loanYearOrdinal(3, 'en')).toBe('3rd');
    expect(loanYearOrdinal(4, 'en')).toBe('4th');
    expect(loanYearOrdinal(11, 'en')).toBe('11th');
    expect(loanYearOrdinal(12, 'en')).toBe('12th');
    expect(loanYearOrdinal(13, 'en')).toBe('13th');
    expect(loanYearOrdinal(21, 'en')).toBe('21st');
    expect(loanYearOrdinal(22, 'en')).toBe('22nd');
    expect(loanYearOrdinal(23, 'en')).toBe('23rd');
  });
});
