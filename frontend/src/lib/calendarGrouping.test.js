import { describe, it, expect } from 'vitest';
import { groupSimilarEvents, normalizeEventUid } from './calendarGrouping';

const baseTradeEvent = {
  scheduled_date: '2026-05-14',
  scheduled_time: '13:00',
  source: 'cbr',
  title: 'Внешняя торговля товарами',
  importance: 2,
  reference_period: 'март 2026',
};

const exportsEvent = {
  ...baseTradeEvent,
  id: 1,
  indicator_code: 'exports',
  indicator_name: 'Экспорт товаров',
  source_event_uid: 'cbr-exports-2026-05-14',
};

const importsEvent = {
  ...baseTradeEvent,
  id: 2,
  indicator_code: 'imports',
  indicator_name: 'Импорт товаров',
  source_event_uid: 'cbr-imports-2026-05-14',
};

const balanceEvent = {
  ...baseTradeEvent,
  id: 3,
  indicator_code: 'trade-balance',
  indicator_name: 'Торговый баланс',
  source_event_uid: 'cbr-trade-balance-2026-05-14',
};

const ruoniaEvent = {
  scheduled_date: '2026-05-14',
  scheduled_time: '15:00',
  source: 'cbr',
  title: 'Ставка RUONIA',
  id: 4,
  indicator_code: 'ruonia',
  indicator_name: 'Ставка RUONIA',
  source_event_uid: 'cbr-ruonia-2026-05-14',
};

describe('normalizeEventUid', () => {
  it('strips indicator-suffix from cbr-style uids', () => {
    expect(normalizeEventUid('cbr-exports-2026-05-14')).toBe('cbr--2026-05-14');
    expect(normalizeEventUid('cbr-services-imports-2026-05-18')).toBe('cbr--2026-05-18');
    expect(normalizeEventUid('rosstat-cpi-2026-05-06')).toBe('rosstat--2026-05-06');
  });

  it('returns uid unchanged when format does not match', () => {
    expect(normalizeEventUid('random-id-without-date')).toBe('random-id-without-date');
    expect(normalizeEventUid('only-2026-01-01-no-source')).toBe('only-2026-01-01-no-source');
  });

  it('handles empty input', () => {
    expect(normalizeEventUid(null)).toBe('');
    expect(normalizeEventUid(undefined)).toBe('');
    expect(normalizeEventUid('')).toBe('');
  });
});

describe('groupSimilarEvents', () => {
  it('returns empty array on empty input', () => {
    expect(groupSimilarEvents([])).toEqual([]);
    expect(groupSimilarEvents(null)).toEqual([]);
  });

  it('keeps single events untouched (no indicators field)', () => {
    const result = groupSimilarEvents([ruoniaEvent]);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual(ruoniaEvent);
    expect(result[0].indicators).toBeUndefined();
  });

  it('merges 3 trade events of same publication into one card', () => {
    const result = groupSimilarEvents([exportsEvent, importsEvent, balanceEvent]);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(1);
    expect(result[0].title).toBe('Внешняя торговля товарами');
    expect(result[0].indicators).toHaveLength(3);
    expect(result[0].indicators.map((i) => i.code).sort()).toEqual([
      'exports',
      'imports',
      'trade-balance',
    ]);
    expect(result[0].indicators.find((i) => i.code === 'exports').name).toBe('Экспорт товаров');
  });

  it('does NOT merge events with different time at same source/title', () => {
    const lateExports = { ...exportsEvent, id: 5, scheduled_time: '14:00' };
    const result = groupSimilarEvents([exportsEvent, lateExports]);
    expect(result).toHaveLength(2);
  });

  it('does NOT merge events with different source', () => {
    const rosstatLike = { ...exportsEvent, id: 6, source: 'rosstat', source_event_uid: 'rosstat-exports-2026-05-14' };
    const result = groupSimilarEvents([exportsEvent, rosstatLike]);
    expect(result).toHaveLength(2);
  });

  it('does NOT merge events with different title', () => {
    const other = { ...exportsEvent, id: 7, title: 'Другая публикация' };
    const result = groupSimilarEvents([exportsEvent, other]);
    expect(result).toHaveLength(2);
  });

  it('does NOT merge events of different dates even if same indicator', () => {
    const nextMonth = { ...exportsEvent, id: 8, scheduled_date: '2026-06-11', source_event_uid: 'cbr-exports-2026-06-11' };
    const result = groupSimilarEvents([exportsEvent, nextMonth]);
    expect(result).toHaveLength(2);
  });

  it('deduplicates indicators with same code', () => {
    const dupe = { ...exportsEvent, id: 9 };
    const result = groupSimilarEvents([exportsEvent, importsEvent, dupe]);
    expect(result).toHaveLength(1);
    expect(result[0].indicators.map((i) => i.code).sort()).toEqual(['exports', 'imports']);
  });

  it('preserves order of unique groups by first-seen', () => {
    const result = groupSimilarEvents([
      ruoniaEvent,
      exportsEvent,
      importsEvent,
      balanceEvent,
    ]);
    expect(result).toHaveLength(2);
    expect(result[0].title).toBe('Ставка RUONIA');
    expect(result[1].title).toBe('Внешняя торговля товарами');
    expect(result[1].indicators).toHaveLength(3);
  });

  it('handles missing scheduled_time consistently (groups on empty time)', () => {
    const a = { ...exportsEvent, scheduled_time: null };
    const b = { ...importsEvent, scheduled_time: null };
    const result = groupSimilarEvents([a, b]);
    expect(result).toHaveLength(1);
    expect(result[0].indicators).toHaveLength(2);
  });
});
