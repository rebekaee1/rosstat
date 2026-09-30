import { describe, it, expect, afterEach, vi } from 'vitest';
import { act, screen, waitFor } from '@testing-library/react';
import { useLocation } from 'react-router-dom';
import HomeWorkbench from './HomeWorkbench';
import { renderPage, mockApiGet } from '../../test/renderPage';

vi.mock('../PlanetView', () => ({
  default: vi.fn(() => <div data-testid="world-map-stub">map</div>),
}));

afterEach(() => { vi.restoreAllMocks(); vi.clearAllMocks(); });

async function planetProps() {
  const PlanetView = (await import('../PlanetView')).default;
  return PlanetView.mock.calls.at(-1)?.[0];
}

function LocationProbe() {
  const { pathname } = useLocation();
  return <output data-testid="location-probe">{pathname}</output>;
}

const INDICATORS = [
  {
    code: 'cpi', name: 'Индекс потребительских цен', unit: '%', category: 'Цены',
    frequency: 'monthly', is_active: true, is_listed: true,
    current_value: 100.2, hero_value: 5.3, hero_unit: '%', change: 0.1,
  },
  {
    code: 'unemployment', name: 'Безработица', unit: '%', category: 'Рынок труда',
    frequency: 'monthly', is_active: true, is_listed: true, current_value: 2.3, change: -0.1,
  },
];

describe('HomeWorkbench', () => {
  it('передаёт рейтинг и годы одной панели планеты без нижних дубликатов', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators/, INDICATORS],
      ['/world/countries', {
        countries: [
          { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', indicators_count: 10 },
        ],
        total: 1,
      }],
      [/^\/world\/compare\/catalog/, {
        items: [{
          concept_slug: 'unemployment-rate',
          concept_name: 'Уровень безработицы',
          unit: '%',
        }],
        total: 1,
      }],
      [/^\/world\/rating\/concepts/, {
        concepts: [{
          slug: 'unemployment-rate',
          name: 'Уровень безработицы',
          unit: '%',
        }],
        total: 1,
      }],
      [/^\/world\/compare\/map-series\//, {
        years: [2024, 2025],
        values_by_year: {
          2025: {
            DE: {
              country_code: 'DE',
              country_slug: 'germany',
              country_name: 'Германия',
              value: 3.1,
            },
          },
        },
        concept: { name: 'Безработица', unit: '%' },
        benchmark_by_year: {},
      }],
    ]);

    renderPage(
      <HomeWorkbench
        ratingConcepts={{
          data: {
            concepts: [{ slug: 'unemployment-rate', name: 'Уровень безработицы', unit: '%' }],
          },
        }}
      />,
      { path: '/', route: '/' },
    );

    expect(screen.getByRole('heading', { name: 'Страны и показатели' })).toBeTruthy();
    // Боковые переходы сняты: разделы живут в меню, на главной остаётся витрина.
    expect(screen.queryByRole('navigation', { name: 'Переходы по разделам' })).toBeNull();
    expect(screen.queryByRole('link', { name: /Регионы России/i })).toBeNull();
    expect(screen.queryByRole('link', { name: /Показатели России/i })).toBeNull();
    // Поиск показателей на карте снят (owner 2026-08-28): глобальный поиск
    // живёт в navbar и в hero главной, пикер метрики карты — без поля.
    expect(screen.queryByRole('searchbox')).toBeNull();
    expect(screen.getByRole('link', { name: /больше показателей/i })).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByTestId('world-map-stub')).toBeTruthy();
    });
    await waitFor(async () => {
      expect(await planetProps()).toMatchObject({
        years: [2024, 2025], year: 2025, conceptSlug: 'unemployment-rate',
        ratingHref: '/world/rating/unemployment-rate/2025',
        rankingItems: [{ country_code: 'DE', value: 3.1 }],
      });
    });
    expect((await planetProps()).onYearChange).toEqual(expect.any(Function));

    const scope = document.querySelector('[data-block="home-data-scope"]');
    const controls = document.querySelector('[data-block="home-map-controls"]');
    const workbench = document.querySelector('[data-block="home-workbench"]');
    expect(scope && controls && workbench).toBeTruthy();
    expect(scope.compareDocumentPosition(controls) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(workbench.contains(controls)).toBe(true);

    expect((await planetProps()).unit).toBe('%');
    expect(screen.queryByRole('button', { name: /Германия/ })).toBeNull();
    expect(screen.queryByTestId('map-timeline-stub')).toBeNull();
  });

  it('для ВВП показывает справку МВФ и медиану с сервера, без выдуманного среднего', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators/, INDICATORS],
      ['/world/countries', {
        countries: [
          { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', indicators_count: 10 },
        ],
        total: 1,
      }],
      [/^\/world\/rating\/concepts/, {
        concepts: [
          { slug: 'gdp-usd', name: 'ВВП', unit: 'млрд $' },
          { slug: 'unemployment-rate', name: 'Уровень безработицы', unit: '%' },
        ],
        total: 2,
      }],
      [/^\/world\/compare\/map-series\/gdp-usd/, {
        years: [2025],
        values_by_year: {
          2025: {
            DE: {
              country_code: 'DE',
              country_slug: 'germany',
              country_name: 'Германия',
              indicator_code: 'de-ngdpd',
              value: 4500,
            },
          },
        },
        concept: { name: 'ВВП', unit: 'млрд $', slug: 'gdp-usd' },
        benchmark_by_year: {
          2025: {
            value: 12.4,
            label: 'Медиана по 48 странам с данными',
            countries_count: 48,
          },
        },
      }],
    ]);

    renderPage(
      <HomeWorkbench
        ratingConcepts={{
          data: {
            concepts: [
              { slug: 'gdp-usd', name: 'ВВП', unit: 'млрд $' },
              { slug: 'unemployment-rate', name: 'Уровень безработицы', unit: '%' },
            ],
          },
        }}
      />,
      { path: '/', route: '/' },
    );

    await waitFor(async () => expect((await planetProps())?.rankingItems).toHaveLength(1));
    expect(screen.getByRole('button', { name: 'Как читается карта валового внутреннего продукта' })).toBeTruthy();
    expect((await planetProps()).benchmark).toEqual({
      value: 12.4, label: 'Медиана по 48 странам с данными', countries_count: 48,
    });
  });

  it('рисует карту по snapshot, не дожидаясь полной истории map-series', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators/, INDICATORS],
      ['/world/countries', {
        countries: [
          { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', indicators_count: 10 },
        ],
        total: 1,
      }],
      [/^\/world\/rating\/concepts/, {
        concepts: [{ slug: 'unemployment-rate', name: 'Уровень безработицы', unit: '%' }],
        total: 1,
      }],
      [/^\/world\/compare\/snapshot\//, {
        items: [{
          country_code: 'DE',
          country_slug: 'germany',
          country_name: 'Германия',
          date: '2025-12-31',
          value: 3.1,
          indicator_code: 'de-un',
        }],
        concept: { name: 'Безработица', unit: '%' },
      }],
      [/^\/world\/compare\/map-series\//, () => new Promise(() => {})],
    ]);

    renderPage(
      <HomeWorkbench
        ratingConcepts={{
          data: {
            concepts: [{ slug: 'unemployment-rate', name: 'Уровень безработицы', unit: '%' }],
          },
        }}
      />,
      { path: '/', route: '/' },
    );

    await waitFor(async () => {
      expect(screen.getByTestId('world-map-stub')).toBeTruthy();
      expect((await planetProps()).rankingItems).toMatchObject([{ country_code: 'DE', value: 3.1 }]);
    });
    expect(screen.queryByTestId('map-timeline-stub')).toBeNull();
  });

  it('не держит карту скелетоном, если map-series уже есть, а каталог стран ещё грузится', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators/, INDICATORS],
      ['/world/countries', () => new Promise(() => {})],
      [/^\/world\/rating\/concepts/, {
        concepts: [{ slug: 'unemployment-rate', name: 'Уровень безработицы', unit: '%' }],
        total: 1,
      }],
      [/^\/world\/compare\/map-series\//, {
        years: [2025],
        values_by_year: {
          2025: {
            DE: {
              country_code: 'DE',
              country_slug: 'germany',
              country_name: 'Германия',
              value: 3.1,
            },
          },
        },
        concept: { name: 'Безработица', unit: '%' },
        benchmark_by_year: {},
      }],
    ]);

    renderPage(
      <HomeWorkbench
        ratingConcepts={{
          data: {
            concepts: [{ slug: 'unemployment-rate', name: 'Уровень безработицы', unit: '%' }],
          },
        }}
      />,
      { path: '/', route: '/' },
    );

    await waitFor(async () => {
      expect(screen.getByTestId('world-map-stub')).toBeTruthy();
      expect((await planetProps()).countries).toMatchObject([{ code: 'DE', slug: 'germany' }]);
      expect((await planetProps()).rankingItems).toMatchObject([{ country_code: 'DE', value: 3.1 }]);
    });
  });

  it('переключает год панели, сохраняет ноль и не выдумывает российское наблюдение', async () => {
    const point = (code, slug, value, year) => ({
      country_code: code, country_slug: slug, country_name: code === 'RU' ? 'Россия' : 'Германия',
      indicator_code: code === 'RU' ? 'unemployment' : 'de-une',
      date: `${year}-06-01`, value,
    });
    mockApiGet([
      ['/auth/me', { user: null }], [/^\/indicators/, INDICATORS],
      ['/world/countries', { countries: [{ code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany' }] }],
      [/^\/world\/compare\/map-series\//, {
        concept: { slug: 'unemployment-rate', unit: '%', russia: { eligible: true, indicator_code: 'unemployment' } },
        years: [2024, 2025],
        values_by_year: {
          2024: { DE: point('DE', 'germany', 3.1, 2024) },
          2025: { DE: point('DE', 'germany', 3.2, 2025), RU: point('RU', 'russia', 0, 2025) },
        },
      }],
    ]);
    renderPage(<><HomeWorkbench ratingConcepts={{ data: { concepts: [{ slug: 'unemployment-rate', unit: '%' }] } }} /><LocationProbe /></>,
      { path: '/*', route: '/' });
    await waitFor(async () => expect((await planetProps())?.year).toBe(2025));
    expect((await planetProps()).rankingItems[0]).toMatchObject({ country_code: 'RU', value: 0 });
    const changeYear = (await planetProps()).onYearChange;
    act(() => changeYear(2024));
    await waitFor(async () => expect((await planetProps())?.year).toBe(2024));
    const props = await planetProps();
    expect(props.ratingHref).toBe('/world/rating/unemployment-rate/2024');
    expect(props.countries.some((country) => country.code === 'RU')).toBe(true);
    expect(props.rankingItems).toMatchObject([{ country_code: 'DE', value: 3.1 }]);
    expect(props.valuesByCode.has('RU')).toBe(false);
    expect(props.detailsByCode.has('RU')).toBe(false);
    const russia = props.countries.find((country) => country.code === 'RU');
    act(() => props.onSelect(russia, null));
    expect(screen.getByTestId('location-probe').textContent).toBe('/russia/indicator/unemployment');
  });

  it('передаёт все строки рейтинга, включая страны за прежним пределом 32', async () => {
    const rows = Array.from({ length: 40 }, (_, index) => ({
      country_code: `C${index}`, country_slug: `country-${index}`, country_name: `Страна ${index}`,
      value: index,
    }));
    mockApiGet([
      ['/auth/me', { user: null }], [/^\/indicators/, INDICATORS],
      ['/world/countries', { countries: [] }],
      [/^\/world\/compare\/map-series\//, {
        concept: { slug: 'unemployment-rate', unit: '%' }, years: [2025],
        values_by_year: { 2025: Object.fromEntries(rows.map((row) => [row.country_code, row])) },
      }],
    ]);
    renderPage(<HomeWorkbench ratingConcepts={{ data: { concepts: [{ slug: 'unemployment-rate', unit: '%' }] } }} />);
    await waitFor(async () => expect((await planetProps())?.rankingItems).toHaveLength(40));
    expect((await planetProps()).rankingItems.at(-1)).toMatchObject({ country_code: 'C39', value: 39 });
    expect((await planetProps()).rankingItems[0].value).toBe(0);
  });
});
