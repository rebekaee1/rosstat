import { describe, it, expect } from 'vitest';
import { splitPriceUnit, signed, money, quoteLine } from './r9bPrice';

const t = (k, p) => `${k}|${Object.values(p).join('|')}`;

describe('r9bPrice', () => {
  it('разбирает единицу цены', () => {
    expect(splitPriceUnit('рублей за литр')).toEqual({ sign: '₽', per: 'за л' });
    expect(splitPriceUnit('')).toEqual({ sign: '', per: '' });
  });
  it('процент с одним знаком после запятой и настоящим минусом', () => {
    expect(signed(9.96, 'ru')).toContain('+10');
    expect(signed(-3.2, 'ru').startsWith('−')).toBe(true);
    expect(signed(0, 'ru').startsWith('+')).toBe(false);
  });
  it('цена с рублём', () => {
    expect(money(null, 'рублей за кг', 'ru')).toBe('');
    expect(money(100, 'рублей за кг', 'ru')).toContain('₽');
  });
  it('цитата содержит название и месяц', () => {
    const q = quoteLine({ name: 'Яйца', unit: 'рублей за 10 штук', value: 120, year_ago_value: 100, yoy_pct: 20, period_label: 'сентябрь 2026' }, t, 'ru');
    expect(q).toContain('Яйца');
    expect(q).toContain('сентябрь 2026');
  });
});
