import { expect, it } from 'vitest';
import { isFreshSeries, splitTourismFeed, tourismRuGroup, TOURISM_FEED_MAX } from './tourismFeed';

const NOW = new Date('2026-11-20T12:00:00Z');
const ind = (code, current_date, frequency = 'monthly') => ({ code, current_date, frequency });

it('свежий — не старше года; годовой — за прошлый или текущий год', () => {
  expect(isFreshSeries(ind('a', '2026-09-30'), NOW)).toBe(true);
  expect(isFreshSeries(ind('a', '2025-11-25'), NOW)).toBe(true);
  expect(isFreshSeries(ind('a', '2025-06-30', 'quarterly'), NOW)).toBe(false);
  expect(isFreshSeries(ind('a', '2025-01-01', 'annual'), NOW)).toBe(true);
  expect(isFreshSeries(ind('a', '2024-12-31', 'annual'), NOW)).toBe(false);
  expect(isFreshSeries(ind('a', null), NOW)).toBe(false);
});

it('в ленту — до восьми свежих рядов, ведущие первыми; старые и лишние уходят в остальное', () => {
  const leads = ['l1', 'l2', 'l3'];
  const listed = [
    ind('old-household', '2023-12-31', 'annual'),
    ind('free1', '2026-09-30'), ind('l3', '2026-06-30'), ind('l1', '2026-06-30'),
    ...Array.from({ length: 9 }, (_, i) => ind(`x${i}`, `2026-0${(i % 8) + 1}-15`)),
  ];
  const { feed, rest } = splitTourismFeed(listed, leads, NOW);
  expect(feed).toHaveLength(TOURISM_FEED_MAX);
  expect(feed.slice(0, 2).map((i) => i.code)).toEqual(['l1', 'l3']);
  expect(feed.some((i) => i.code === 'old-household')).toBe(false);
  expect(rest.map((i) => i.code)).toContain('old-household');
  expect(feed.length + rest.length).toBe(listed.length);
});

it('группы остальных рядов', () => {
  expect(tourismRuGroup('tour-outbound-turkey')).toBe('trips');
  expect(tourismRuGroup('tour-hotel-guests')).toBe('stay');
  expect(tourismRuGroup('tour-cpi-hotels')).toBe('prices');
  expect(tourismRuGroup('tour-package-price')).toBe('prices');
  expect(tourismRuGroup('tour-airport-sochi')).toBe('transport');
  expect(tourismRuGroup('tour-tax')).toBe('money');
  expect(tourismRuGroup('tour-packages')).toBe('money');
});
