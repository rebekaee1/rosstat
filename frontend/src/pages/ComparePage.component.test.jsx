// Т-13: ComparePage — smoke: страница монтируется, дерево «сначала страна»,
// без трёх плоских колонок-пикера.
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import ComparePage from './ComparePage';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../lib/track', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, track: vi.fn() };
});

import { track } from '../lib/track';

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

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
  return mockApiGet([
    ['/auth/me', { user: null }],
    [/^\/indicators\?/, INDICATORS],
    ['/indicators', INDICATORS],
    [/^\/indicators\/[a-z0-9-]+\/data/, (url) => ({ ...DATA, indicator: url.split('/')[2] })],
    [/^\/indicators\/[a-z0-9-]+\/forecast/, { indicator: 'cpi', forecast: null }],
    ['/regions/catalog', { sections: [] }],
    [/^\/regions\/?$/, { districts: [], russia: null, totals: { regions: 0, indicators: 0, points: 0 } }],
    [/^\/regions/, { districts: [], sections: [] }],
    ['/world/compare/catalog', WORLD_CATALOG],
    [/^\/world\/[^/]+\/regions$/, { regions: [], indicators: [], sections: [] }],
  ]);
}

describe('ComparePage', () => {
  beforeEach(() => {
    track.mockClear();
  });

  it('монтируется и показывает заголовок сравнения', async () => {
    mockCompareApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    const heading = await screen.findByRole('heading', { level: 1 });
    expect(heading.textContent).toBe('Сравнение показателей');
  });

  it('AddIndicator dual-write: compare_search и search_query(compare-macro)', async () => {
    mockCompareApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    fireEvent.click(await screen.findByRole('button', { name: 'Россия' }));
    fireEvent.click(await screen.findByRole('button', { name: /Макропоказатели/ }));
    const input = await screen.findByPlaceholderText('Найдите или выберите макроиндикатор…');

    track.mockClear();
    vi.useFakeTimers();
    fireEvent.change(input, { target: { value: 'cpi' } });
    expect(track).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(900);
    });

    expect(track).toHaveBeenCalledWith('compare_search', { q: 'cpi', results: 1 });
    expect(track).toHaveBeenCalledWith('search_query', {
      q: 'cpi',
      results: 1,
      context: 'compare-macro',
    });
  });

  it('на шаге России поиск сразу по всему каталогу, плитки макро/регионы на месте', async () => {
    mockCompareApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    fireEvent.click(await screen.findByRole('button', { name: 'Россия' }));
    expect(screen.getByRole('button', { name: /Макропоказатели/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Регионы/ })).toBeTruthy();
    const input = await screen.findByPlaceholderText('Найти показатель…');
    fireEvent.focus(input);
    expect(screen.getByText('Индекс потребительских цен')).toBeTruthy();
    expect(screen.getByText('Ключевая ставка ЦБ')).toBeTruthy();
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

  it('EN: Россия в compare-catalog находится по gross и стоит рядом с US/Canada GDP', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators\?/, INDICATORS],
      ['/indicators', INDICATORS],
      [/^\/indicators\/[a-z0-9-]+\/data/, (url) => ({ ...DATA, indicator: url.split('/')[2] })],
      [/^\/indicators\/[a-z0-9-]+\/forecast/, { indicator: 'cpi', forecast: null }],
      ['/regions/catalog', { sections: [] }],
      [/^\/regions\/?$/, { districts: [], russia: null, totals: { regions: 0, indicators: 0, points: 0 } }],
      [/^\/regions/, { districts: [], sections: [] }],
      ['/world/compare/catalog', {
        items: [
          {
            code: 'w:united-states:gdp-usd',
            country_slug: 'united-states',
            country_name: 'United States',
            concept_slug: 'gdp-usd',
            concept_name: 'Gross domestic product',
            frequency: 'annual',
            unit: 'bn $',
          },
          {
            code: 'w:canada:gdp-usd',
            country_slug: 'canada',
            country_name: 'Canada',
            concept_slug: 'gdp-usd',
            concept_name: 'Gross domestic product',
            frequency: 'annual',
            unit: 'bn $',
          },
          {
            code: 'w:russia:gdp-usd',
            country_slug: 'russia',
            country_name: 'Russia',
            concept_slug: 'gdp-usd',
            concept_name: 'Gross domestic product',
            frequency: 'annual',
            unit: 'bn $',
            national_method: true,
          },
        ],
        total: 3,
      }],
      [/^\/world\/compare\/series\//, {
        meta: {
          code: 'w:russia:gdp-usd',
          country_slug: 'russia',
          country_name: 'Russia',
          concept_slug: 'gdp-usd',
          concept_name: 'Gross domestic product',
          unit: 'bn $',
          source: 'Rosstat, Bank of Russia',
          national_method: true,
        },
        data: [
          { date: '2023-01-01', value: 2000 },
          { date: '2024-01-01', value: 2100 },
        ],
      }],
    ]);
    renderPage(<ComparePage />, { path: '/compare', route: '/compare', locale: 'en' });
    const heading = await screen.findByRole('heading', { level: 1 });
    expect(heading.textContent).toBe('Compare indicators');
    fireEvent.click(await screen.findByRole('button', { name: 'Russia' }));
    expect(screen.getByRole('button', { name: /Macro indicators/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Regions/ })).toBeTruthy();
    const input = screen.getByPlaceholderText('Find indicator…');
    fireEvent.focus(input);
    expect(screen.getByText('Индекс потребительских цен')).toBeTruthy();
    fireEvent.change(input, { target: { value: 'gross' } });
    expect(screen.getByText('Gross domestic product')).toBeTruthy();
    expect(screen.queryByText(/валового внутреннего/i)).toBeNull();
  });

  it('типизированный world-код us-unemployment-rate грузит ряд с карточки', async () => {
    const spy = mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators\?/, INDICATORS],
      ['/indicators', INDICATORS],
      [/^\/indicators\/[a-z0-9-]+\/data/, (url) => ({ ...DATA, indicator: url.split('/')[2] })],
      [/^\/indicators\/[a-z0-9-]+\/forecast/, { indicator: 'cpi', forecast: null }],
      ['/regions/catalog', { sections: [] }],
      [/^\/regions\/?$/, { districts: [], russia: null, totals: { regions: 0, indicators: 0, points: 0 } }],
      [/^\/regions/, { districts: [], sections: [] }],
      ['/world/compare/catalog', WORLD_CATALOG],
      ['/world/indicators/united-states/us-unemployment-rate/data', {
        points: [
          { date: '2025-07-01', value: 4.2 },
          { date: '2025-08-01', value: 4.3 },
        ],
      }],
      ['/world/indicators/united-states/us-unemployment-rate', {
        country: { slug: 'united-states', name: 'США', name_en: 'United States' },
        indicator: {
          code: 'us-unemployment-rate',
          name: 'Уровень безработицы',
          name_en: 'Unemployment Rate',
          unit: '%',
          frequency: 'monthly',
          concept_slug: 'unemployment-rate',
        },
      }],
    ]);
    renderPage(<ComparePage />, {
      path: '/compare',
      route: '/compare?codes=w:united-states:us-unemployment-rate',
    });
    expect(await screen.findByRole('heading', { level: 2, name: /Уровень безработицы — США/ })).toBeTruthy();
    expect(screen.queryByTestId('compare-chart-skeleton')).toBeNull();
    expect(screen.queryByTestId('compare-empty')).toBeNull();
    const urls = spy.mock.calls.map((call) => String(call[0]));
    expect(urls.some((u) => u.includes('/world/compare/series/united-states/us-unemployment-rate'))).toBe(true);
    expect(urls.some((u) => u === '/world/indicators/united-states/us-unemployment-rate/data')).toBe(true);
  });

  it('голый код не из каталога — empty-state, не скелетон и не запрос /data', async () => {
    const spy = mockCompareApis();
    renderPage(<ComparePage />, {
      path: '/compare',
      route: '/compare?codes=us-unemployment-rate',
    });
    const empty = await screen.findByTestId('compare-empty');
    expect(empty.textContent).toMatch(/Не удалось загрузить выбранные ряды/);
    expect(screen.queryByTestId('compare-chart-skeleton')).toBeNull();
    await waitFor(() => {
      const urls = spy.mock.calls.map((call) => String(call[0]));
      expect(urls.some((u) => u.includes('/indicators/us-unemployment-rate/data'))).toBe(false);
    });
  });

  it('США: ветка штатов как регионы России — территория + показатель', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators\?/, INDICATORS],
      ['/indicators', INDICATORS],
      [/^\/indicators\/[a-z0-9-]+\/data/, (url) => ({ ...DATA, indicator: url.split('/')[2] })],
      [/^\/indicators\/[a-z0-9-]+\/forecast/, { indicator: 'cpi', forecast: null }],
      ['/regions/catalog', { sections: [] }],
      [/^\/regions\/?$/, { districts: [], russia: null, totals: { regions: 0, indicators: 0, points: 0 } }],
      [/^\/regions/, { districts: [], sections: [] }],
      ['/world/compare/catalog', {
        items: [
          {
            code: 'w:united-states:us-unemployment-rate',
            country_slug: 'united-states',
            country_name: 'США',
            country_name_en: 'United States',
            concept_slug: 'us-unemployment-rate',
            concept_name: 'Уровень безработицы',
            frequency: 'monthly',
            unit: '%',
          },
        ],
        total: 1,
      }],
      ['/world/united-states/regions', {
        country: { slug: 'united-states', name: 'США' },
        kind_label_plural: 'Штаты',
        regions: [
          { slug: 'california', name: 'Калифорния', name_en: 'California' },
        ],
        indicators: [
          { code: 'unemployment-rate', name: 'Безработица', section: 'Труд' },
        ],
        sections: [
          { num: 1, name: 'Труд', indicators: [{ code: 'unemployment-rate', name: 'Безработица' }] },
        ],
      }],
    ]);
    renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    fireEvent.click(await screen.findByRole('button', { name: 'США' }));
    expect(await screen.findByRole('button', { name: /Макропоказатели/ })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Штаты/ }));
    expect(screen.getAllByText('Добавить ряд территории').length).toBeGreaterThan(0);
    expect(screen.getByPlaceholderText('Выберите или найдите территорию…')).toBeTruthy();
  });
});
