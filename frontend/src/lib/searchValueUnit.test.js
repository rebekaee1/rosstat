import { describe, expect, it } from 'vitest';
import { regionRubleUnit } from './searchValueUnit';

describe('regionRubleUnit: множитель ряда не теряется', () => {
  it('«миллионов рублей с начала года» → «млн ₽»', () => {
    expect(regionRubleUnit('миллионов рублей с начала года')).toBe('млн\u00A0₽');
    expect(regionRubleUnit('млн руб.')).toBe('млн\u00A0₽');
    expect(regionRubleUnit('тыс. руб.')).toBe('тыс.\u00A0₽');
    expect(regionRubleUnit('млрд рублей')).toBe('млрд\u00A0₽');
  });

  it('обычные рубли — «₽»', () => {
    expect(regionRubleUnit('руб.')).toBe('₽');
    expect(regionRubleUnit('рублей за литр')).toBe('₽');
  });

  it('английские единицы', () => {
    expect(regionRubleUnit('RUB million, year to date', 'en')).toBe('mn\u00A0₽');
    expect(regionRubleUnit('RUB mn', 'en')).toBe('mn\u00A0₽');
    expect(regionRubleUnit('RUB', 'en')).toBe('₽');
  });

  it('не рубли — пустая строка', () => {
    expect(regionRubleUnit('%')).toBe('');
    expect(regionRubleUnit('тыс. человек')).toBe('');
    expect(regionRubleUnit('')).toBe('');
  });
});
