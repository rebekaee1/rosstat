import { describe, expect, it } from 'vitest';
import { formatAsOfHuman, tickerSourceKind } from './tickerFormat';

const NOON_MSK = new Date('2026-10-04T09:00:00Z'); // 12:00 по Москве, 4 октября

describe('formatAsOfHuman', () => {
  it('значение за сегодня не подписывается: «04.10» рядом с курсом только шумит', () => {
    expect(formatAsOfHuman('2026-10-04', 'ru', NOON_MSK)).toBe('');
    expect(formatAsOfHuman('2026-10-04T08:00:00+00:00', 'ru', NOON_MSK)).toBe('');
  });

  it('устаревшее значение подписывается человеческой датой', () => {
    expect(formatAsOfHuman('2026-10-02', 'ru', NOON_MSK)).toMatch(/^2\s+окт/);
    expect(formatAsOfHuman('2026-10-02', 'en', NOON_MSK)).toBe('Oct 2');
  });

  it('день считается в часовом поясе витрины: 23:30 UTC — уже следующий день по Москве', () => {
    const lateUtc = new Date('2026-10-03T23:30:00Z'); // 02:30 4 октября по Москве
    expect(formatAsOfHuman('2026-10-04', 'ru', lateUtc)).toBe('');
    expect(formatAsOfHuman('2026-10-04', 'en', lateUtc)).toMatch(/Oct 4/);
  });

  it('пустое и непонятное значение — без подписи', () => {
    expect(formatAsOfHuman(null)).toBe('');
    expect(formatAsOfHuman('вчера')).toBe('');
  });
});

describe('tickerSourceKind', () => {
  it('различает биржевую котировку и официальный курс ЦБ', () => {
    expect(tickerSourceKind('MOEX')).toBe('market');
    expect(tickerSourceKind('CBR')).toBe('cb');
    expect(tickerSourceKind('Банк России')).toBe('cb');
  });

  it('прочие источники без подписи', () => {
    expect(tickerSourceKind('EIA')).toBeNull();
    expect(tickerSourceKind('Binance')).toBeNull();
    expect(tickerSourceKind(undefined)).toBeNull();
  });
});
