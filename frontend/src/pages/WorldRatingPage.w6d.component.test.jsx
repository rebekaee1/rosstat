import { describe, it, expect, afterEach, vi } from 'vitest';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
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

describe('WorldRatingPage, волна 6 (зона D)', () => {
  it('заголовок короткий, подзаголовок поясняет единицу, а слово «планета» из подсказки ушло', async () => {
    renderRating('/world/rating/gdp-usd');
    expect(await screen.findByRole('heading', { level: 1, name: 'ВВП по странам, 2025' })).toBeTruthy();
    expect(screen.getByText('в текущих долларах США')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/планета/i);
    expect(document.body.textContent).toMatch(/Крутите шар, выбирайте год, сравнивайте страны/);
  });

  it('показывает все показатели группами, с поиском, а «ВВП на душу к ЕС» называется понятно', async () => {
    renderRating('/world/rating/gdp-usd');
    await screen.findByTestId('world-map-stub');
    const open = await screen.findByRole('button', { name: /Все показатели \(8\)/ });
    fireEvent.click(open);
    const panel = document.querySelector('.w6d-picker__panel');
    expect(panel).toBeTruthy();
    for (const group of ['Экономика', 'Цены и работа', 'Деньги государства', 'Люди']) {
      expect(within(panel).getByRole('heading', { name: group })).toBeTruthy();
    }
    expect(within(panel).getByRole('link', { name: /ВВП на душу, % от среднего по ЕС/ })).toBeTruthy();
    expect(within(panel).queryByText('ВВП на душу к ЕС')).toBeNull();
    // Поиск по показателю
    fireEvent.change(within(panel).getByRole('searchbox'), { target: { value: 'безраб' } });
    expect(within(panel).getByRole('link', { name: /Безработица/ })).toBeTruthy();
    expect(within(panel).queryByRole('link', { name: /Население/ })).toBeNull();
  });

  it('при смене показателя ссылки сохраняют выбранный год', async () => {
    renderRating('/world/rating/gdp-usd/2022');
    await screen.findByTestId('world-map-stub');
    const link = (await screen.findAllByRole('link', { name: 'Инфляция' }))[0];
    expect(link.getAttribute('href')).toBe('/world/rating/hicp-index/2022');
  });

  it('выбор года обновляет постоянный адрес; год по умолчанию живёт на базовом адресе', async () => {
    renderRating('/world/rating/gdp-usd');
    await screen.findByTestId('world-map-stub');
    const PlanetView = (await import('../components/PlanetView')).default;
    const props = () => PlanetView.mock.calls.at(-1)[0];
    await waitFor(() => expect(props().year).toBe(2025));
    act(() => props().onYearChange(2021));
    await waitFor(() => expect(screen.getByTestId('loc').textContent).toBe('/world/rating/gdp-usd/2021'));
    expect(document.querySelector('link[rel=canonical]').href).toMatch(/\/world\/rating\/gdp-usd\/2021$/);
    act(() => props().onYearChange(2025));
    await waitFor(() => expect(screen.getByTestId('loc').textContent).toBe('/world/rating/gdp-usd'));
  });

  it('год без данных в адресе приводится к базовому адресу', async () => {
    renderRating('/world/rating/gdp-usd/2031');
    await waitFor(() => expect(screen.getByTestId('loc').textContent).toBe('/world/rating/gdp-usd'));
  });

  it('блок «Другие годы» даёт постоянные ссылки на каждый год', async () => {
    renderRating('/world/rating/gdp-usd');
    const heading = await screen.findByRole('heading', { name: 'Другие годы' });
    const links = within(heading.closest('section')).getAllByRole('link');
    expect(links.map((l) => l.getAttribute('href'))).toEqual([
      '/world/rating/gdp-usd/2024',
      '/world/rating/gdp-usd/2023',
      '/world/rating/gdp-usd/2022',
      '/world/rating/gdp-usd/2021',
      '/world/rating/gdp-usd/2020',
    ]);
  });

  it('показывает 12 строк и кнопку «Показать все страны», стрелку изменения и пояснение медианы', async () => {
    renderRating('/world/rating/gdp-usd');
    await screen.findByTestId('world-map-stub');
    await waitFor(() => expect(document.querySelectorAll('#rating-table tbody tr')).toHaveLength(12));
    const rows = document.querySelectorAll('#rating-table tbody tr');
    // США: 5050 против 5040 в прошлом году, +0,2 %
    expect(rows[0].textContent).toMatch(/\+0,2\s?%/);
    expect(document.body.textContent).toMatch(/Типичная страна: 3\s?100 млрд \$\. Половина стран ниже этого значения/);
    fireEvent.click(screen.getByRole('button', { name: /Показать все страны \(16\)/ }));
    await waitFor(() => expect(document.querySelectorAll('#rating-table tbody tr')).toHaveLength(16));
    fireEvent.click(screen.getByRole('button', { name: 'Свернуть список' }));
    await waitFor(() => expect(document.querySelectorAll('#rating-table tbody tr')).toHaveLength(12));
  });

  it('таблица сортируется по названию страны и по изменению к прошлому году', async () => {
    renderRating('/world/rating/gdp-usd');
    await screen.findByTestId('world-map-stub');
    const head = document.querySelector('#rating-table thead');
    const nameTh = within(head).getAllByRole('columnheader').find((th) => th.textContent.includes('Страна'));
    fireEvent.click(within(nameTh).getAllByRole('button')[0]);
    await waitFor(() => {
      const first = document.querySelector('#rating-table tbody tr td:nth-child(2)');
      expect(first.textContent).toContain('Австралия');
    });
    const changeTh = within(head).getAllByRole('columnheader').find((th) => th.textContent.includes('К прошлому году'));
    expect(changeTh).toBeTruthy();
    fireEvent.click(within(changeTh).getAllByRole('button')[0]);
    // Индонезия: скачок 2024 -> 2025 самый сильный
    await waitFor(() => {
      const first = document.querySelector('#rating-table tbody tr td:nth-child(2)');
      expect(first.textContent).toContain('Индонезия');
    });
  });

  it('показывает, как изменились места за 5 лет', async () => {
    renderRating('/world/rating/gdp-usd');
    const heading = await screen.findByRole('heading', { name: 'Как изменились места за 5 лет' });
    const block = heading.closest('section');
    expect(within(block).getByRole('heading', { name: 'Поднялись выше всех' })).toBeTruthy();
    expect(within(block).getAllByRole('link')[0].textContent).toBe('Индонезия');
    expect(block.textContent).toMatch(/было 16, стало 2/);
  });

  it('в русском интерфейсе названия стран, единицы и источник по-русски, даже если срез пришёл на английском', async () => {
    renderRating('/world/rating/gdp-usd', { english: true });
    await screen.findByTestId('world-map-stub');
    await waitFor(() => expect(document.querySelectorAll('#rating-table tbody tr').length).toBeGreaterThan(0));
    const first = document.querySelector('#rating-table tbody tr');
    expect(first.textContent).toContain('США');
    expect(first.textContent).not.toContain('United States');
    expect(document.body.textContent).toMatch(/млрд \$/);
    expect(document.body.textContent).not.toMatch(/billion \$/);
    const PlanetView = (await import('../components/PlanetView')).default;
    const details = PlanetView.mock.calls.at(-1)[0].detailsByCode;
    expect(details.get('RU').source).toBe('Росстат, Банк России');
    expect(details.get('US').country_name).toBe('США');
    expect(screen.getByText('Первое место').closest('a').textContent).toContain('США');
    expect(screen.getByText('Первое место').closest('a').textContent).toContain('млрд $');
  });
});
