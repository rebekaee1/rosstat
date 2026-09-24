import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import WorldRegionsHome from './WorldRegionsHome';
import WorldRegionProfile from './WorldRegionProfile';
import WorldRegionIndicatorPage from './WorldRegionIndicatorPage';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/RegionsMap', () => ({
  default: () => <div data-testid="map-stub">map</div>,
}));
vi.mock('../components/MapTimeline', () => ({
  default: ({ year, onYearChange }) => (
    <button type="button" data-testid="timeline-stub" onClick={() => onYearChange(2023)}>
      timeline {year}
    </button>
  ),
}));
vi.mock('../components/RegionAnnualChart', () => ({
  default: () => <div data-testid="chart-stub">chart</div>,
}));

afterEach(() => vi.restoreAllMocks());

const HUB = {
  country: { code: 'US', slug: 'united-states', name: 'США', name_en: 'United States' },
  kind_label: 'Штат',
  kind_label_plural: 'Штаты',
  default_indicator: 'unemployment-rate',
  map_id: 'us-states',
  totals: { regions: 2, indicators: 2 },
  regions: [
    { slug: 'california', name: 'Калифорния', name_en: 'California' },
    { slug: 'new-york', name: 'Нью-Йорк', name_en: 'New York' },
  ],
  indicators: [
    { code: 'unemployment-rate', name: 'Безработица', section: 'Труд', unit: '%' },
    { code: 'real-gdp', name: 'ВРП', section: 'Счета', unit: 'млн $' },
  ],
  sections: [
    { num: 1, name: 'Труд', indicators: [{ code: 'unemployment-rate', name: 'Безработица' }] },
  ],
};

const MAP = {
  indicator: { code: 'unemployment-rate', name: 'Безработица', unit: '%', better_is_low: true },
  period: '2024-02',
  periods: [
    { key: '2024-02', label: 'февраль 2024' },
    { key: '2023-02', label: 'февраль 2023' },
  ],
  values: [
    { slug: 'new-york', name: 'Нью-Йорк', value: 4.2, rank: 1 },
    { slug: 'california', name: 'Калифорния', value: 5.0, rank: 2 },
  ],
};

const PROFILE = {
  country: { code: 'US', slug: 'united-states', name: 'США', name_en: 'United States' },
  region: { slug: 'california', name: 'Калифорния', name_en: 'California' },
  kind_label: 'Штат',
  kind_label_plural: 'Штаты',
  catalog_total: 3,
  available_total: 2,
  indicators: [
    {
      code: 'unemployment-rate', name: 'Безработица', label: 'Безработица',
      unit: '%', value: 5, prev_value: 5.1, year: 2024, period_label: 'февраль 2024',
      section: 'Труд', rank: 2, of: 2,
    },
    {
      code: 'real-gdp', name: 'ВРП', label: 'ВРП',
      unit: 'млн $', value: 3000000, prev_value: null, year: 2023, period_label: '2023',
      section: 'Счета', rank: 1, of: 2,
    },
    { code: 'unavailable', name: 'Нет данных', section: 'Цены', value: null },
  ],
  sections: [
    { num: 1, name: 'Труд', indicators: [
      {
        code: 'unemployment-rate', name: 'Безработица', unit: '%', value: 5,
        prev_value: 5.1, year: 2024, period_label: 'февраль 2024',
      },
    ] },
    { num: 2, name: 'Счета', indicators: [
      {
        code: 'real-gdp', name: 'ВРП', unit: 'млн $', value: 3000000,
        year: 2023, period_label: '2023',
      },
    ] },
    { num: 3, name: 'Цены', indicators: [
      { code: 'unavailable', name: 'Нет данных', value: null },
    ] },
  ],
};

const SERIES = {
  country: { code: 'US', slug: 'united-states', name: 'США', name_en: 'United States' },
  region: { slug: 'california', name: 'Калифорния' },
  kind_label: 'Штат',
  kind_label_plural: 'Штаты',
  indicator: {
    code: 'unemployment-rate',
    name: 'Безработица',
    unit: '%',
    frequency: 'monthly',
    section: 'Труд',
    description: 'Доля безработных.',
    methodology: 'Обследование рабочей силы.',
    source: 'BLS',
    national_code: 'us-unemployment-rate',
    better_is_low: true,
  },
  series: [
    { date: '2024-01-01', value: 5.1, year: 2024, month: 1, label: '2024-01' },
    { date: '2024-02-01', value: 5.0, year: 2024, month: 2, label: '2024-02' },
  ],
  national: {
    code: 'us-unemployment-rate',
    name: 'США',
    series: [
      { date: '2024-01-01', value: 3.7, year: 2024, month: 1, label: '2024-01' },
      { date: '2024-02-01', value: 3.9, year: 2024, month: 2, label: '2024-02' },
    ],
  },
  siblings: [{ code: 'real-gdp', name: 'ВРП' }],
  rank: {
    position: 2,
    total: 2,
    year: 2024,
    rank_as_achievement: true,
    top: [
      { slug: 'new-york', name: 'Нью-Йорк', value: 4.2, rank: 1 },
      { slug: 'california', name: 'Калифорния', value: 5.0, rank: 2 },
    ],
  },
  of: 2,
  last_value: 5,
  last_period_label: 'февраль 2024',
};

function mockWorld(extra = []) {
  return mockApiGet([
    ['/auth/me', { user: null }],
    ['/world/united-states/regions', HUB],
    [/\/world\/united-states\/regions\/map\//, MAP],
    ['/world/united-states/regions/region/california', PROFILE],
    ['/world/united-states/regions/region/california/unemployment-rate', SERIES],
    ...extra,
  ]);
}

describe('WorldRegionsHome', () => {
  it('список штатов в том же каркасе, что регионы России: поиск и вкладка карта', async () => {
    mockWorld();
    renderPage(<WorldRegionsHome />, {
      path: '/:countrySlug/regions',
      route: '/united-states/regions',
    });

    expect(await screen.findByRole('heading', { name: 'Штаты США' })).toBeTruthy();
    expect((await screen.findAllByRole('link', { name: /Калифорния/ }))[0].getAttribute('href'))
      .toBe('/united-states/region/california');
    expect(screen.getByPlaceholderText('Найти территорию…')).toBeTruthy();
  });

  it('карта открывается с чипами показателя и графиком-хороплетом', async () => {
    mockWorld();
    renderPage(<WorldRegionsHome />, {
      path: '/:countrySlug/region/map/:code',
      route: '/united-states/region/map/unemployment-rate',
    });

    expect(await screen.findByTestId('map-stub')).toBeTruthy();
    expect(screen.getByRole('tab', { name: 'Обзор' })).toBeTruthy();
    expect(screen.getByRole('tab', { name: 'Безработица' })).toBeTruthy();
    expect(screen.getByLabelText('Скачать карту картинкой')).toBeTruthy();
  });

  it('сохраняет ползунок при загрузке следующего года во время перетаскивания', async () => {
    const get = mockWorld();
    const original = get.getMockImplementation();
    get.mockImplementation((url, options) => {
      if (url.includes('/regions/map/') && options?.params?.period === '2023-02') {
        return new Promise(() => {});
      }
      return original(url, options);
    });
    renderPage(<WorldRegionsHome />, {
      path: '/:countrySlug/region/map/:code',
      route: '/united-states/region/map/unemployment-rate',
    });

    fireEvent.click(await screen.findByTestId('timeline-stub'));
    await waitFor(() => expect(get).toHaveBeenCalledWith(
      '/world/united-states/regions/map/unemployment-rate', { params: { period: '2023-02' } },
    ));
    expect(screen.getByTestId('timeline-stub')).toBeTruthy();
  });
});

describe('WorldRegionProfile', () => {
  it('темы слева и строки показателей как у региона РФ', async () => {
    mockWorld();
    renderPage(<WorldRegionProfile />, {
      path: '/:countrySlug/region/:slug',
      route: '/united-states/region/california',
    });

    expect(await screen.findByRole('heading', { name: 'Калифорния' })).toBeTruthy();
    expect(screen.getAllByRole('button', { name: /ВВП и производство/ }).length).toBeGreaterThan(0);
    expect(screen.getByText(/2 показателя в 2 разделах/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /^Цены/ })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /Труд и зарплаты/ }));
    expect(screen.getAllByRole('link', { name: /Безработица/ })[0].getAttribute('href'))
      .toBe('/united-states/region/california/unemployment-rate');
  });
});

describe('WorldRegionIndicatorPage', () => {
  it('график с сравнением, рядом страны и выгрузками как у региона РФ', async () => {
    mockWorld();
    renderPage(<WorldRegionIndicatorPage />, {
      path: '/:countrySlug/region/:slug/:code',
      route: '/united-states/region/california/unemployment-rate',
    });

    expect(await screen.findByRole('heading', { name: 'Безработица' })).toBeTruthy();
    expect(screen.getByTestId('chart-stub')).toBeTruthy();
    expect(screen.getByLabelText('Сравнить с другой территорией')).toBeTruthy();
    expect(screen.getByRole('button', { name: /США/ })).toBeTruthy();
    expect(screen.getByLabelText('Скачать CSV')).toBeTruthy();
    expect(screen.getByLabelText('Скачать Excel')).toBeTruthy();
    expect(screen.getByLabelText('Скачать график картинкой')).toBeTruthy();
    expect(screen.getByText('Таблица значений по годам')).toBeTruthy();
    expect(screen.getByRole('link', { name: /Сравнить с США/ }).getAttribute('href'))
      .toBe('/compare?codes=w:united-states:us-unemployment-rate,s:united-states:california:unemployment-rate');
  });
});
