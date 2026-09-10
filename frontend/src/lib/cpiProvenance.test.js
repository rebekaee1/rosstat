import { describe, it, expect } from 'vitest';
import { cpiProvenance } from './cpiProvenance';
import { compareDifferenceUnit, compareLegendParts } from './compareRepresentation';
import { formatValueWithUnit } from './format';

describe('annual CPI provenance and absolute differences', () => {
  it('distinguishes reconstructed annual CPI from native monthly and unrelated prices', () => {
    expect(cpiProvenance('cpi', 'inflation')).toContain('округления');
    expect(cpiProvenance('cpi-food-yoy', null, 'en')).toContain('Calculated');
    expect(cpiProvenance('cpi', 'cpi')).toBeNull();
    expect(cpiProvenance('ppi', 'yoy')).toBeNull();
  });
  it('reports 14% minus 6.5% as 7.5 percentage points, not percent', () => {
    expect(formatValueWithUnit(14 - 6.5, compareDifferenceUnit('%'), 2, 'ru')).toBe('7,50 п.п.');
    expect(compareDifferenceUnit('%', { locale: 'en' })).toBe('p.p.');
    expect(compareDifferenceUnit('индекс')).toBe('п. индекса');
    expect(compareDifferenceUnit('руб.')).toBe('руб.');
    expect(compareDifferenceUnit('% ВВП')).toBe('п.п. ВВП');
    expect(compareDifferenceUnit('%', { indexed: true })).toBe('п. индекса');
  });
  it('does not emit an empty unit field in an index legend', () => {
    expect(compareLegendParts(['Индекс', '', 'Месяц', 'Левая ось'])).toBe('Индекс, Месяц, Левая ось');
    expect(compareLegendParts(['Индекс', ', старт = 100'])).toBe('Индекс, старт = 100');
  });
});
