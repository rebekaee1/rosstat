import { describe, expect, it } from 'vitest';
import { calculatorAliasTarget } from './calculatorAlias';

describe('угаданные адреса калькуляторов', () => {
  it('ипотека и вклад ведут на свои калькуляторы, остальное на общий', () => {
    expect(calculatorAliasTarget('mortgage')).toBe('/calculator/mortgage');
    expect(calculatorAliasTarget('Ipoteka/extra')).toBe('/calculator/mortgage');
    expect(calculatorAliasTarget('deposit')).toBe('/calculator/compound');
    expect(calculatorAliasTarget('inflation')).toBe('/calculator');
    expect(calculatorAliasTarget('')).toBe('/calculator');
    expect(calculatorAliasTarget(undefined)).toBe('/calculator');
  });
});
