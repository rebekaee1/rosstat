// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import {
  currentJumpValue, emitPeriodPick, nearestRow, onPeriodPick, periodJumpOptions,
} from './periodJump';

const desc = (dates) => dates.map((date, i) => ({ date, value: i }));

describe('periodJump', () => {
  it('по годам: год ведёт на страницу, где он начинается в текущем порядке', () => {
    const rows = desc(['2025-03-01', '2025-01-01', '2024-12-01', '2024-06-01', '2023-12-01']);
    const jump = periodJumpOptions(rows, 2);
    expect(jump.kind).toBe('year');
    expect(jump.options).toEqual([
      { value: '2025', label: '2025', page: 0 },
      { value: '2024', label: '2024', page: 1 },
      { value: '2023', label: '2023', page: 2 },
    ]);
    expect(currentJumpValue(jump, rows, 1, 2)).toBe('2024');
  });

  it('годовой ряд и ряд внутри одного года — отрезки страниц', () => {
    const annual = desc(['2025-01-01', '2024-01-01', '2023-01-01']);
    const a = periodJumpOptions(annual, 2, { yearMode: true });
    expect(a.kind).toBe('page');
    expect(a.options.map((o) => o.label)).toEqual(['2025–2024', '2023–2023']);
    const oneYear = desc(['2025-03-03', '2025-03-02', '2025-03-01']);
    const b = periodJumpOptions(oneYear, 2, { pageLabel: (x, y) => `${x}/${y}` });
    expect(b.kind).toBe('page');
    expect(b.options[1]).toEqual({ value: '1', label: '2025-03-01/2025-03-01', page: 1 });
  });

  it('одна страница — переходов нет', () => {
    expect(periodJumpOptions(desc(['2025-01-01', '2024-01-01']), 20).options).toEqual([]);
  });

  it('ближайшая строка: точная дата, иначе соседняя в сторону листания', () => {
    const rows = desc(['2025-03-01', '2025-02-01', '2025-01-01']);
    expect(nearestRow(rows, '2025-02-01')).toEqual({ index: 1, date: '2025-02-01' });
    expect(nearestRow(rows, '2025-02-15')).toEqual({ index: 1, date: '2025-02-01' });
    expect(nearestRow(rows, '2020-01-01')).toEqual({ index: 2, date: '2025-01-01' });
    const asc = [...rows].reverse();
    expect(nearestRow(asc, '2025-02-15', { asc: true })).toEqual({ index: 2, date: '2025-03-01' });
    expect(nearestRow([], '2025-01-01')).toBeNull();
  });

  it('выбор на графике доходит до подписчика и отписывается', () => {
    const handler = vi.fn();
    const off = onPeriodPick(handler);
    emitPeriodPick('2024-05-01T00:00:00');
    expect(handler).toHaveBeenCalledWith({ date: '2024-05-01', source: 'chart' });
    off();
    emitPeriodPick('2024-06-01');
    expect(handler).toHaveBeenCalledTimes(1);
  });
});
