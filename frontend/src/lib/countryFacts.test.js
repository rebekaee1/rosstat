import { describe, expect, it } from 'vitest';
import {
  billionsOf,
  buildCountryFacts,
  formatEconomySize,
  formatPercentValue,
  sparkValuesForCountry,
} from './countryFacts';
import { countryReference } from './countryReference';
import { historyYears } from './homeStats';

describe('formatEconomySize', () => {
  it('крупные суммы в триллионах, средние в миллиардах', () => {
    expect(formatEconomySize(30800, 'ru').replace(/\u00a0/g, ' ')).toBe('30,8 трлн $');
    expect(formatEconomySize(3456, 'ru').replace(/\u00a0/g, ' ')).toBe('3,5 трлн $');
    expect(formatEconomySize(820, 'ru').replace(/\u00a0/g, ' ')).toBe('820 млрд $');
    expect(formatEconomySize(0.45, 'ru').replace(/\u00a0/g, ' ')).toBe('450 млн $');
  });

  it('EN: знак доллара перед числом', () => {
    expect(formatEconomySize(3456, 'en')).toBe('$3.5 trillion');
    expect(formatEconomySize(820, 'en')).toBe('$820 billion');
  });

  it('нет значения или не положительное: пустая строка', () => {
    expect(formatEconomySize(null)).toBe('');
    expect(formatEconomySize(0)).toBe('');
    expect(formatEconomySize('abc')).toBe('');
  });
});

describe('formatPercentValue', () => {
  it('один знак после запятой и неразрывный пробел по-русски', () => {
    expect(formatPercentValue(4, 'ru')).toBe('4,0\u00a0%');
    expect(formatPercentValue(2.34, 'en')).toBe('2.3%');
    expect(formatPercentValue(undefined)).toBe('');
  });
});

describe('billionsOf', () => {
  it('приводит единицу к миллиардам', () => {
    expect(billionsOf(3, 'трлн $')).toBe(3000);
    expect(billionsOf(500, 'млн $')).toBe(0.5);
    expect(billionsOf(820, 'млрд $')).toBe(820);
  });
});

describe('sparkValuesForCountry / buildCountryFacts', () => {
  const gdpSeries = {
    values_by_year: {
      2022: { DE: { value: 4 }, FR: { value: 3 } },
      2023: { DE: { value: 4.2 } },
      2024: { DE: { value: 4.5 }, FR: { value: 3.1 } },
    },
  };

  it('значения страны по годам, по возрастанию года, не больше лимита', () => {
    expect(sparkValuesForCountry(gdpSeries, 'DE')).toEqual([4, 4.2, 4.5]);
    expect(sparkValuesForCountry(gdpSeries, 'DE', 2)).toEqual([4.2, 4.5]);
    expect(sparkValuesForCountry(gdpSeries, 'ZZ')).toEqual([]);
    expect(sparkValuesForCountry(null, 'DE')).toEqual([]);
  });

  it('собирает факты по коду страны; нет источника: нет поля', () => {
    const facts = buildCountryFacts({
      gdp: { items: [{ country_code: 'DE', value: 4500, unit: 'млрд $' }] },
      inflation: { items: [{ country_code: 'DE', value: 2.3 }] },
      unemployment: { items: [{ country_code: 'FR', value: 7.1 }] },
      gdpSeries,
    });
    expect(facts.get('DE')).toMatchObject({ economyBn: 4500, inflation: 2.3, unemployment: null });
    expect(facts.get('DE').spark).toEqual([4, 4.2, 4.5]);
    expect(facts.get('FR')).toMatchObject({ economyBn: null, unemployment: 7.1 });
    expect(buildCountryFacts().size).toBe(0);
  });
});

describe('countryReference', () => {
  it('столица и валюта на языке страницы; неизвестная страна: null', () => {
    expect(countryReference('DE', 'ru')).toEqual({ capital: 'Берлин', currency: 'Евро' });
    expect(countryReference('us', 'en')).toEqual({ capital: 'Washington, D.C.', currency: 'US dollar' });
    expect(countryReference('ZZ')).toBeNull();
  });
});

describe('historyYears', () => {
  it('сколько лет охватывает история', () => {
    expect(historyYears(1897, new Date('2026-10-05'))).toBe(129);
    expect(historyYears(null)).toBeNull();
    expect(historyYears(2100, new Date('2026-10-05'))).toBeNull();
  });
});
