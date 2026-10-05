import { describe, it, expect, afterEach, vi } from 'vitest';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import WorldRatingPage from './WorldRatingPage';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/PlanetView', () => ({
  default: vi.fn(() => <div data-testid="world-map-stub">map</div>),
}));

afterEach(() => { vi.restoreAllMocks(); vi.clearAllMocks(); });

async function planetProps() {
  const PlanetView = (await import('../components/PlanetView')).default;
  return PlanetView.mock.calls.at(-1)?.[0];
}

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

    expect(screen.getByText(/Страны без данных за 2025/i)).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Италия' })).toBeTruthy();
    expect(screen.queryByText('Стран с данными')).toBeNull();
    expect(screen.queryByText('Всего стран')).toBeNull();
    expect(screen.queryByText('Доступно лет')).toBeNull();
    const table = document.querySelector('#rating-table');
    expect(within(table).getByRole('button', { name: 'Год: 2025' })).toBeTruthy();
    expect(within(table).getByRole('button', { name: 'По убыванию' })).toBeTruthy();

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
    // Список у планеты остаётся рейтингом базовой безработицы: сортировка
    // дополнительной колонки таблицы не подменяет показатель этого списка.
    expect((await planetProps()).rankingItems).toMatchObject([
      { country_code: 'DE', rank: 1, value: 3.1 },
      { country_code: 'FR', rank: 2, value: 7.2 },
    ]);
    expect((await planetProps()).ratingHref).toBe('#rating-table');
    expect((await planetProps()).conceptSlug).toBe('unemployment-rate');

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

  it('на телефоне показывает карточки «место, флаг, страна, значение с единицей» вместо таблицы со спрятанным значением', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((media) => ({
      matches: media.includes('max-width: 639px'), media, addEventListener() {}, removeEventListener() {},
    }));
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
        concepts: [{ slug: 'unemployment-rate', name: 'Уровень безработицы', unit: '%', default_sort: 'asc' }],
        total: 1,
      }],
      [/^\/world\/compare\/map-series\/unemployment-rate/, {
        concept: { slug: 'unemployment-rate', name: 'Уровень безработицы', unit: '%' },
        years: [2025],
        values_by_year: {
          2025: {
            DE: { country_code: 'DE', country_slug: 'germany', country_name: 'Германия', indicator_code: 'de-une', date: '2025-06-01', value: 3.1, unit: '%' },
            FR: { country_code: 'FR', country_slug: 'france', country_name: 'Франция', indicator_code: 'fr-une', date: '2025-06-01', value: 7.4, unit: '%' },
          },
        },
        benchmark_by_year: {},
      }],
    ]);
    renderPage(<WorldRatingPage />, { path: '/world/rating/:conceptSlug', route: '/world/rating/unemployment-rate' });
    await waitFor(() => expect(document.querySelectorAll('.w2-rank-item')).toHaveLength(2));
    // Таблицы нет, значение и единица стоят рядом со страной в одной строке.
    expect(document.querySelector('#rating-table table')).toBeNull();
    const first = document.querySelectorAll('.w2-rank-row')[0];
    const text = first.textContent.replace(/\u00A0/g, ' ');
    expect(text).toContain('1');
    expect(text).toContain('Германия');
    expect(text).toContain('3,1');
    expect(text).toContain('%');
    expect(first.querySelector('.fe-flag')).toBeTruthy();
    // Технические фразы убраны с экрана.
    const page = document.body.textContent;
    expect(page).not.toMatch(/Медиана по|В таблице участвуют|для цен на карте/i);
    expect(document.body.textContent).not.toContain('\u00B7');
  });

  it('скрывает карточку «Страны без данных», когда без данных никого нет, и прячет нехватающих под раскрывающийся блок', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators/, []],
      [/^\/world\/countries/, {
        countries: [
          { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', indicators_count: 10 },
          { code: 'FR', slug: 'france', name: 'Франция', name_en: 'France', indicators_count: 10 },
        ],
        total: 2,
      }],
      [/^\/world\/rating\/concepts/, {
        concepts: [{ slug: 'unemployment-rate', name: 'Уровень безработицы', unit: '%', default_sort: 'asc' }],
        total: 1,
      }],
      [/^\/world\/compare\/map-series\/unemployment-rate/, {
        concept: { slug: 'unemployment-rate', name: 'Уровень безработицы', unit: '%' },
        years: [2025],
        values_by_year: {
          2025: {
            DE: { country_code: 'DE', country_slug: 'germany', country_name: 'Германия', indicator_code: 'de-une', date: '2025-06-01', value: 3.1, unit: '%' },
            FR: { country_code: 'FR', country_slug: 'france', country_name: 'Франция', indicator_code: 'fr-une', date: '2025-06-01', value: 7.4, unit: '%' },
          },
        },
        benchmark_by_year: {},
      }],
    ]);
    renderPage(<WorldRatingPage />, { path: '/world/rating/:conceptSlug', route: '/world/rating/unemployment-rate' });
    await waitFor(() => expect(dataRows()).toHaveLength(2));
    expect(screen.queryByText(/Страны без данных/)).toBeNull();
    expect(screen.queryByText(/Все страны мирового каталога имеют значение/)).toBeNull();
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
    const WorldMap = (await import('../components/PlanetView')).default;

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

  it('EN: крошки, страны и единица без русского, даже если map-series отдал RU', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators/, []],
      [/^\/world\/countries/, {
        countries: [
          { code: 'US', slug: 'united-states', name: 'США', name_en: 'United States', indicators_count: 10 },
          { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', indicators_count: 10 },
        ],
        total: 2,
      }],
      [/^\/world\/rating\/concepts/, {
        concepts: [
          { slug: 'gdp-usd', name: 'GDP in current US dollars', unit: 'млрд $', default_sort: 'desc' },
        ],
        total: 1,
      }],
      [/^\/world\/compare\/map-series\/gdp-usd/, {
        concept: { slug: 'gdp-usd', name: 'GDP in current US dollars', unit: 'млрд $' },
        years: [2025],
        values_by_year: {
          2025: {
            US: {
              country_code: 'US',
              country_slug: 'united-states',
              country_name: 'США',
              date: '2025-01-01',
              value: 5048.1,
              unit: 'млрд $',
            },
            DE: {
              country_code: 'DE',
              country_slug: 'germany',
              country_name: 'Германия',
              date: '2025-01-01',
              value: 4435.2,
              unit: 'млрд $',
            },
          },
        },
      }],
    ]);

    renderPage(
      <WorldRatingPage />,
      { path: '/world/rating/:conceptSlug', route: '/world/rating/gdp-usd', locale: 'en' },
    );

    await waitFor(() => expect(dataRows()).toHaveLength(2));
    expect(screen.getByText('Home')).toBeTruthy();
    expect(screen.getAllByText('Country rankings').length).toBeGreaterThan(0);
    expect(screen.queryByText('Главная')).toBeNull();
    expect(screen.getByRole('link', { name: 'United States' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Germany' })).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'США' })).toBeNull();
    expect(screen.getByText(/Billion \$/)).toBeTruthy();
    expect(dataRows()[0].textContent).toMatch(/5[,\u00A0 ]?048/);
  });
});

it('сохраняет год из быстрой ссылки и переключает фактический год рейтинга', async () => {
  const point = (value, year) => ({ country_code: 'DE', country_slug: 'germany', country_name: 'Германия',
    indicator_code: 'de-weo-ngdpd', date: `${year}-01-01`, value, unit: 'USD' });
  mockApiGet([
    ['/auth/me', { user: null }], [/^\/indicators/, []],
    [/^\/world\/countries/, { countries: [{ code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany' }], total: 1 }],
    [/^\/world\/rating\/concepts/, { concepts: [{ slug: 'gdp-usd', name: 'ВВП', unit: 'USD' }], total: 1 }],
    [/^\/world\/compare\/map-series\/gdp-usd/, { concept: { slug: 'gdp-usd', name: 'ВВП', unit: 'USD' },
      years: [2024, 2025], values_by_year: { 2024: { DE: point(4100, 2024) }, 2025: { DE: point(4900, 2025) } }, benchmark_by_year: {} }],
  ]);
  renderPage(<WorldRatingPage />, { path: '/world/rating/:conceptSlug', route: '/world/rating/gdp-usd?view=interactive&year=2024#chart' });
  await waitFor(async () => expect((await planetProps())?.year).toBe(2024));
  expect((await planetProps()).years).toEqual([2024, 2025]);
  expect((await planetProps()).rankingItems).toMatchObject([{ country_code: 'DE', value: 4100 }]);
  const table = () => within(document.querySelector('#rating-table'));
  expect(table().getByRole('button', { name: 'Год: 2024' })).toBeTruthy();
  expect(document.querySelector('link[rel=canonical]').href).toMatch(/\/world\/rating\/gdp-usd\/2024$/);
  expect(document.querySelector('meta[property="og:image"]').content).toMatch(/\/2024\.png$/);
  const changeYear = (await planetProps()).onYearChange;
  act(() => changeYear(2025));
  await waitFor(async () => expect((await planetProps())?.year).toBe(2025));
  expect(table().getByRole('button', { name: 'Год: 2025' })).toBeTruthy();
  expect((await planetProps()).rankingItems).toMatchObject([{ country_code: 'DE', value: 4900 }]);
  expect(document.querySelector('link[rel=canonical]').href).toMatch(/\/world\/rating\/gdp-usd$/);
  fireEvent.click(table().getByRole('button', { name: 'Год: 2025' }));
  fireEvent.click(table().getByRole('option', { name: '2024' }));
  await waitFor(async () => expect((await planetProps())?.year).toBe(2024));
  expect(screen.queryByTestId('map-timeline-stub')).toBeNull();
});

it('смена года планеты сохраняет нулевую Россию и пустое российское наблюдение', async () => {
  const point = (code, slug, value, year) => ({
    country_code: code, country_slug: slug, country_name: code === 'RU' ? 'Россия' : 'Германия',
    indicator_code: code === 'RU' ? 'unemployment' : 'de-une',
    date: `${year}-06-01`, value, unit: '%',
  });
  mockApiGet([
    ['/auth/me', { user: null }], [/^\/indicators/, []],
    [/^\/world\/countries/, { countries: [{ code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany' }] }],
    [/^\/world\/rating\/concepts/, { concepts: [{ slug: 'unemployment-rate', name: 'Безработица', unit: '%', default_sort: 'asc' }] }],
    [/^\/world\/compare\/map-series\//, {
      concept: { slug: 'unemployment-rate', unit: '%', russia: { eligible: true, indicator_code: 'unemployment' } },
      years: [2024, 2025],
      values_by_year: {
        2024: { DE: point('DE', 'germany', 3.1, 2024) },
        2025: { DE: point('DE', 'germany', 3.2, 2025), RU: point('RU', 'russia', 0, 2025) },
      },
      benchmark_by_year: { 2025: { value: 0, label: 'Сравнимое значение' } },
    }],
  ]);
  renderPage(<WorldRatingPage />, { path: '/world/rating/:conceptSlug', route: '/world/rating/unemployment-rate' });
  await waitFor(async () => expect((await planetProps())?.year).toBe(2025));
  expect((await planetProps()).rankingItems[0]).toMatchObject({ country_code: 'RU', value: 0, rank: 1 });
  expect((await planetProps()).benchmark).toEqual({ value: 0, label: 'Сравнимое значение' });
  const changeYear = (await planetProps()).onYearChange;
  act(() => changeYear(2024));
  await waitFor(async () => expect((await planetProps())?.year).toBe(2024));
  const props = await planetProps();
  expect(props.countries.some((country) => country.code === 'RU')).toBe(true);
  expect(props.valuesByCode.has('RU')).toBe(false);
  expect(props.detailsByCode.has('RU')).toBe(false);
  expect(props.rankingItems).toMatchObject([{ country_code: 'DE', value: 3.1, rank: 1 }]);
  expect(props.benchmark).toBeUndefined();
  expect(dataRows()).toHaveLength(1);
  expect(screen.getByRole('link', { name: 'Россия' }).getAttribute('href')).toBe('/russia/indicator/unemployment');
});
