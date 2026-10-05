import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import { useLocation } from 'react-router-dom';
import WorldRatingPage from './WorldRatingPage';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/PlanetView', () => ({
  default: vi.fn(() => <div data-testid="world-map-stub">map</div>),
}));

afterEach(() => { vi.restoreAllMocks(); vi.clearAllMocks(); });

const CODES = ['US', 'CN', 'DE', 'JP', 'IN', 'GB', 'FR', 'IT', 'BR', 'CA', 'RU', 'KR', 'AU', 'ES', 'MX', 'ID'];
const NAMES = {
  US: 'США', CN: 'Китай', DE: 'Германия', JP: 'Япония', IN: 'Индия', GB: 'Великобритания', FR: 'Франция', IT: 'Италия',
  BR: 'Бразилия', CA: 'Канада', RU: 'Россия', KR: 'Южная Корея', AU: 'Австралия', ES: 'Испания', MX: 'Мексика', ID: 'Индонезия',
};
const ENGLISH = {
  US: 'United States', CN: 'China', DE: 'Germany', JP: 'Japan', IN: 'India', GB: 'United Kingdom', FR: 'France', IT: 'Italy',
  BR: 'Brazil', CA: 'Canada', RU: 'Russia', KR: 'South Korea', AU: 'Australia', ES: 'Spain', MX: 'Mexico', ID: 'Indonesia',
};

function point(code, year, value, { english = false } = {}) {
  return {
    country_code: code,
    country_slug: ENGLISH[code].toLowerCase().replace(/ /g, '-'),
    country_name: english ? ENGLISH[code] : NAMES[code],
    indicator_code: `${code.toLowerCase()}-gdp`,
    date: `${year}-01-01`,
    value,
    unit: english ? 'billion $' : 'млрд $',
    ...(code === 'RU' ? { source: 'Rosstat, Bank of Russia' } : {}),
  };
}

/** Страна i в году y: значение убывает с индексом, у последних двух места меняются между 2020 и 2025. */
function mapSeries({ english = false } = {}) {
  const years = [2020, 2021, 2022, 2023, 2024, 2025];
  const values_by_year = {};
  for (const year of years) {
    values_by_year[year] = {};
    CODES.forEach((code, index) => {
      let value = 5000 - index * 250 + (year - 2020) * 10;
      if (year === 2025 && code === 'ID') value = 4900; // Индонезия поднимается на второе место
      values_by_year[year][code] = point(code, year, value, { english });
    });
  }
  return {
    concept: { slug: 'gdp-usd', name: 'ВВП', unit: english ? 'billion $' : 'млрд $' },
    years,
    values_by_year,
    benchmark_by_year: { 2025: { value: 3100, label: 'Медиана по 16 странам с данными', countries_count: 16 } },
  };
}

function concepts() {
  return {
    concepts: [
      { slug: 'gdp-usd', name: 'ВВП', unit: 'млрд $', default_sort: 'desc' },
      { slug: 'gdp-per-capita-usd', name: 'ВВП на душу', unit: '$ на человека', default_sort: 'desc' },
      { slug: 'gdp-per-capita-eu', name: 'ВВП на душу к ЕС', unit: '% от среднего по ЕС на душу населения', default_sort: 'desc' },
      { slug: 'hicp-index', name: 'Инфляция', unit: '%', default_sort: 'desc' },
      { slug: 'unemployment-rate', name: 'Безработица', unit: '%', default_sort: 'asc' },
      { slug: 'population', name: 'Население', unit: 'человек', default_sort: 'desc' },
      { slug: 'government-debt-gdp', name: 'Госдолг', unit: '% ВВП', default_sort: 'desc' },
      { slug: 'budget-balance-gdp', name: 'Баланс бюджета', unit: '% ВВП', default_sort: 'desc' },
    ],
    total: 8,
  };
}

function baseMocks(options) {
  return [
    ['/auth/me', { user: null }],
    [/^\/indicators/, []],
    [/^\/world\/countries/, {
      countries: CODES.map((code) => ({
        code, slug: ENGLISH[code].toLowerCase().replace(/ /g, '-'), name: NAMES[code], name_en: ENGLISH[code], indicators_count: 5,
      })),
      total: CODES.length,
    }],
    [/^\/world\/rating\/concepts/, concepts()],
    [/^\/world\/compare\/map-series\/gdp-usd/, mapSeries(options)],
    [/^\/world\/compare\/map-series\/hicp-index/, {
      ...mapSeries(options),
      concept: { slug: 'hicp-index', name: 'Инфляция', unit: '%' },
      years: [2019, 2020, 2021, 2022, 2023, 2024],
    }],
  ];
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="loc">{location.pathname + location.search}</output>;
}

function renderRating(route, options = {}) {
  mockApiGet(baseMocks(options));
  return renderPage(
    <><WorldRatingPage /><LocationProbe /></>,
    { path: '/world/rating/:conceptSlug/:year?', route, ...options },
  );
}

describe('WorldRatingPage, раунд 2 (зона Z6)', () => {
  it('выбор показателя: кнопка «Другой показатель» без счётчика, справка подписана словами', async () => {
    renderRating('/world/rating/gdp-usd');
    await screen.findByTestId('world-map-stub');
    const other = await screen.findByRole('button', { name: 'Другой показатель' });
    expect(other.textContent).not.toMatch(/\(\d+\)/);
    expect(screen.getByRole('button', { name: 'Что это за показатель' })).toBeTruthy();
    // справка стоит в той же строке выбора, а не отдельной строкой под плитой
    expect(document.querySelector('.z6-toolbar .z6-picker__trailing')).toBeTruthy();
  });

  it('раскладка: таблица и итоги слева, шар справа, а у шара нет дубля списка стран', async () => {
    renderRating('/world/rating/gdp-usd');
    await screen.findByTestId('world-map-stub');
    const main = document.querySelector('.z6-main');
    const side = document.querySelector('.z6-side');
    expect(main.querySelector('#rating-table')).toBeTruthy();
    expect(main.querySelector('.z6-toolbar')).toBeTruthy();
    expect(main.querySelector('.z6-ribbon')).toBeTruthy();
    expect(side.querySelector('#chart [data-testid="world-map-stub"]')).toBeTruthy();
    expect(main.querySelector('#chart')).toBeNull();
    // «Как изменились места» живёт под шаром, в узком варианте
    const shifts = side.querySelector('.w6d-shifts--compact');
    expect(shifts).toBeTruthy();
    expect(shifts.querySelectorAll('.w6d-shifts__col.is-up .w6d-shift').length).toBeLessThanOrEqual(3);
  });

  it('таблица: без колонки «Период», период под заголовком, у лидеров тёплая подсветка, у полосок значение доли', async () => {
    renderRating('/world/rating/gdp-usd');
    await screen.findByTestId('world-map-stub');
    await waitFor(() => expect(document.querySelectorAll('#rating-table tbody tr')).toHaveLength(12));
    const head = document.querySelector('#rating-table thead');
    expect(within(head).queryByText('Период')).toBeNull();
    expect(document.querySelector('.z6-table__sub').textContent).toBe('Данные за 2025');
    const rows = [...document.querySelectorAll('#rating-table tbody tr')];
    expect(rows.slice(0, 3).map((row) => row.getAttribute('data-top'))).toEqual(['1', '2', '3']);
    expect(rows[3].hasAttribute('data-top')).toBe(false);
    const share = (row) => Number(row.querySelector('.w6d-bar').style.getPropertyValue('--z6-s'));
    expect(share(rows[0])).toBeCloseTo(1, 2);
    expect(share(rows[8])).toBeLessThan(share(rows[0]));
    expect(rows[0].querySelector('[title="Период: 2025"]')).toBeTruthy();
    expect(document.querySelector('.z6-table-card').hasAttribute('data-scroll')).toBe(false);
  });

  it('золотая лента показывает первое и последнее место и стоит над таблицей', async () => {
    renderRating('/world/rating/gdp-usd');
    await screen.findByTestId('world-map-stub');
    const ribbon = document.querySelector('.z6-ribbon');
    expect(within(ribbon).getByText('Первое место').closest('a').getAttribute('data-place')).toBe('first');
    expect(within(ribbon).getByText('Последнее место').closest('a').getAttribute('data-place')).toBe('last');
    expect(ribbon.compareDocumentPosition(document.querySelector('#rating-table')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('с дополнительной колонкой таблица остаётся прокручиваемой (шапка не липнет, но ничего не обрезается)', async () => {
    renderRating('/world/rating/gdp-usd?cols=hicp-index');
    await screen.findByTestId('world-map-stub');
    await waitFor(() => expect(document.querySelectorAll('#rating-table tbody tr').length).toBeGreaterThan(0));
    expect(document.querySelector('.z6-table-card').getAttribute('data-scroll')).toBe('x');
  });
});
