import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import HomeWorkbench from './HomeWorkbench';
import { renderPage, mockApiGet } from '../../test/renderPage';

vi.mock('../WorldMap', () => ({
  default: () => <div data-testid="world-map-stub">map</div>,
}));
vi.mock('../MapTimeline', () => ({
  default: ({ years, year, onYearChange }) => (
    <div data-testid="map-timeline-stub">
      timeline:{Array.isArray(years) ? years.join(',') : 'none'}:{year ?? 'nil'}:{typeof onYearChange}
    </div>
  ),
}));

afterEach(() => vi.restoreAllMocks());

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
  it('рисует карту, рейтинг и подсказку на полный рейтинг вместо боковых переходов', async () => {
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
    const timeline = screen.getByTestId('map-timeline-stub');
    expect(timeline.textContent).toContain('timeline:2024,2025:2025:function');

    const scope = document.querySelector('[data-block="home-data-scope"]');
    const controls = document.querySelector('[data-block="home-map-controls"]');
    const workbench = document.querySelector('[data-block="home-workbench"]');
    expect(scope && controls && workbench).toBeTruthy();
    expect(scope.compareDocumentPosition(controls) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(workbench.contains(controls)).toBe(true);

    await waitFor(() => {
      expect(screen.getByText(/3,10/)).toBeTruthy();
    });
    const rankingBtn = screen.getByRole('button', { name: /Германия/ });
    expect(rankingBtn.textContent).toMatch(/Германия/);
    expect(rankingBtn.textContent).toMatch(/3,10/);
    // Единица один раз в шапке блока, не в каждой строке.
    expect(rankingBtn.textContent).not.toMatch(/% экономически/);
    expect(screen.getByText('%')).toBeTruthy();
    // В строках рейтинга нет обрезанных имён (ellipsis в placeholder поиска — ок).
    expect(rankingBtn.textContent).not.toMatch(/\.\.\.|…/);
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

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Германия/ })).toBeTruthy();
    });
    expect(screen.getByRole('button', { name: 'Как читается карта валового внутреннего продукта' })).toBeTruthy();
    expect(screen.getByText('Медиана по 48 странам с данными')).toBeTruthy();
    expect(screen.getByText(/12,40/)).toBeTruthy();
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

    await waitFor(() => {
      expect(screen.getByTestId('world-map-stub')).toBeTruthy();
      expect(screen.getByRole('button', { name: /Германия/ })).toBeTruthy();
    });
    expect(screen.getByRole('button', { name: /Германия/ }).textContent).toMatch(/3,10/);
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

    await waitFor(() => {
      expect(screen.getByTestId('world-map-stub')).toBeTruthy();
      expect(screen.getByRole('button', { name: /Германия/ })).toBeTruthy();
    });
  });
});
