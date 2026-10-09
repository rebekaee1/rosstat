import { describe, it, expect } from 'vitest';
import { formatRate, parseAmountInput } from './currencyRates';
import { alignIndex, axisPlan, changePct, cleanSeries, downsample, rateDigits, sliceByPeriod } from './currencyChart';

const daily = (from, n, f = (i) => 80 + i) => Array.from({ length: n }, (_, i) => ({
  date: new Date(Date.parse(`${from}T00:00:00Z`) + i * 86_400_000).toISOString().slice(0, 10),
  value: f(i),
}));

describe('sliceByPeriod', () => {
  const rows = daily('2025-01-01', 600);
  it('неделя, месяц и год считаются от последней точки', () => {
    expect(sliceByPeriod(rows, 'week').length).toBe(8);
    expect(sliceByPeriod(rows, 'month').length).toBe(32);
    expect(sliceByPeriod(rows, 'year').length).toBe(367);
  });
  it('всё время прореживается до разумного числа точек и оставляет последнюю', () => {
    const long = daily('1999-01-01', 9000);
    const all = sliceByPeriod(long, 'all');
    expect(all.length).toBeLessThanOrEqual(600);
    expect(all[all.length - 1].date).toBe(long[long.length - 1].date);
    expect(all[0].date).toBe(long[0].date);
  });
  it('редкий ряд за неделю даёт хотя бы две точки', () => {
    const rare = [{ date: '2026-01-01', value: 1 }, { date: '2026-03-01', value: 2 }];
    expect(sliceByPeriod(rare, 'week')).toHaveLength(2);
  });
});

describe('alignIndex', () => {
  it('обе пары стартуют со 100, вторая берёт последнее известное значение', () => {
    const a = [{ date: '2026-01-01', value: 10 }, { date: '2026-01-02', value: 11 }, { date: '2026-01-03', value: 12 }];
    const b = [{ date: '2025-12-31', value: 50 }, { date: '2026-01-03', value: 75 }];
    const out = alignIndex(a, b);
    out.map((p) => p.a).forEach((v, i) => expect(v).toBeCloseTo([100, 110, 120][i]));
    expect(out.map((p) => p.b)).toEqual([100, 100, 150]);
  });
  it('если общих дат нет, пусто', () => {
    expect(alignIndex([{ date: '2026-01-01', value: 1 }, { date: '2026-01-02', value: 1 }], [{ date: '2026-02-01', value: 1 }])).toEqual([]);
  });
});

describe('axisPlan', () => {
  it('за неделю подписи по дням без повторов, за год по месяцам, за много лет по годам', () => {
    const week = sliceByPeriod(daily('2026-09-01', 60), 'week');
    expect(axisPlan(week).kind).toBe('day');
    expect(new Set(axisPlan(week).ticks).size).toBe(axisPlan(week).ticks.length);
    expect(axisPlan(sliceByPeriod(daily('2025-01-01', 600), 'year')).kind).toBe('month');
    const all = sliceByPeriod(daily('2000-01-01', 9000), 'all');
    const plan = axisPlan(all);
    expect(plan.kind).toBe('year');
    expect(plan.ticks.length).toBeLessThanOrEqual(5);
    expect(axisPlan(all, true).ticks.length).toBeLessThanOrEqual(3);
  });
});

describe('мелочи', () => {
  it('rateDigits: тысячи без копеек, малые доли с точностью', () => {
    expect(rateDigits(85276)).toBe(0);
    expect(rateDigits(80.5)).toBe(2);
    expect(rateDigits(0.0117)).toBe(4);
    expect(rateDigits(0.000012)).toBe(6);
  });
  it('cleanSeries отбрасывает мусор и сортирует; changePct считает процент', () => {
    const s = cleanSeries([{ date: '2026-01-02', value: 12 }, { date: '2026-01-01', value: 10 }, { date: 'x', value: 5 }, { date: '2026-01-03', value: -1 }]);
    expect(s.map((p) => p.date)).toEqual(['2026-01-01', '2026-01-02']);
    expect(changePct(s)).toBeCloseTo(20);
    expect(downsample(daily('2020-01-01', 10), 600)).toHaveLength(10);
  });
});

describe('ввод суммы и курс в строке', () => {
  it('английская запятая отделяет тысячи, русская — дробь', () => {
    expect(parseAmountInput('10,000', 'en')).toBe(10000);
    expect(parseAmountInput('10 000', 'ru')).toBe(10000);
    expect(parseAmountInput('1,5', 'ru')).toBe(1.5);
    expect(parseAmountInput('1.5', 'en')).toBe(1.5);
  });
  it('курс: 80,00 · 0,0117 · 0,000012 вместо восьми знаков', () => {
    expect(formatRate(80, 'ru')).toBe('80,00');
    expect(formatRate(0.01169849, 'ru')).toBe('0,0117');
    expect(formatRate(0.00001234, 'en')).toBe('0.00001234');
    expect(formatRate(85276.4, 'ru').replace(/\s/g, ' ')).toBe('85 276');
  });
});
