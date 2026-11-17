import { describe, expect, it } from 'vitest';
import {
  FIELD, areaPath, cleanSeries, fieldBounds, formatMonth, formatPercent, linePath, nearestIndex, place, yearTicks,
} from './welcomeChart';

const monthly = (from, n, fn) => Array.from({ length: n }, (_, i) => {
  const d = new Date(Date.UTC(from, i, 1));
  return { date: d.toISOString().slice(0, 10), value: fn(i) };
});

describe('приветственный экран: настоящий ряд', () => {
  it('берёт только настоящие числа, по порядку, последние десять лет', () => {
    const rows = monthly(2010, 200, (i) => 5 + (i % 7) / 10);
    const payload = { data: [...rows.slice(100), { date: 'мусор', value: 3 }, { date: '2020-01-01', value: null }, ...rows.slice(0, 100)] };
    const s = cleanSeries(payload);
    expect(s.length).toBeGreaterThan(115);
    expect(s.length).toBeLessThanOrEqual(122);
    for (let i = 1; i < s.length; i += 1) expect(s[i].t).toBeGreaterThan(s[i - 1].t);
    expect(s.at(-1).date).toBe(rows.at(-1).date);
    expect(s.every((p) => Number.isFinite(p.value))).toBe(true);
  });

  it('короткий или пустой ответ — ряда нет (экран покажет текст без линии, числа не выдумывает)', () => {
    expect(cleanSeries(null)).toEqual([]);
    expect(cleanSeries({ data: [] })).toEqual([]);
    expect(cleanSeries({ data: monthly(2026, 5, () => 2) })).toEqual([]);
  });

  it('линия проходит ровно через точки ряда: первая слева, последняя у правого края, значения внутри поля', () => {
    const s = cleanSeries({ data: monthly(2016, 120, (i) => 2 + Math.sin(i / 9) * 2) });
    const b = fieldBounds(s);
    const first = place(s[0], b); const last = place(s.at(-1), b);
    expect(first.x).toBeCloseTo(0, 5);
    expect(last.x).toBeCloseTo(FIELD.w, 5);
    for (const p of s) {
      const { y } = place(p, b);
      expect(y).toBeGreaterThanOrEqual(FIELD.top);
      expect(y).toBeLessThanOrEqual(FIELD.h - FIELD.bottom);
    }
    const d = linePath(s, b);
    expect(d.startsWith('M0 ')).toBe(true);
    expect(d.match(/L/g)).toHaveLength(s.length - 1);
    expect(d).not.toMatch(/[CQ]/); // без сглаживания: только отрезки между настоящими точками
    expect(areaPath(s, b).endsWith('Z')).toBe(true);
  });

  it('два ряда делят одно поле: границы общие', () => {
    const a = cleanSeries({ data: monthly(2016, 120, () => 4) });
    const c = cleanSeries({ data: monthly(2016, 120, () => 7) });
    const b = fieldBounds(a, c);
    expect(place(c[0], b).y).toBeLessThan(place(a[0], b).y);
    expect(fieldBounds([], null)).toBeNull();
  });

  it('под пальцем — ближайший месяц; за краями поля — крайние точки', () => {
    const s = cleanSeries({ data: monthly(2016, 120, (i) => i) });
    const b = fieldBounds(s);
    expect(nearestIndex(s, b, 0)).toBe(0);
    expect(nearestIndex(s, b, 1)).toBe(s.length - 1);
    expect(nearestIndex(s, b, -3)).toBe(0);
    expect(nearestIndex(s, b, 9)).toBe(s.length - 1);
    const mid = nearestIndex(s, b, 0.5);
    expect(Math.abs(mid - (s.length - 1) / 2)).toBeLessThanOrEqual(1);
    expect(nearestIndex([], b, 0.5)).toBe(-1);
  });

  it('отметки лет: начало года, не больше шести, по возрастанию', () => {
    const s = cleanSeries({ data: monthly(2016, 129, () => 1) });
    const ticks = yearTicks(fieldBounds(s));
    expect(ticks.length).toBeGreaterThan(2);
    expect(ticks.length).toBeLessThanOrEqual(6);
    for (const tick of ticks) { expect(tick.fraction).toBeGreaterThan(0); expect(tick.fraction).toBeLessThan(1); }
    expect(ticks.map((x) => x.year)).toEqual([...ticks.map((x) => x.year)].sort((x, y) => x - y));
  });

  it('число и месяц пишутся по правилам языка', () => {
    expect(formatPercent(2.2, 'ru')).toBe('2,2\u00a0%');
    expect(formatPercent(4.1, 'en')).toBe('4.1%');
    expect(formatPercent(3, 'ru')).toBe('3,0\u00a0%');
    expect(formatMonth('2026-09-01', 'ru')).toBe('сентябрь 2026');
    expect(formatMonth('2026-10-01', 'en')).toBe('October 2026');
  });
});
