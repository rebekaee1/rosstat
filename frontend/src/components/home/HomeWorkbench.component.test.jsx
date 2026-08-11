import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import HomeWorkbench from './HomeWorkbench';
import { renderPage, mockApiGet } from '../../test/renderPage';

vi.mock('../WorldMap', () => ({
  default: () => <div data-testid="world-map-stub">map</div>,
}));
vi.mock('../MapTimeline', () => ({
  default: () => <div data-testid="map-timeline-stub">timeline</div>,
}));
vi.mock('../RegionsMap', () => ({
  default: () => <div data-testid="regions-map-stub">regions-map</div>,
}));

afterEach(() => vi.restoreAllMocks());

const INDICATORS = [
  {
    code: 'cpi', name: 'Индекс потребительских цен', unit: '%', category: 'Цены',
    frequency: 'monthly', is_active: true, is_listed: true,
    current_value: 100.2, hero_value: 5.3, hero_unit: '%', change: 0.1,
  },
  {
    code: 'key-rate', name: 'Ключевая ставка ЦБ', unit: '%', category: 'Ставки',
    frequency: 'daily', is_active: true, is_listed: true, current_value: 14.25, change: 0,
  },
  {
    code: 'usd-rub', name: 'Доллар США', unit: 'руб.', category: 'Валюты',
    frequency: 'daily', is_active: true, is_listed: true, current_value: 90.1, change: 0.2,
  },
  {
    code: 'unemployment', name: 'Безработица', unit: '%', category: 'Рынок труда',
    frequency: 'monthly', is_active: true, is_listed: true, current_value: 2.3, change: -0.1,
  },
  {
    code: 'gdp-nominal', name: 'ВВП номинальный', unit: 'млрд руб.', category: 'ВВП',
    frequency: 'quarterly', is_active: true, is_listed: true, current_value: 50000, change: 100,
  },
  {
    code: 'ipi', name: 'Индекс промышленного производства', unit: '%', category: 'Бизнес',
    frequency: 'monthly', is_active: true, is_listed: true,
    current_value: 102, hero_value: 2.1, hero_unit: '%',
  },
];

describe('HomeWorkbench', () => {
  it('рисует a11y tablist и переключает плоскости без карты на России', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      ['/dashboard/sparklines', {}],
      [/^\/indicators/, INDICATORS],
      ['/world/countries', { countries: [], total: 0 }],
      ['/world/compare/catalog', { items: [], total: 0 }],
      [/^\/world\/compare\/map-series\//, { years: [], values_by_year: {}, concept: { name: 'Безработица', unit: '%' } }],
      [/^\/regions\/heatmap\//, { indicator: { code: 'x', name: 'Зарплата', unit: 'руб.' }, year: 2024, values: [] }],
    ]);

    renderPage(
      <HomeWorkbench indicators={INDICATORS} indicatorsLoading={false} />,
      { path: '/', route: '/' },
    );

    const tablist = screen.getByRole('tablist', { name: 'Плоскости данных' });
    expect(tablist).toBeTruthy();

    const russia = screen.getByRole('tab', { name: 'Россия' });
    const regions = screen.getByRole('tab', { name: 'Регионы' });
    const countries = screen.getByRole('tab', { name: 'Страны' });
    expect(russia.getAttribute('aria-selected')).toBe('true');
    expect(regions.getAttribute('aria-selected')).toBe('false');

    expect(screen.getByText('Флагманские показатели')).toBeTruthy();
    expect(screen.queryByText(/европейское покрытие/i)).toBeNull();

    fireEvent.click(countries);
    expect(countries.getAttribute('aria-selected')).toBe('true');
    expect(await screen.findByText(/Текущее покрытие — страны Европы/i)).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByTestId('world-map-stub')).toBeTruthy();
    });
  });
});
