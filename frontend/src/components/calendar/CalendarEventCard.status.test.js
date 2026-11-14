import { describe, expect, it } from 'vitest';
import { eventStatus } from '../../lib/calendarStatus';

const TODAY = '2026-11-14';

describe('eventStatus — честный статус события календаря (14.11.2026)', () => {
  it('прошедшее заседание с цифрой — «вышло», а не «ориентировочно»', () => {
    expect(eventStatus({ scheduled_date: '2026-10-23', status: 'released', actual_value: '14' }, TODAY))
      .toEqual({ kind: 'released' });
  });

  it('неделю после даты ждём данные, потом пишем «дата прошла»', () => {
    const base = { indicator_code: 'cpi', status: 'awaiting_confirmation' };
    expect(eventStatus({ ...base, scheduled_date: '2026-11-13' }, TODAY).kind).toBe('awaiting');
    expect(eventStatus({ ...base, scheduled_date: '2026-10-20' }, TODAY).kind).toBe('passed');
    // Резюме обсуждения ставки не даёт цифры — сразу «дата прошла».
    expect(eventStatus({ scheduled_date: '2026-11-05', status: 'awaiting_confirmation' }, TODAY).kind).toBe('passed');
    expect(eventStatus({ ...base, scheduled_date: '2026-11-13', event_key: 'rosstat:plan:gdp-real:q3-2026:flash' }, TODAY).kind)
      .toBe('passed');
  });

  it('перенос источника виден до даты выхода', () => {
    expect(eventStatus({ scheduled_date: '2026-11-25', rescheduled_from: '2026-11-13',
      date_confidence: 'official_explicit' }, TODAY)).toEqual({ kind: 'moved', from: '2026-11-13' });
  });

  it('ежедневные курсы — «по графику», объявленные даты — «подтверждена»', () => {
    expect(eventStatus({ scheduled_date: '2026-11-16', date_confidence: 'official_rule' }, TODAY).kind).toBe('byRule');
    expect(eventStatus({ scheduled_date: '2026-11-18', date_confidence: 'official_explicit' }, TODAY).kind).toBe('confirmed');
  });

  it('срок Минфина — «не позднее», пока не вышло', () => {
    expect(eventStatus({ scheduled_date: '2026-11-20', date_confidence: 'official_deadline', deadline: true }, TODAY))
      .toEqual({ kind: 'deadline', date: '2026-11-20' });
    expect(eventStatus({ scheduled_date: '2026-11-20', deadline: true, status: 'released', actual_value: '3' }, TODAY).kind)
      .toBe('released');
  });
});
