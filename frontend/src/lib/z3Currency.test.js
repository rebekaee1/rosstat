// Z3 (круг 08.11): мелкие валюты по-человечески: номинал, пресеты суммы, слова, поиск по стране.
import { describe, it, expect } from 'vitest';
import {
  amountPresets, buildEdges, currencySearchText, describeRate, formatConverted, nominalFor, unitWord,
} from './currencyRates';

const ITEMS = [
  { code: 'usd-rub', current_value: 80, unit: 'руб.', current_date: '2026-11-07' },
  { code: 'uzs-rub', current_value: 68.6, unit: 'руб. за 10 000', current_date: '2026-11-07' },
  { code: 'kzt-rub', current_value: 16.4, unit: 'руб. за 100', current_date: '2026-11-07' },
];
const edges = buildEdges(ITEMS);

describe('Z3: валюты по-человечески', () => {
  it('номинал: мелкая валюта за 10 000 / 100, привычные за 1', () => {
    expect(nominalFor('UZS', 0.00686)).toBe(10000);
    expect(nominalFor('KZT', 0.164)).toBe(100);
    expect(nominalFor('USD', 0.0125)).toBe(1);
    expect(nominalFor('TRY', 2.1)).toBe(1);
  });

  it('строки курса: сум «10 000 сумов = 68,60 ₽» и «1 ₽ = …»; привычная пара как раньше', () => {
    const uzs = describeRate('UZS', 'RUB', edges, 'ru');
    expect(uzs.lines[0]).toBe('10\u00a0000\u00a0сумов = 68,60\u00a0₽');
    expect(uzs.lines[1]).toMatch(/^1\u00a0₽ = 145,\d\d\u00a0сума$/);
    expect(describeRate('USD', 'RUB', edges, 'ru').lines).toEqual(['1 USD = 80,00 RUB']);
  });

  it('пресеты суммы подбираются под валюту', () => {
    expect(amountPresets('UZS', edges)).toEqual({ list: [100000, 1000000, 10000000], initial: 1000000 });
    expect(amountPresets('USD', edges).list).toEqual([1, 100, 1000, 10000]);
  });

  it('склонение и округление до копеек', () => {
    expect(unitWord(1, 'UZS')).toBe('сум');
    expect(unitWord(2, 'UZS')).toBe('сума');
    expect(unitWord(10000, 'UZS')).toBe('сумов');
    expect(unitWord(11, 'AMD')).toBe('драмов');
    expect(formatConverted(0.686004, 'ru', { money: true })).toBe('0,69');
    expect(formatConverted(0.00123456, 'en')).toBe('0.00123456');
  });

  it('поиск находит валюту по стране и латинице', () => {
    expect(currencySearchText('UZS')).toContain('узбекистан');
    expect(currencySearchText('UZS')).toContain('uzbek');
    expect(currencySearchText('AED')).toContain('dirham');
    expect(currencySearchText('AED')).toContain('дубай');
  });
});
