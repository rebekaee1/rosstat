import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import WorldRatingPage from './WorldRatingPage';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/WorldMap', () => ({
  default: vi.fn(() => <div data-testid="world-map-stub">map</div>),
}));

vi.mock('../components/MapTimeline', () => ({
  default: ({ years, year, onYearChange }) => (
    <div data-testid="map-timeline-stub">
      timeline:{years.join(',')}:{year}:{typeof onYearChange}
    </div>
  ),
}));

afterEach(() => vi.restoreAllMocks());

/** Строки полной таблицы (внутри #rating-table). */
function dataRows(container = document.body) {
  const table = container.querySelector('#rating-table');
  const scope = table || container;
  return screen.getAllByRole('row').filter((row) => scope.contains(row)).slice(1);
}

/** Шапка таблицы (первая строка внутри #rating-table). */
function headRow() {
  return screen.getAllByRole('row').filter(
    (row) => document.querySelector('#rating-table')?.contains(row),
  )[0];
}

describe('WorldRatingPage', () => {
  it('показывает полный рейтинг, сортирует кликом по заголовку и глобальным переключателем', async () => {
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
            unit: '%',
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
      [/^\/world\/compare\/map-series\/hicp-index/, {
        concept: { slug: 'hicp-index', name: 'Гармонизированный индекс потребительских цен', unit: '%' },
        years: [2025],
        values_by_year: {
          2025: {
            DE: {
              country_code: 'DE',
              country_slug: 'germany',
              country_name: 'Германия',
              indicator_code: 'de-hicp',
              date: '2025-12-01',
              value: 1.1,
              unit: '%',
            },
            FR: {
              country_code: 'FR',
              country_slug: 'france',
              country_name: 'Франция',
              indicator_code: 'fr-hicp',
              date: '2025-12-01',
              value: 2.2,
              unit: '%',
            },
          },
        },
        benchmark_by_year: {},
      }],
    ]);

    renderPage(
      <WorldRatingPage />,
      { path: '/world/rating/:conceptSlug', route: '/world/rating/unemployment-rate?cols=hicp-index' },
    );

    expect(await screen.findByRole('heading', { name: /Рейтинг стран по уровню безработицы/i })).toBeTruthy();
    expect(await screen.findByTestId('world-map-stub')).toBeTruthy();

    expect(screen.getAllByRole('link', { name: 'Безработица' }).length).toBeGreaterThan(0);
    // Правка 16: изменение потребительских цен на витрине называется инфляцией.
    expect(screen.getAllByRole('link', { name: 'Инфляция' }).length).toBeGreaterThan(0);
    expect(screen.queryByRole('link', { name: /изменение за год/i })).toBeNull();

    // Смысловой порядок концепта: безработица asc — Германия (3,1) выше.
    await waitFor(() => {
      const rows = dataRows();
      expect(rows).toHaveLength(2);
      expect(within(rows[0]).getByRole('link', { name: 'Германия' })).toBeTruthy();
      expect(within(rows[1]).getByRole('link', { name: 'Франция' })).toBeTruthy();
    });

    expect(screen.getByRole('heading', { name: /Страны без данных за 2025/i })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Италия' })).toBeTruthy();

    // Первый клик по заголовку доп-колонки — смысловое направление её
    // концепта (инфляция desc): Франция (2,2) поднимается наверх.
    const extraTh = screen
      .getAllByRole('columnheader')
      .find((node) => node.textContent.includes('Инфляция'));
    const extraHeader = within(extraTh).getAllByRole('button')[0];
    fireEvent.click(extraHeader);

    await waitFor(() => {
      const rows = dataRows();
      expect(within(rows[0]).getByRole('link', { name: 'Франция' })).toBeTruthy();
      expect(within(rows[1]).getByRole('link', { name: 'Германия' })).toBeTruthy();
      expect(rows[0].textContent).toMatch(/2[.,]20/);
    });

    // Второй клик разворачивает доп-колонку по возрастанию.
    fireEvent.click(extraHeader);
    await waitFor(() => {
      expect(within(dataRows()[0]).getByRole('link', { name: 'Германия' })).toBeTruthy();
    });

    // Глобальный переключатель «Порядок» разворачивает активную колонку
    // (после кликов активна доп-колонка asc → desc).
    fireEvent.click(screen.getByRole('button', { name: 'По убыванию' }));
    await waitFor(() => {
      expect(within(dataRows()[0]).getByRole('link', { name: 'Франция' })).toBeTruthy();
    });
    fireEvent.click(screen.getByRole('button', { name: 'По возрастанию' }));
    await waitFor(() => {
      expect(within(dataRows()[0]).getByRole('link', { name: 'Германия' })).toBeTruthy();
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

    const head = headRow();
    expect(within(head).queryByText('Единица')).toBeNull();
    expect(within(head).getByText(/Значение, %/)).toBeTruthy();

    const row = dataRows()[0];
    expect(within(row).queryByText('%')).toBeNull();
    expect(row.textContent).toContain('июнь 2025');
    expect(row.textContent).not.toContain('1 июня 2025');
  });

  it('на рейтинге нет поиска страны, фильтра и матрицы «Страны рядом» (правка 16)', async () => {
    mockApiGet(ratingMocks());

    renderPage(
      <WorldRatingPage />,
      { path: '/world/rating/:conceptSlug', route: '/world/rating/unemployment-rate' },
    );

    await waitFor(() => expect(dataRows()).toHaveLength(2));
    expect(document.querySelector('#rating-table input[type="search"]')).toBeNull();
    expect(screen.queryByPlaceholderText(/Найти страну/)).toBeNull();
    expect(screen.queryByRole('button', { name: 'Сбросить фильтр' })).toBeNull();
    // Правка 16: секция «Страны рядом» удалена целиком.
    expect(screen.queryByText('Страны рядом')).toBeNull();
    expect(document.querySelector('#compare-matrix')).toBeNull();
    // Плюсики добавления стран в таблицу убраны.
    expect(document.querySelector('#rating-table').textContent).not.toContain('+');
  });

  it('включает Россию в таблицу, блок ссылок только в ru-локали, серверная нота не рендерится', async () => {
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
      const ruLink = dataRows().flatMap((row) => within(row).queryAllByRole('link', { name: 'Россия' }))[0];
      expect(ruLink).toBeTruthy();
    });
    // ru-локаль localhost: блок «Россия и регионы» отрисован с региональными ссылками…
    expect(screen.getByText('Россия и регионы')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Регионы России' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Региональный рейтинг' }).getAttribute('href'))
      .toBe('/russia/region-rating/uroven-bezrabotitsy');
    // …но серверная нота «Для России …» больше не рендерится нигде.
    expect(screen.queryByText(/Росстата/)).toBeNull();
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
            unit: '%',
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

  it('гость может открыть один показатель; полный набор — после регистрации', async () => {
    mockApiGet(ratingMocks());

    renderPage(
      <WorldRatingPage />,
      { path: '/world/rating/:conceptSlug', route: '/world/rating/unemployment-rate' },
    );

    await waitFor(() => expect(dataRows()).toHaveLength(2));

    // Гостю доступен один выбор — кнопка показателя в панели добавления.
    fireEvent.click(screen.getByRole('button', { name: 'Добавить показатель' }));
    fireEvent.click(screen.getByRole('button', { name: 'Инфляция' }));

    // Колонки: место, страна, значение, инфляция, период.
    await waitFor(() => {
      const head = headRow();
      expect(within(head).getAllByRole('columnheader')).toHaveLength(5);
    });
    // Второй добавить нельзя — достигнут гостевой лимит.
    fireEvent.click(screen.getByRole('button', { name: 'Добавить показатель' }));
    expect(within(document.body).queryAllByRole('button', { name: 'Безработица' }).length).toBe(0);
  });

  it('авторизованный открывает колонки в таблице до пяти показателей', async () => {
    mockApiGet(ratingMocks({ user: { id: 1, email: 't@example.com' } }));

    renderPage(
      <WorldRatingPage />,
      { path: '/world/rating/:conceptSlug', route: '/world/rating/unemployment-rate?cols=hicp-index' },
    );

    // Колонки: место, страна, значение, инфляция, период.
    await waitFor(() => {
      const head = headRow();
      expect(within(head).getAllByRole('columnheader')).toHaveLength(5);
    });
    expect(screen.queryByRole('link', { name: 'Создать аккаунт' })).toBeNull();
  });

  it('переводит карту в текущее направление сортировки (colorDirection)', async () => {
    mockApiGet(ratingMocks());
    const WorldMap = (await import('../components/WorldMap')).default;

    renderPage(
      <WorldRatingPage />,
      { path: '/world/rating/:conceptSlug', route: '/world/rating/unemployment-rate' },
    );

    await waitFor(() => expect(dataRows()).toHaveLength(2));

    // Смысловой asc у безработицы → карта asc.
    expect(WorldMap).toHaveBeenCalledWith(
      expect.objectContaining({ colorDirection: 'asc' }),
      undefined,
    );

    // Клик по базовой колонке: первый фиксирует смысловой порядок,
    // второй разворачивает — карта инвертируется.
    const baseHeader = screen
      .getAllByRole('columnheader')
      .find((node) => node.textContent.includes('Значение'));
    fireEvent.click(within(baseHeader).getAllByRole('button')[0]);
    fireEvent.click(within(baseHeader).getAllByRole('button')[0]);
    expect(WorldMap).toHaveBeenLastCalledWith(
      expect.objectContaining({ colorDirection: 'desc' }),
      undefined,
    );
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
    const head = headRow();
    expect(within(head).getAllByRole('columnheader')).toHaveLength(5);
    // Шапка доп-колонки несёт единицу измерения своего концепта.
    expect(within(head).getByText(/Инфляция, %/)).toBeTruthy();
    // Значения инфляции взяты из 2025 — ближайшего опубликованного года к базе 2026
    // (сортировка по безработице desc: Франция 7,0 выше Германии 3,4).
    expect(within(dataRows()[0]).getByText('Франция')).toBeTruthy();
    await waitFor(() => {
      expect(dataRows()[0].textContent).toMatch(/1[.,]10/);
      expect(dataRows()[1].textContent).toMatch(/2[.,]20/);
    });
  });
});
