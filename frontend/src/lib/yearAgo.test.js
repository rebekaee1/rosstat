import { describe, expect, it } from 'vitest';
import { yearAgoRow } from './yearAgo';

const map = (dates) => new Map(dates.map((d) => [d, { value: 1, date: d }]));

describe('yearAgoRow', () => {
  it('квартал — тот же квартал прошлого года', () => {
    const m = map(['2024-07-01', '2025-07-01', '2025-10-01']);
    expect(yearAgoRow('2025-07-01', m)?.date).toBe('2024-07-01');
    expect(yearAgoRow('2025-10-01', m)).toBeNull();
  });
  it('годовой ряд — предыдущий год, пропуск года — null', () => {
    const m = map(['2014-01-01', '2015-01-01', '2019-01-01']);
    expect(yearAgoRow('2015-01-01', m, true)?.date).toBe('2014-01-01');
    expect(yearAgoRow('2019-01-01', m, true)).toBeNull();
  });
  it('конец месяца в високосный год находится в пределах трёх дней', () => {
    const m = map(['2024-02-29', '2025-02-28']);
    expect(yearAgoRow('2025-02-28', m)?.date).toBe('2024-02-29');
  });
});
