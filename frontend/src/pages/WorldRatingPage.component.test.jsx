import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import WorldRatingPage from './WorldRatingPage';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/WorldMap', () => ({
  default: () => <div data-testid="world-map-stub">map</div>,
}));

vi.mock('../components/MapTimeline', () => ({
  default: ({ years, year, onYearChange }) => (
    <div data-testid="map-timeline-stub">
      timeline:{years.join(',')}:{year}:{typeof onYearChange}
    </div>
  ),
}));

afterEach(() => vi.restoreAllMocks());

function dataRows() {
  return screen.getAllByRole('row').slice(1);
}

describe('WorldRatingPage', () => {
  it('показывает полный рейтинг, страны без данных и переключает сортировку', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators/, []],
      [/^\/world\/countries/, {
        countries: [
          { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', indicators_count: 10 },
          { code: 'FR', slug: 'france', name: 'Франция', name_en: 'France', indicators_count: 10 },
          { code: 'IT', slug: 'italy', name: 'Италия', name_en: 'Italy', indicators_count: 10 },
        ],
        total: 3,
      }],
      [/^\/world\/rating\/concepts/, {
        concepts: [
          {
            slug: 'unemployment-rate',
            name: 'Уровень безработицы',
            unit: '% экономически активного населения',
            default_sort: 'asc',
          },
          {
            slug: 'hicp-index',
            name: 'Гармонизированный индекс потребительских цен',
            unit: 'индекс 2015=100',
            default_sort: 'desc',
          },
        ],
        total: 2,
      }],
      [/^\/world\/compare\/map-series\/unemployment-rate/, {
        concept: {
          slug: 'unemployment-rate',
          name: 'Уровень безработицы',
          unit: '% экономически активного населения',
        },
        years: [2024, 2025],
        values_by_year: {
          2025: {
            DE: {
              country_code: 'DE',
              country_slug: 'germany',
              country_name: 'Германия',
              indicator_code: 'de-une_rt_m-total-sa-t-pc-act',
              date: '2025-06-01',
              value: 3.1,
              unit: '% экономически активного населения',
            },
            FR: {
              country_code: 'FR',
              country_slug: 'france',
              country_name: 'Франция',
              indicator_code: 'fr-une_rt_m-total-sa-t-pc-act',
              date: '2025-06-01',
              value: 7.2,
              unit: '% экономически активного населения',
            },
          },
        },
        benchmark_by_year: {},
      }],
    ]);

    renderPage(
      <WorldRatingPage />,
      { path: '/world/rating/:conceptSlug', route: '/world/rating/unemployment-rate' },
    );

    expect(await screen.findByRole('heading', { name: /Рейтинг стран по уровню безработицы/i })).toBeTruthy();
    expect(await screen.findByTestId('world-map-stub')).toBeTruthy();
    expect((await screen.findByTestId('map-timeline-stub')).textContent).toContain('timeline:2024,2025:2025:function');

    expect(screen.getByRole('link', { name: 'Безработица' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Цены, изменение за год' })).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'ВВП, год' })).toBeNull();

    await waitFor(() => {
      const rows = dataRows();
      expect(rows).toHaveLength(2);
      expect(within(rows[0]).getByRole('link', { name: 'Германия' })).toBeTruthy();
      expect(within(rows[1]).getByRole('link', { name: 'Франция' })).toBeTruthy();
    });

    expect(screen.getByRole('heading', { name: /Страны без данных за 2025/i })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Италия' })).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'По убыванию' }));

    await waitFor(() => {
      const rows = dataRows();
      expect(within(rows[0]).getByRole('link', { name: 'Франция' })).toBeTruthy();
      expect(within(rows[1]).getByRole('link', { name: 'Германия' })).toBeTruthy();
    });
  });

  it('не повторяет общую единицу в каждой строке и датирует месячный ряд месяцем', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators/, []],
      [/^\/world\/countries/, {
        countries: [{ code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', indicators_count: 10 }],
        total: 1,
      }],
      [/^\/world\/rating\/concepts/, {
        concepts: [{
          slug: 'unemployment-rate',
          name: 'Уровень безработицы',
          unit: '% экономически активного населения',
          default_sort: 'asc',
        }],
        total: 1,
      }],
      [/^\/world\/compare\/map-series\/unemployment-rate/, {
        concept: { slug: 'unemployment-rate', name: 'Уровень безработицы', unit: '%' },
        years: [2025],
        values_by_year: {
          2025: {
            DE: {
              country_code: 'DE',
              country_slug: 'germany',
              country_name: 'Германия',
              indicator_code: 'de-une_rt_m-total-sa-t-pc-act',
              date: '2025-06-01',
              value: 3.1,
              unit: '%',
            },
          },
        },
        benchmark_by_year: {},
      }],
    ]);

    renderPage(
      <WorldRatingPage />,
      { path: '/world/rating/:conceptSlug', route: '/world/rating/unemployment-rate' },
    );

    await waitFor(() => expect(dataRows()).toHaveLength(1));

    const head = screen.getAllByRole('row')[0];
    expect(within(head).queryByText('Единица')).toBeNull();
    expect(within(head).getByText(/Значение, %/)).toBeTruthy();
    expect(within(head).getByText('Период')).toBeTruthy();

    const row = dataRows()[0];
    expect(within(row).queryByText('%')).toBeNull();
    expect(row.textContent).toContain('июнь 2025');
    expect(row.textContent).not.toContain('1 июня 2025');
  });

  it('включает Россию в таблицу и даёт переход в регионы', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/world\/countries/, {
        countries: [
          { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', indicators_count: 10 },
        ],
        total: 1,
      }],
      [/^\/world\/rating\/concepts/, {
        concepts: [{
          slug: 'unemployment-rate',
          name: 'Уровень безработицы',
          unit: '% экономически активного населения',
          default_sort: 'asc',
        }],
        total: 1,
      }],
      [/^\/world\/compare\/map-series\/unemployment-rate/, {
        concept: {
          slug: 'unemployment-rate',
          name: 'Уровень безработицы',
          unit: '% экономически активного населения',
          russia: {
            eligible: true,
            indicator_code: 'unemployment',
            note: 'Для России в рейтинг входит уровень безработицы по обследованию рабочей силы Росстата.',
            country: {
              code: 'RU', slug: 'russia', name_ru: 'Россия', name_en: 'Russia', region_ru: 'Европа',
            },
          },
        },
        years: [2025],
        values_by_year: {
          2025: {
            DE: {
              country_code: 'DE',
              country_slug: 'germany',
              country_name: 'Германия',
              indicator_code: 'de-une',
              date: '2025-06-01',
              value: 3.1,
              unit: '% экономически активного населения',
            },
            RU: {
              country_code: 'RU',
              country_slug: 'russia',
              country_name: 'Россия',
              indicator_code: 'unemployment',
              date: '2025-06-01',
              value: 2.3,
              unit: '% экономически активного населения',
            },
          },
        },
        benchmark_by_year: {},
      }],
    ]);

    renderPage(
      <WorldRatingPage />,
      { path: '/world/rating/:conceptSlug', route: '/world/rating/unemployment-rate' },
    );

    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Россия' })).toBeTruthy();
    });
    expect(screen.getByRole('link', { name: 'Регионы России' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Региональный рейтинг' }).getAttribute('href'))
      .toBe('/russia/region-rating/uroven-bezrabotitsy');
    expect(screen.getByText(/Росстата/)).toBeTruthy();
    expect(screen.getByRole('searchbox', { name: /Поиск/i })).toBeTruthy();
  });
});
