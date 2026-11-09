import { describe, expect, it } from 'vitest';
import { dateShortcuts, rateOnDate, ratesCsv } from './r5cExport';

const rows = [
  { date: '2026-10-29', value: 80 },
  { date: '2026-10-31', value: 81 },
  { date: '2026-11-07', value: 82 },
];

describe('rateOnDate', () => {
  it('берёт последний курс не позже дня', () => {
    expect(rateOnDate(rows, '2026-10-30').rate).toBe(80);
    expect(rateOnDate(rows, '2026-10-31').date).toBe('2026-10-31');
  });
  it('день раньше ряда: нет курса', () => {
    expect(rateOnDate(rows, '2026-10-01')).toBeNull();
  });
  it('учитывает номинал и обратный курс', () => {
    expect(rateOnDate(rows, '2026-11-07', { units: 100 }).rate).toBeCloseTo(0.82);
    expect(rateOnDate(rows, '2026-11-07', { invert: true }).rate).toBeCloseTo(1 / 82);
  });
});

describe('dateShortcuts', () => {
  it('конец прошлого месяца и первое число', () => {
    const [end, start, week] = dateShortcuts('2026-11-07');
    expect(end.iso).toBe('2026-10-31');
    expect(start.iso).toBe('2026-11-01');
    expect(week.iso).toBe('2026-10-31');
  });
});

describe('ratesCsv', () => {
  it('русский вид: точка с запятой и запятая в дроби, с BOM', () => {
    const csv = ratesCsv([{ name: 'Юань', code: 'CNY', nominal: 1, value: 12.27, date: '2026-11-07' }], 'ru');
    expect(csv.charCodeAt(0)).toBe(0xfeff);
    expect(csv).toContain('Юань;CNY;1;12,27;2026-11-07');
  });
});
