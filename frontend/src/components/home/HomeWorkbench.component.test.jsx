import { describe, it, expect, afterEach, vi } from 'vitest';
import { act, screen, waitFor, within } from '@testing-library/react';
import { useLocation } from 'react-router-dom';
import HomeWorkbench from './HomeWorkbench';
import { renderPage, mockApiGet } from '../../test/renderPage';

vi.mock('../PlanetView', () => ({
  default: vi.fn(() => <div data-testid="world-map-stub">map</div>),
}));
// Счётчики загрузки модулей: фабрика мока срабатывает при первом import(), то есть когда код реально потребовали.
const loaded = vi.hoisted(() => ({ scene: 0, map: 0, images: [] }));
vi.mock('../PlanetScene', () => { loaded.scene += 1; return { default: () => null }; });
vi.mock('../WorldMap', () => { loaded.map += 1; return { default: () => null }; });

afterEach(() => { vi.restoreAllMocks(); vi.clearAllMocks(); vi.unstubAllGlobals(); window.localStorage.clear(); });

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
        ratingHref: '/world/rating/unemployment-rate?year=2025',
        rankingItems: [{ country_code: 'DE', value: 3.1 }],
      });
    });
    expect((await planetProps()).onYearChange).toEqual(expect.any(Function));

    const scope = document.querySelector('[data-block="home-data-scope"]');
    const controls = document.querySelector('[data-block="home-map-controls"]');
    const workbench = document.querySelector('[data-block="home-workbench"]');
    expect(scope && controls && workbench).toBeTruthy();
    // Планета на первом экране: рабочая панель идёт сразу за поиском, числа платформы — после неё.
    expect(workbench.compareDocumentPosition(scope) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(document.querySelector('.fe-hero-planet').contains(workbench)).toBe(true);
    expect(workbench.contains(controls)).toBe(true);

    expect((await planetProps()).unit).toBe('%');
    // Русский сайт стартует шар над Евразией, а не над пустой Атлантикой.
    expect((await planetProps()).startFocus).toEqual([52, 38]);
    expect(screen.queryByRole('button', { name: /Германия/ })).toBeNull();
    expect(screen.queryByTestId('map-timeline-stub')).toBeNull();
  });

  it('левая колонка героя: быстрые ссылки ведут сразу на страницу, «Мир сейчас» из срезов, порядок в разметке как на телефоне', async () => {
    const snapshot = (items) => ({ items, average: null });
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators/, INDICATORS],
      ['/world/countries', {
        countries: [
          { code: 'US', slug: 'united-states', name: 'США', name_en: 'United States', indicators_count: 10 },
          { code: 'CN', slug: 'china', name: 'Китай', name_en: 'China', indicators_count: 10 },
          { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', indicators_count: 10 },
          { code: 'IN', slug: 'india', name: 'Индия', name_en: 'India', indicators_count: 10 },
        ],
        total: 4,
      }],
      [/^\/world\/rating\/concepts/, { concepts: [{ slug: 'gdp-usd', name: 'ВВП', unit: 'млрд $' }], total: 1 }],
      ['/world/compare/snapshot/gdp-usd', snapshot([
        { country_code: 'US', country_slug: 'united-states', indicator_code: 'weo-gdp-usd', date: '2025-12-31', value: 30767, unit: 'млрд $' },
        { country_code: 'CN', country_slug: 'china', indicator_code: 'weo-gdp-usd', date: '2025-12-31', value: 19400, unit: 'млрд $' },
        { country_code: 'DE', country_slug: 'germany', indicator_code: 'weo-gdp-usd', date: '2025-12-31', value: 4900, unit: 'млрд $' },
        { country_code: 'IN', country_slug: 'india', indicator_code: 'in-gdp', date: '2025-12-31', value: 4100, unit: 'млрд $' },
      ])],
      ['/world/compare/snapshot/hicp-index', snapshot([
        { country_code: 'US', country_slug: 'united-states', indicator_code: 'us-cpi', date: '2025-12-31', value: 2.9 },
        { country_code: 'CN', country_slug: 'china', indicator_code: 'cn-cpi', date: '2025-12-31', value: 0.4 },
        { country_code: 'DE', country_slug: 'germany', indicator_code: 'de-cpi', date: '2025-12-31', value: 2.2 },
        { country_code: 'RU', country_slug: 'russia', indicator_code: 'cpi-yoy', date: '2025-12-31', value: 8.1 },
      ])],
      ['/world/compare/snapshot/unemployment-rate', snapshot([
        { country_code: 'US', country_slug: 'united-states', indicator_code: 'us-un', date: '2025-12-31', value: 4.1 },
        { country_code: 'DE', country_slug: 'germany', indicator_code: 'de-un', date: '2025-12-31', value: 3.1 },
        { country_code: 'CN', country_slug: 'china', indicator_code: 'cn-un', date: '2025-12-31', value: 5.1 },
      ])],
      [/^\/world\/compare\/map-series\//, { years: [2025], values_by_year: {}, concept: { name: 'ВВП', unit: 'млрд $' }, benchmark_by_year: {} }],
    ]);
    renderPage(
      <HomeWorkbench ratingConcepts={{ data: { concepts: [{ slug: 'gdp-usd', name: 'ВВП', unit: 'млрд $' }] } }} />,
      { path: '/', route: '/' },
    );

    const quick = screen.getByRole('navigation', { name: 'Частые запросы' });
    const hrefs = [...quick.querySelectorAll('a')].map((a) => [a.textContent, a.getAttribute('href')]);
    expect(hrefs.slice(0, 3)).toEqual([
      ['Курс доллара', '/currencies/indicator/usd-rub'],
      ['Инфляция в России', '/russia/indicator/cpi-yoy'],
      ['Ключевая ставка', '/russia/indicator/key-rate'],
    ]);
    // «ВВП Индии» после загрузки среза ведёт сразу на показатель, а не на страницу страны.
    await waitFor(() => expect(within(quick).getByRole('link', { name: 'ВВП Индии' }).getAttribute('href')).toBe('/india/indicator/in-gdp'));

    const today = await screen.findByRole('region', { name: 'Мир сейчас' });
    await waitFor(() => expect(today.querySelectorAll('.fe-today__tile').length).toBe(4));
    const tiles = [...today.querySelectorAll('.fe-today__tile')].map((tile) => tile.getAttribute('data-tile'));
    expect(tiles).toEqual(['economy', 'prices', 'jobs', 'home']);
    const economy = today.querySelector('[data-tile="economy"]');
    expect(economy.textContent).toContain('30,8');
    expect(economy.textContent).toContain('США');
    expect(economy.textContent).toContain('Место 1 из 4');
    expect(economy.getAttribute('href')).toBe('/united-states/indicator/weo-gdp-usd');
    // Россия на русском сайте ведёт в российский раздел.
    expect(today.querySelector('[data-tile="home"]').getAttribute('href')).toBe('/russia/indicator/cpi-yoy');
    expect(today.querySelector('[data-tile="home"]').textContent).toContain('8,1');

    // Порядок в разметке как на телефоне: поиск и ссылки, планета, «Мир сейчас», числа платформы.
    const text = document.querySelector('.fe-hero-text');
    const planet = document.querySelector('.fe-hero-planet');
    const scope = document.querySelector('.fe-hero-scope');
    expect(text.compareDocumentPosition(planet) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(planet.compareDocumentPosition(today) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(today.compareDocumentPosition(scope) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
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
    expect(props.ratingHref).toBe('/world/rating/unemployment-rate?year=2024');
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

  it('чипы показателей видны сразу все (из словаря), пока каталог понятий ещё не пришёл', () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/world\/rating\/concepts/, () => new Promise(() => {})],
    ]);
    renderPage(<HomeWorkbench ratingConcepts={{ data: undefined }} />, { path: '/', route: '/' });
    const group = screen.getByRole('group', { name: 'Показатель' });
    const labels = [...group.querySelectorAll('.fe-chip')].map((el) => el.textContent);
    expect(labels).toEqual(['ВВП', 'ВВП на душу населения', 'Безработица', 'Инфляция', 'Население']);
  });

  it('лёгкая главная: по умолчанию заранее качается только плоская карта, а шар, его сцена и текстура не стартуют', async () => {
    vi.stubGlobal('Image', class { set src(value) { loaded.images.push(value); } });
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/world\/rating\/concepts/, () => new Promise(() => {})],
    ]);
    renderPage(<HomeWorkbench ratingConcepts={{ data: undefined }} />, { path: '/', route: '/' });
    await waitFor(() => expect(loaded.map).toBe(1));
    expect(loaded.scene).toBe(0);
    expect(loaded.images.filter((src) => /planet|earth/.test(src))).toEqual([]);
  });

  it('если человек раньше выбрал шар, сцена и дневная текстура греются заранее, как и прежде', async () => {
    window.localStorage.setItem('fe_planet_view', 'globe');
    vi.stubGlobal('Image', class { set src(value) { loaded.images.push(value); } });
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/world\/rating\/concepts/, () => new Promise(() => {})],
    ]);
    renderPage(<HomeWorkbench ratingConcepts={{ data: undefined }} />, { path: '/', route: '/' });
    await waitFor(() => expect(loaded.scene).toBe(1));
    expect(loaded.images).toContain('/planet/earth_day_2048.webp');
  });
});
