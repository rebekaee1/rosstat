import { describe, it, expect } from 'vitest';
import { plural, years } from './calcFormat';

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
