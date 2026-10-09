import { describe, expect, it } from 'vitest';
import { buildCompareRows, COMPARE_MAX, toggleCompareSlug } from './regionCompareTable';

const heat = (code, unit, rows) => ({ indicator: { code, unit }, year: 2024, values: rows.map(([slug, value]) => ({ slug, value })) });

describe('buildCompareRows', () => {
  const metrics = [
    { code: 'wage', label: 'Зарплата' },
    { code: 'unemp', label: 'Безработица', betterIsLow: true },
    { code: 'pop', label: 'Население', neutral: true },
  ];
  const heats = [
    heat('wage', '₽', [['a', 100], ['b', 150], ['c', 90]]),
    heat('unemp', '%', [['a', 4], ['b', 2], ['c', 2]]),
    heat('pop', 'чел.', [['a', 10], ['b', 20]]),
  ];

  it('лучший в строке отмечен по смыслу показателя, у численности отметки нет, ничья без победителя', () => {
    const rows = buildCompareRows(metrics, heats, ['a', 'b']);
    expect(rows[0].leader).toBe('b');
    expect(rows[1].leader).toBe('b');
    expect(rows[2].leader).toBeNull();
    const tie = buildCompareRows(metrics, heats, ['b', 'c']);
    expect(tie[1].leader).toBeNull();
  });

  it('нет значения у региона — пусто, без выдумки; нет среза — все пусто', () => {
    const rows = buildCompareRows(metrics, heats, ['a', 'c']);
    expect(rows[2].cells).toEqual([{ slug: 'a', value: 10 }, { slug: 'c', value: null }]);
    expect(rows[2].leader).toBeNull();
    expect(buildCompareRows(metrics, [undefined, undefined, undefined], ['a', 'b'])[0].cells.every((c) => c.value === null)).toBe(true);
    expect(rows[0].unit).toBe('₽');
  });
});

describe('toggleCompareSlug', () => {
  it('добавляет, убирает и не выходит за предел', () => {
    expect(toggleCompareSlug([], 'a')).toEqual(['a']);
    expect(toggleCompareSlug(['a', 'b'], 'a')).toEqual(['b']);
    const full = ['a', 'b', 'c', 'd', 'e'];
    expect(COMPARE_MAX).toBe(5);
    expect(toggleCompareSlug(full, 'f')).toBe(full);
  });
});
