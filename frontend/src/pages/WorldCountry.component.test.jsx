import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import WorldCountry from './WorldCountry';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/WorldMap', () => ({
  CountrySilhouette: () => <div data-testid="silhouette-stub">map</div>,
}));

afterEach(() => vi.restoreAllMocks());

const US_COUNTRY = {
  country: {
    code: 'US',
    slug: 'united-states',
    name: 'США',
    name_en: 'United States',
    region: 'Америка',
    indicators_count: 1,
  },
  categories: [
    {
      name: 'Рынок труда',
      count: 1,
      indicators: [
        {
          code: 'us-unemployment',
          name: 'Уровень безработицы',
          unit: '%',
          frequency: 'monthly',
          frequencies: ['monthly'],
          last_value: 4.1,
          last_date: '2026-06-01',
        },
      ],
    },
  ],
  overview: [],
  coverage: {
    history_start: '2024-01-01',
    history_end: '2026-06-01',
    frequencies: ['monthly'],
  },
  market_indicators: [
    {
      code: 'ust-10y',
      name: 'Доходность 10-летних гособлигаций США',
      name_en: 'U.S. 10-year Treasury yield',
      unit: '%',
      last_value: 4.25,
      last_date: '2026-08-21',
      frequency: 'daily',
    },
    {
      code: 'usd-index',
      name: 'Индекс доллара США',
      name_en: 'Broad U.S. Dollar Index',
      unit: 'пунктов',
      last_value: 120.1,
      last_date: '2026-08-21',
      frequency: 'daily',
    },
  ],
};

const GERMANY = {
  ...US_COUNTRY,
  country: {
    code: 'DE',
    slug: 'germany',
    name: 'Германия',
    name_en: 'Germany',
    region: 'Европа',
    indicators_count: 1,
  },
  market_indicators: [],
};

function renderCountry(slug, payload) {
  mockApiGet([
    ['/auth/me', { user: null }],
    [`/world/countries/${slug}`, payload],
  ]);
  return renderPage(<WorldCountry />, {
    path: '/:countrySlug',
    route: `/${slug}`,
  });
}

describe('WorldCountry market indicators', () => {
  it('показывает блок «Мировые рынки» со ссылками в общий каталог', async () => {
    renderCountry('united-states', US_COUNTRY);

    const heading = await screen.findByRole('heading', { name: 'Мировые рынки' });
    expect(heading).toBeTruthy();

    const ust = await screen.findByRole('link', {
      name: /Доходность 10-летних гособлигаций США/,
    });
    expect(ust.getAttribute('href')).toBe('/russia/indicator/ust-10y');

    const usd = screen.getByRole('link', { name: /Индекс доллара США/ });
    expect(usd.getAttribute('href')).toBe('/russia/indicator/usd-index');

    const une = screen.getByRole('link', { name: /Уровень безработицы/ });
    expect(une.getAttribute('href')).toBe('/united-states/indicator/us-unemployment');
  });

  it('не рендерит блок, если привязанных рядов нет', async () => {
    renderCountry('germany', GERMANY);

    await screen.findByRole('heading', { name: 'Рынок труда' });
    expect(screen.queryByRole('heading', { name: 'Мировые рынки' })).toBeNull();
    expect(screen.queryByTestId('country-market-indicators')).toBeNull();
  });
});

describe('WorldCountry empty states', () => {
  it('пустой каталог ведёт к списку стран, а не на /world', async () => {
    renderCountry('germany', {
      ...GERMANY,
      country: { ...GERMANY.country, indicators_count: 0 },
      categories: [],
      overview: [],
      market_indicators: [],
    });

    expect(await screen.findByText(/Пока нет опубликованных показателей/)).toBeTruthy();
    const link = screen.getByRole('link', { name: 'К списку стран' });
    expect(link.getAttribute('href')).toBe('/#countries');
  });

  it('пустой поиск сбрасывается кнопкой из i18n', async () => {
    renderCountry('germany', GERMANY);
    await screen.findByRole('heading', { name: 'Рынок труда' });

    fireEvent.change(screen.getByLabelText('Поиск по показателям страны'), {
      target: { value: 'qqqq' },
    });
    expect(await screen.findByText(/По запросу «qqqq» ничего не найдено/)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Сбросить поиск' }));
    expect(await screen.findByRole('heading', { name: 'Рынок труда' })).toBeTruthy();
  });
});
