import { describe, expect, it } from 'vitest';
import { rowUnit } from './rowUnit';
import { shortUnit } from './regionsApi';

describe('rowUnit — единица у числа в выдаче', () => {
  it('длинная единица получает короткую форму, а не пропадает (en)', () => {
    expect(rowUnit('thousand hectares', 'en')).toBe('thous. ha');
    expect(rowUnit('roubles per item', 'en')).toBe('₽ per item');
    expect(rowUnit('roubles per litre', 'en')).toBe('₽ per litre');
    expect(rowUnit('roubles per 10 tablets', 'en')).toBe('₽ per 10 tablets');
    expect(rowUnit('% of previous year', 'en')).toBe('%');  // общее правило процента — как раньше
    expect(rowUnit('thousand people', 'en')).toBe('thous. people');
  });

  it('то же по-русски', () => {
    expect(rowUnit('миллионов рублей', 'ru')).toBe('млн ₽');
    expect(rowUnit('рублей за поездку', 'ru')).toBe('₽ за поездку');
    expect(rowUnit('рублей за 10 таблеток', 'ru')).toBe('₽ за 10 таблеток');
    expect(rowUnit('% к предыдущему году', 'ru')).toBe('%');
  });

  it('короткие единицы — как раньше; слишком длинные по-прежнему без единицы у числа', () => {
    expect(rowUnit('тысяч гектаров', 'ru')).toBe('тысяч гектаров');
    expect(rowUnit('million rubles', 'en')).toBe('million rubles');
    expect(rowUnit('%', 'ru')).toBe('%');
    expect(rowUnit('случаев на 1000 человек населения', 'ru')).toBe('');
    expect(rowUnit('roubles per m² of floor area', 'en')).toBe('');
    expect(rowUnit('', 'en')).toBe('');
  });

  it('regionsApi по-прежнему отдаёт shortUnit (перенос без изменения поведения)', () => {
    expect(shortUnit('thousand hectares')).toBe('thous. ha');
  });
});
