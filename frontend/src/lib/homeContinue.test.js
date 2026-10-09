// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { RECENT_VISITED_KEY, clearRecentVisited, continueItems, readRecentVisited } from './homeContinue';

const put = (items) => window.localStorage.setItem(RECENT_VISITED_KEY, JSON.stringify(items));

describe('homeContinue', () => {
  beforeEach(() => window.localStorage.clear());

  it('читает записи зоны G (путь, название, вид, время) и отбрасывает повреждённые и чужие адреса', () => {
    put([
      { path: '/turkey', title: 'Турция', kind: 'country', ts: 5 },
      { path: 'https://evil.example/', title: 'Чужой', kind: 'country', ts: 4 },
      { path: '//evil.example', title: 'Чужой 2', kind: 'country', ts: 3 },
      { path: '/x', title: '', kind: 'country', ts: 2 },
      { path: '/y', title: 'Игра', kind: 'unknown-kind', ts: 1 },
      null,
    ]);
    expect(readRecentVisited()).toEqual([
      { path: '/turkey', title: 'Турция', kind: 'country', ts: 5 },
      { path: '/y', title: 'Игра', kind: 'other', ts: 1 },
    ]);
  });

  it('пустое и повреждённое хранилище дают пустой список', () => {
    expect(readRecentVisited()).toEqual([]);
    window.localStorage.setItem(RECENT_VISITED_KEY, '{oops');
    expect(readRecentVisited()).toEqual([]);
    window.localStorage.setItem(RECENT_VISITED_KEY, '"строка"');
    expect(readRecentVisited()).toEqual([]);
  });

  it('continueItems убирает повторы по названию и ограничивает число', () => {
    const items = [
      { path: '/a', title: 'Турция', kind: 'country', ts: 3 },
      { path: '/a?x=1', title: 'турция', kind: 'country', ts: 2 },
      ...Array.from({ length: 9 }, (_, i) => ({ path: `/p${i}`, title: `Страница ${i}`, kind: 'other', ts: 1 })),
    ];
    const out = continueItems(items, 6);
    expect(out).toHaveLength(6);
    expect(out.map((item) => item.title).filter((title) => /турция/i.test(title))).toHaveLength(1);
  });

  it('clearRecentVisited стирает список', () => {
    put([{ path: '/turkey', title: 'Турция', kind: 'country', ts: 5 }]);
    clearRecentVisited();
    expect(readRecentVisited()).toEqual([]);
  });
});
