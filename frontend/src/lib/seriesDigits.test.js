import { describe, expect, it } from 'vitest';
import { valueDigitsFor, yAxisLabelWidth } from './seriesDigits';

describe('valueDigitsFor', () => {
  it('«тыс. поездок» с сотыми: от ста — без дроби (1 847,69 → 1 848)', () => {
    expect(valueDigitsFor('тыс. поездок', [1847.69, 2210.4, 1500.11])).toBe(0);
    expect(valueDigitsFor('тыс. поездок', [48.25, 52.1, 61.7])).toBe(1);
    expect(valueDigitsFor('тыс. поездок', [4.25, 5.1])).toBe(2);
  });
  it('целые числа в счётной единице — без «.00» (16,112.00)', () => {
    expect(valueDigitsFor('people', [16112, 582880])).toBe(0);
    expect(valueDigitsFor('чел.', [16112.5])).toBe(0);
  });
  it('единицы с настройкой сайта и обычные ряды не меняются', () => {
    expect(valueDigitsFor('%', [14, 16.5])).toBe(2);
    expect(valueDigitsFor('млрд руб.', [1500.123])).toBe(1);
    expect(valueDigitsFor('руб./л', [58.43, 60.1])).toBe(2);
    expect(valueDigitsFor('индекс', [101.2, 99.8])).toBe(2);
    expect(valueDigitsFor('$', [58.43])).toBe(2);
  });
});

describe('yAxisLabelWidth', () => {
  it('ширина по самой длинной подписи: «10 000» при нижней границе «−2» не обрезается', () => {
    expect(yAxisLabelWidth(['−2', '5 000', '10 000'])).toBeGreaterThan(yAxisLabelWidth(['−2']));
    expect(yAxisLabelWidth(['10 000'])).toBeGreaterThanOrEqual(6 * 7.5);
    expect(yAxisLabelWidth([])).toBe(40);
  });
});
