import { describe, expect, it } from 'vitest';
import { buildEdges, convert, quoteUnitsOf } from './currencyRates';

describe('курсы мелких валют за 100 / 10 000 единиц (ЦБ, 08.11.2026)', () => {
  it('читает единицу ряда', () => {
    expect(quoteUnitsOf('руб.')).toBe(1);
    expect(quoteUnitsOf('руб. за 100')).toBe(100);
    expect(quoteUnitsOf('руб. за 10 000')).toBe(10000);
    expect(quoteUnitsOf('руб. за 1 000 000')).toBe(1000000);
  });

  it('конвертер считает за одну единицу', () => {
    const edges = buildEdges([
      { code: 'uzs-rub', current_value: 68.6, unit: 'руб. за 10 000' },
      { code: 'usd-rub', current_value: 82, unit: 'руб.' },
    ]);
    expect(edges.find((e) => e.code === 'uzs-rub').rate).toBeCloseTo(0.00686, 6);
    expect(convert(10000, 'UZS', 'RUB', edges).value).toBeCloseTo(68.6, 6);
  });
});
