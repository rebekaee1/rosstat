// Т-13: ComparePage — smoke: страница монтируется, дерево «сначала страна»,
// без трёх плоских колонок-пикера.
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

const WORLD_CATALOG = {
  items: [
    {
      code: 'w:germany:unemployment-rate',
      country_slug: 'germany',
      country_name: 'Германия',
      concept_slug: 'unemployment-rate',
      concept_name: 'Безработица',
      frequency: 'monthly',
      unit: '%',
    },
  ],
  total: 1,
};

function mockCompareApis() {
  mockApiGet([
    ['/auth/me', { user: null }],
    [/^\/indicators\?/, INDICATORS],
    ['/indicators', INDICATORS],
    [/^\/indicators\/[a-z0-9-]+\/data/, (url) => ({ ...DATA, indicator: url.split('/')[2] })],
    [/^\/indicators\/[a-z0-9-]+\/forecast/, { indicator: 'cpi', forecast: null }],
    ['/regions/catalog', { sections: [] }],
    [/^\/regions\/?$/, { districts: [], russia: null, totals: { regions: 0, indicators: 0, points: 0 } }],
    [/^\/regions/, { districts: [], sections: [] }],
    ['/world/compare/catalog', WORLD_CATALOG],
  ]);
}

describe('ComparePage', () => {
  it('монтируется и показывает заголовок сравнения', async () => {
    mockCompareApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    const heading = await screen.findByRole('heading', { level: 1 });
    expect(heading.textContent).toBe('Сравнение показателей');
  });

  it('показывает шаг выбора страны с Россией первой', async () => {
    mockCompareApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    expect(await screen.findByText('Страна')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Россия' })).toBeTruthy();
    expect(await screen.findByRole('button', { name: 'Германия' })).toBeTruthy();
  });

  it('не рендерит три плоские колонки пикера', async () => {
    mockCompareApis();
    const { container } = renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    await screen.findByRole('heading', { level: 1 });
    const picker = container.querySelector('[data-block="compare-add"]');
    expect(picker).toBeTruthy();
    expect(picker.querySelector('.xl\\:grid-cols-3')).toBeNull();
    // Старые равные заголовки колонок «Россия / Регионы / Страны» не сосуществуют.
    expect(screen.queryByText('Добавить региональный индикатор')).toBeNull();
    expect(screen.queryByText('Единый показатель, затем страна')).toBeNull();
  });
});
