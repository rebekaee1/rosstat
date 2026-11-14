import { describe, it, expect } from 'vitest';
import { groupSimilarEvents } from './calendarGrouping';

const base = { scheduled_date: '2026-11-11', scheduled_time: '16:00', source: 'cbr', title: 'Внешняя торговля товарами',
  source_event_uid: 'uid-1' };

describe('карточка-группа: статус и цифры (14.11.2026)', () => {
  it('разные ряды одной публикации — «вышло» без чужой цифры', () => {
    const [card] = groupSimilarEvents([
      { ...base, id: 1, indicator_code: 'exports', status: 'awaiting_confirmation' },
      { ...base, id: 2, indicator_code: 'imports', status: 'released', actual_value: '24,1', released_on: '2026-11-11' },
    ]);
    expect(card.status).toBe('released');
    expect(card.released_on).toBe('2026-11-11');
    expect(card.actual_value).toBeNull();
  });

  it('индекс цен и его части — цифра головного ряда', () => {
    const cpi = { ...base, source: 'rosstat', title: 'ИПЦ', scheduled_time: null, source_event_uid: 'rosstat-x-2026-11-25' };
    const [card] = groupSimilarEvents([
      { ...cpi, id: 3, indicator_code: 'cpi-food', status: 'released', actual_value: '100,9' },
      { ...cpi, id: 4, indicator_code: 'cpi', status: 'released', actual_value: '100,5', previous_value: '100,3' },
    ]);
    expect(card.actual_value).toBe('100,5');
    expect(card.previous_value).toBe('100,3');
  });
});
