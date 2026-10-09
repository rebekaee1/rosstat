import { describe, expect, it } from 'vitest';
import { CHART_EVENTS, eventsInWindow, labelledMarks, medianStepDays } from './chartEvents';

const monthly = (from, to) => {
  const out = [];
  for (let y = from; y <= to; y += 1) for (let m = 1; m <= 12; m += 1) out.push(`${y}-${String(m).padStart(2, '0')}-01`);
  return out;
};
const yearly = (from, to) => Array.from({ length: to - from + 1 }, (_, i) => `${from + i}-01-01`);

describe('chartEvents', () => {
  it('в справочнике около двенадцати событий без дублей, по времени', () => {
    expect(CHART_EVENTS.length).toBeGreaterThanOrEqual(10);
    expect(CHART_EVENTS.length).toBeLessThanOrEqual(14);
    expect(new Set(CHART_EVENTS.map((e) => e.id)).size).toBe(CHART_EVENTS.length);
    const dates = CHART_EVENTS.map((e) => e.date);
    expect([...dates].sort()).toEqual(dates);
  });

  it('медианный шаг: месяц, год', () => {
    expect(medianStepDays(monthly(2000, 2001))).toBeGreaterThanOrEqual(28);
    expect(medianStepDays(yearly(2000, 2010))).toBeGreaterThanOrEqual(365);
  });

  it('месячный ряд: событие стоит на своём месяце', () => {
    const marks = eventsInWindow(monthly(2005, 2012));
    const crisis = marks.find((m) => m.id === 'crisis2008');
    expect(crisis.at).toBe('2008-09-01');
  });

  it('годовой ряд: событие сентября 2008 ставится на 2008, а не на 2009', () => {
    const marks = eventsInWindow(yearly(2000, 2024));
    expect(marks.find((m) => m.id === 'crisis2008').at).toBe('2008-01-01');
    expect(marks.find((m) => m.id === 'covid2020').at).toBe('2020-01-01');
  });

  it('события вне окна и в будущем в список не попадают', () => {
    const marks = eventsInWindow(monthly(2015, 2019));
    expect(marks.map((m) => m.id)).toEqual(['brexit2016']);
    expect(eventsInWindow([])).toEqual([]);
    expect(eventsInWindow(['2020-01-01'])).toEqual([]);
  });

  it('подписи года не слипаются', () => {
    const dates = monthly(2019, 2023);
    const marks = eventsInWindow(dates);
    const shown = labelledMarks(marks, dates, 300);
    expect(shown.has('sanctions2022')).toBe(true);
    expect(shown.has('rates2022')).toBe(false);
    expect(labelledMarks(marks, dates, 0).size).toBe(0);
  });
});
