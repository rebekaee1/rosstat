import { describe, expect, it } from 'vitest';
import { separateVisibleTwins } from './searchExamples';

const t = (key) => ({
  'c9b.search.variant.month': 'к пред. месяцу',
  'c9b.search.variant.year': 'за год',
  'c9b.search.variant.index': 'индекс',
}[key] || key);
const base = { titleOf: () => 'Инфляция в Турции', detailOf: () => 'Турция — по месяцам', nameOf: (row) => row.name, t };

describe('separateVisibleTwins (круг 9, Q3)', () => {
  it('одинаково названные ряды получают различитель по смыслу сырого названия', () => {
    const rows = [
      { key: 'a', name: 'Индекс потребительских цен к предыдущему месяцу' },
      { key: 'b', name: 'Изменение цен за год' },
    ];
    const { rows: kept, variants } = separateVisibleTwins(rows, base);
    expect(kept).toHaveLength(2);
    expect(variants.get('a')).toBe('к пред. месяцу');
    expect(variants.get('b')).toBe('за год');
  });

  it('близнецы без различителя склеиваются: остаётся первый (самый релевантный)', () => {
    const rows = [{ key: 'a', name: 'Цены' }, { key: 'b', name: 'Цены (оценка)' }];
    const { rows: kept, variants } = separateVisibleTwins(rows, base);
    expect(kept.map((row) => row.key)).toEqual(['a']);
    expect(variants.size).toBe(0);
  });

  it('разные видимые названия не трогаются', () => {
    const rows = [{ key: 'a', name: 'ВВП' }, { key: 'b', name: 'Безработица' }];
    const { rows: kept } = separateVisibleTwins(rows, { ...base, titleOf: (row) => row.name });
    expect(kept).toHaveLength(2);
  });
});
