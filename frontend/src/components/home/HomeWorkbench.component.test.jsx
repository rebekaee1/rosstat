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
  it('рисует карту мира, боковые переходы и без mid-dot в заголовке', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators/, INDICATORS],
      ['/world/countries', {
        countries: [
          { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', indicators_count: 10 },
        ],
        total: 1,
      }],
      ['/world/compare/catalog', {
        items: [{
          concept_slug: 'unemployment-rate',
          concept_name: 'Уровень безработицы',
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
      <HomeWorkbench indicators={INDICATORS} />,
      { path: '/', route: '/' },
    );

    expect(screen.getByRole('heading', { name: 'Страны и показатели' })).toBeTruthy();
    expect(screen.queryByText(/Россия · Регионы/)).toBeNull();
    expect(screen.getByRole('navigation', { name: 'Переходы по разделам' })).toBeTruthy();
    expect(screen.getByRole('link', { name: /Регионы России/i })).toBeTruthy();
    expect(screen.getByRole('link', { name: /^Европа/i })).toBeTruthy();
    expect(screen.getByRole('link', { name: /^Мир/i })).toBeTruthy();
    expect(screen.getByRole('link', { name: /Показатели России/i })).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByTestId('world-map-stub')).toBeTruthy();
    });
    const timeline = screen.getByTestId('map-timeline-stub');
    expect(timeline).toBeTruthy();
    expect(timeline.textContent).toContain('timeline:2024,2025:2025:function');
  });
});
