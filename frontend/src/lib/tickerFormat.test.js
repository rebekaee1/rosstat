import { describe, expect, it } from 'vitest';
import { formatAsOfHuman, tickerSourceKind, tickerSourceName } from './tickerFormat';

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

  it('свежий дневной курс (вчера, выходные) не подписывается, если задан порог давности', () => {
    // 4 октября; значение за 2 октября — «as of Oct 2» над EUR/USD только шумит.
    expect(formatAsOfHuman('2026-10-02', 'en', NOON_MSK, { minAgeDays: 4 })).toBe('');
    expect(formatAsOfHuman('2026-10-02', 'ru', NOON_MSK, { minAgeDays: 4 })).toBe('');
    // По-настоящему устаревшее значение подписывается по-прежнему.
    expect(formatAsOfHuman('2026-09-20', 'en', NOON_MSK, { minAgeDays: 4 })).toBe('Sep 20');
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

describe('tickerSourceName: источник для подсказки', () => {
  it('по-русски называет биржу, ЦБ и EIA словами', () => {
    expect(tickerSourceName('MOEX', 'ru')).toBe('Московская биржа');
    expect(tickerSourceName('ЦБ РФ', 'ru')).toBe('Банк России');
    expect(tickerSourceName('Банк России', 'ru')).toBe('Банк России');
    expect(tickerSourceName('ЕЦБ', 'ru')).toBe('Европейский центральный банк');
    expect(tickerSourceName('EIA', 'ru')).toContain('EIA');
    expect(tickerSourceName('Binance', 'ru')).toBe('Binance');
  });

  it('по-английски кириллицы нет', () => {
    expect(tickerSourceName('MOEX', 'en')).toBe('Moscow Exchange');
    expect(tickerSourceName('ЕЦБ', 'en')).toBe('European Central Bank');
    expect(tickerSourceName('Банк России', 'en')).toBe('Bank of Russia');
    expect(tickerSourceName('ЦБ РФ', 'en')).toBe('Bank of Russia');
    expect(tickerSourceName(undefined, 'en')).toBeUndefined();
  });
});
