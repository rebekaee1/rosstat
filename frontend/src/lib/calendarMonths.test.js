import { describe, it, expect } from 'vitest';
import { calendarMonthParams, eventsInRange, monthRange, shiftMonth, WORLD_SOURCES } from './calendarMonths';

describe('calendarMonths', () => {
  it('monthRange: первый и последний день, февраль високосного года', () => {
    expect(monthRange(2028, 1)).toEqual({ from: '2028-02-01', to: '2028-02-29' });
    expect(monthRange(2026, 10)).toEqual({ from: '2026-11-01', to: '2026-11-30' });
  });

  it('shiftMonth переходит через границу года в обе стороны и на много месяцев', () => {
    expect(shiftMonth(2026, 0, -1)).toEqual({ year: 2025, month: 11 });
    expect(shiftMonth(2026, 11, 1)).toEqual({ year: 2027, month: 0 });
    expect(shiftMonth(2026, 10, -21)).toEqual({ year: 2025, month: 1 });
  });

  it('calendarMonthParams: «мир» раскрывается в мировые источники, «все» — без source', () => {
    expect(calendarMonthParams(2026, 10, 'world').source).toBe(WORLD_SOURCES);
    expect(calendarMonthParams(2026, 10, '')).toEqual({ from: '2026-11-01', to: '2026-11-30', source: undefined, limit: 500 });
    expect(calendarMonthParams(2026, 10, 'cbr').source).toBe('cbr');
  });

  it('eventsInRange оставляет только события своего месяца', () => {
    const evs = [{ scheduled_date: '2026-10-31' }, { scheduled_date: '2026-11-01' }, { scheduled_date: '2026-11-30' }, { scheduled_date: '2026-12-01' }];
    expect(eventsInRange(evs, monthRange(2026, 10)).map((e) => e.scheduled_date)).toEqual(['2026-11-01', '2026-11-30']);
    expect(eventsInRange(undefined, monthRange(2026, 10))).toEqual([]);
  });
});
