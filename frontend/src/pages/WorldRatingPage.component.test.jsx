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
    // Правка 16: изменение потребительских цен на витрине называется инфляцией.
    expect(screen.getByRole('link', { name: 'Инфляция' })).toBeTruthy();
    expect(screen.queryByRole('link', { name: /изменение за год/i })).toBeNull();

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
    expect(screen.queryByRole('searchbox')).toBeNull();
  });

  function ratingMocks({ user = null } = {}) {
    return [
      ['/auth/me', { user }],
      [/^\/indicators/, []],
      [/^\/world\/countries/, {
        countries: [
          { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', indicators_count: 10 },
          { code: 'FR', slug: 'france', name: 'Франция', name_en: 'France', indicators_count: 10 },
        ],
        total: 2,
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
            FR: {
              country_code: 'FR',
              country_slug: 'france',
              country_name: 'Франция',
              indicator_code: 'fr-une',
              date: '2025-06-01',
              value: 7.2,
              unit: '% экономически активного населения',
            },
          },
        },
        benchmark_by_year: {},
      }],
      [/^\/world\/compare\/map-series\/hicp-index/, {
        concept: { slug: 'hicp-index', name: 'Гармонизированный индекс потребительских цен', unit: '%' },
        years: [2025],
        values_by_year: {},
        benchmark_by_year: {},
      }],
    ];
  }

  it('гость: «Добавить показатель» не создаёт колонку и зовёт зарегистрироваться', async () => {
    mockApiGet(ratingMocks());

    renderPage(
      <WorldRatingPage />,
      { path: '/world/rating/:conceptSlug', route: '/world/rating/unemployment-rate' },
    );

    await waitFor(() => expect(dataRows()).toHaveLength(2));
    expect(screen.getByRole('button', { name: 'Добавить показатель' })).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Создать аккаунт' })).toBeNull();

    const headBefore = screen.getAllByRole('row')[0];
    expect(within(headBefore).getAllByRole('columnheader')).toHaveLength(4);
    expect(within(headBefore).queryByRole('button', { name: 'Убрать колонку' })).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Добавить показатель' }));

    expect(screen.getByRole('link', { name: 'Создать аккаунт' }).getAttribute('href')).toBe('/register');
    expect(screen.getByRole('link', { name: 'Войти' }).getAttribute('href')).toBe('/login');
    expect(within(screen.getAllByRole('row')[0]).getAllByRole('columnheader')).toHaveLength(4);
    expect(screen.queryByRole('button', { name: 'Убрать колонку' })).toBeNull();
    expect(within(dataRows()[0]).getByRole('link', { name: 'Германия' })).toBeTruthy();
  });

  it('гость игнорирует cols в URL и не рисует лишние колонки', async () => {
    mockApiGet(ratingMocks());

    renderPage(
      <WorldRatingPage />,
      {
        path: '/world/rating/:conceptSlug',
        route: '/world/rating/unemployment-rate?cols=hicp-index',
      },
    );

    await waitFor(() => expect(dataRows()).toHaveLength(2));
    expect(within(screen.getAllByRole('row')[0]).getAllByRole('columnheader')).toHaveLength(4);
    expect(screen.queryByRole('button', { name: 'Убрать колонку' })).toBeNull();
    expect(screen.getByRole('link', { name: 'Инфляция' })).toBeTruthy();
  });

  it('доп. колонка берёт ближайший опубликованный год, если за базовый год данных нет', async () => {
    const mocks = [
      ['/auth/me', { user: { id: 1, email: 't@example.com' } }],
      [/^\/indicators/, []],
      [/^\/world\/countries/, {
        countries: [
          { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', indicators_count: 10 },
          { code: 'FR', slug: 'france', name: 'Франция', name_en: 'France', indicators_count: 10 },
        ],
        total: 2,
      }],
      [/^\/world\/rating\/concepts/, {
        concepts: [
          {
            slug: 'unemployment-rate',
            name: 'Уровень безработицы',
            unit: '% экономически активного населения',
            default_sort: 'desc',
          },
          {
            slug: 'hicp-index',
            name: 'Гармонизированный индекс потребительских цен',
            unit: '%',
            default_sort: 'desc',
          },
        ],
        total: 2,
      }],
      // База — безработица 2026; доп. колонка «Инфляция» публикуется до 2025.
      [/^\/world\/compare\/map-series\/unemployment-rate/, {
        concept: {
          slug: 'unemployment-rate',
          name: 'Уровень безработицы',
          unit: '% экономически активного населения',
        },
        years: [2025, 2026],
        values_by_year: {
          2026: {
            DE: {
              country_code: 'DE',
              country_slug: 'germany',
              country_name: 'Германия',
              indicator_code: 'de-une',
              date: '2026-06-01',
              value: 3.4,
              unit: '% экономически активного населения',
            },
            FR: {
              country_code: 'FR',
              country_slug: 'france',
              country_name: 'Франция',
              indicator_code: 'fr-une',
              date: '2026-06-01',
              value: 7.0,
              unit: '% экономически активного населения',
            },
          },
        },
        benchmark_by_year: {},
      }],
      [/^\/world\/compare\/map-series\/hicp-index/, {
        concept: { slug: 'hicp-index', name: 'Гармонизированный индекс потребительских цен', unit: '%' },
        years: [2024, 2025],
        values_by_year: {
          2025: {
            DE: {
              country_code: 'DE',
              country_slug: 'germany',
              country_name: 'Германия',
              indicator_code: 'de-hicp',
              date: '2025-12-01',
              value: 2.2,
              unit: '%',
            },
            FR: {
              country_code: 'FR',
              country_slug: 'france',
              country_name: 'Франция',
              indicator_code: 'fr-hicp',
              date: '2025-12-01',
              value: 1.1,
              unit: '%',
            },
          },
        },
        benchmark_by_year: {},
      }],
    ];

    mockApiGet(mocks);

    renderPage(
      <WorldRatingPage />,
      {
        path: '/world/rating/:conceptSlug',
        route: '/world/rating/unemployment-rate?cols=hicp-index',
      },
    );

    await waitFor(() => expect(dataRows()).toHaveLength(2));
    const head = screen.getAllByRole('row')[0];
    expect(within(head).getAllByRole('columnheader')).toHaveLength(5);
    // Значения инфляции взяты из 2025 — ближайшего опубликованного года к базе 2026
    // (сортировка по безработице desc: Франция 7,0 выше Германии 3,4).
    expect(within(dataRows()[0]).getByText('Франция')).toBeTruthy();
    await waitFor(() => {
      expect(dataRows()[0].textContent).toMatch(/1[.,]10/);
      expect(dataRows()[1].textContent).toMatch(/2[.,]20/);
    });
  });
});
