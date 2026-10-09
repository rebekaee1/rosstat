// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { RECENT_LIMIT, RECENT_SHOWN, clearRecentQueries, readRecentQueries, rememberQuery } from './searchRecent';

describe('searchRecent', () => {
  beforeEach(() => window.localStorage.clear());

  it('запоминает запросы, свежий первым, повтор поднимается без дубля', () => {
    rememberQuery('инфляция турция');
    rememberQuery('ввп индии');
    rememberQuery('Инфляция Турция');
    expect(readRecentQueries()).toEqual(['Инфляция Турция', 'ввп индии']);
  });

  it('не хранит слишком короткое и держит не больше лимита', () => {
    rememberQuery('а');
    for (let i = 0; i < RECENT_LIMIT + 3; i += 1) rememberQuery(`запрос ${i}`);
    expect(readRecentQueries()).toHaveLength(RECENT_LIMIT);
    expect(readRecentQueries()).not.toContain('а');
  });

  it('повреждённое хранилище даёт пустой список, а не ошибку', () => {
    window.localStorage.setItem('fe_recent_queries', '{oops');
    expect(readRecentQueries()).toEqual([]);
  });

  it('круг 11: хранит восемь запросов, показывает первые шесть; «очистить» стирает всё', () => {
    expect(RECENT_LIMIT).toBe(8);
    expect(RECENT_SHOWN).toBe(6);
    for (let i = 0; i < 10; i += 1) rememberQuery(`запрос ${i}`);
    expect(readRecentQueries()).toHaveLength(8);
    clearRecentQueries();
    expect(readRecentQueries()).toEqual([]);
  });
});
