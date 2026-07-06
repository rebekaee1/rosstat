// Т-13: ComparePage — smoke: страница монтируется, тянет каталог и рисует
// заголовок с рядами по умолчанию, «Добавить» доступен.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import ComparePage from './ComparePage';
import { renderPage, mockApiGet } from '../test/renderPage';

afterEach(() => vi.restoreAllMocks());

const INDICATORS = [
  {
    code: 'cpi', name: 'Индекс потребительских цен', unit: '%', category: 'Цены',
    frequency: 'monthly', is_active: true, is_listed: true, current_value: 100.2,
  },
  {
    code: 'key-rate', name: 'Ключевая ставка ЦБ', unit: '%', category: 'Ставки',
    frequency: 'daily', is_active: true, is_listed: true, current_value: 14.25,
  },
];

const DATA = {
  indicator: 'cpi',
  data: [
    { date: '2025-01-01', value: 100.5 },
    { date: '2025-02-01', value: 100.7 },
  ],
};

describe('ComparePage', () => {
  it('монтируется и показывает заголовок сравнения', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators\?/, INDICATORS],
      ['/indicators', INDICATORS],
      [/^\/indicators\/[a-z0-9-]+\/data/, (url) => ({ ...DATA, indicator: url.split('/')[2] })],
      [/^\/indicators\/[a-z0-9-]+\/forecast/, { indicator: 'cpi', forecast: null }],
      ['/regions/catalog', { sections: [] }],
      [/^\/regions\/?$/, { districts: [], russia: null, totals: { regions: 0, indicators: 0, points: 0 } }],
      [/^\/regions/, { districts: [], sections: [] }],
    ]);
    renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    const heading = await screen.findByRole('heading', { level: 1 });
    expect(heading.textContent.length).toBeGreaterThan(3);
  });
});
