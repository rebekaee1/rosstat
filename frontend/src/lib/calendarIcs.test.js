import { describe, it, expect } from 'vitest';
import { buildEventIcs } from './calendarIcs';

const now = new Date('2026-10-08T10:00:00Z');

describe('buildEventIcs', () => {
  it('переводит московское время в UTC и ставит напоминание', () => {
    const ics = buildEventIcs(
      { scheduled_date: '2026-10-09', scheduled_time: '19:00', id: 7 },
      { title: 'Индекс потребительских цен, сентябрь', now },
    );
    expect(ics).toContain('DTSTART:20261009T160000Z');
    expect(ics).toContain('SUMMARY:Индекс потребительских цен\\, сентябрь');
    expect(ics).toContain('TRIGGER:-PT30M');
    expect(ics.endsWith('END:VCALENDAR\r\n')).toBe(true);
  });

  it('без времени делает событие на весь день и переносит месяц', () => {
    const ics = buildEventIcs({ scheduled_date: '2026-10-31', id: 1 }, { title: 'X', now });
    expect(ics).toContain('DTSTART;VALUE=DATE:20261031');
    expect(ics).toContain('DTEND;VALUE=DATE:20261101');
  });

  it('время после полуночи по Москве уходит на предыдущие сутки в UTC', () => {
    const ics = buildEventIcs({ scheduled_date: '2026-10-09', scheduled_time: '01:30', id: 1 }, { title: 'X', now });
    expect(ics).toContain('DTSTART:20261008T223000Z');
  });

  it('без даты возвращает null', () => {
    expect(buildEventIcs({}, { title: 'X' })).toBeNull();
  });
});
