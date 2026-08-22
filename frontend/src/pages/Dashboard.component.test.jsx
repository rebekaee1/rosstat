import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import Dashboard from './Dashboard';
import { renderPage, mockApiGet } from '../test/renderPage';

afterEach(() => vi.restoreAllMocks());

const INDICATORS = [
  {
    code: 'btc-usd', name: 'Биткоин (BTC/USD)', unit: 'USD', category: 'Валюты',
    frequency: 'daily', is_active: true, is_listed: true, current_value: 95000,
  },
  {
    code: 'brent', name: 'Нефть Brent', unit: 'USD/баррель', category: 'Товарные рынки',
    frequency: 'daily', is_active: true, is_listed: true, current_value: 78.5,
  },
  {
    code: 'natural-gas', name: 'Природный газ', unit: 'USD/млн БТЕ', category: 'Товарные рынки',
    frequency: 'daily', is_active: true, is_listed: true, current_value: 2.79,
  },
  {
    code: 'usd-index', name: 'Индекс доллара США', unit: 'пунктов', category: 'Индексы',
    frequency: 'daily', is_active: true, is_listed: true, current_value: 120.5,
  },
  {
    code: 'ust-10y', name: 'Доходность 10-летних гособлигаций США', unit: '%', category: 'Индексы',
    frequency: 'daily', is_active: true, is_listed: true, current_value: 4.2,
  },
  {
    code: 'eth-usd', name: 'Эфириум (ETH/USD)', unit: 'USD', category: 'Валюты',
    frequency: 'daily', is_active: true, is_listed: true, current_value: 3400,
  },
  {
    code: 'sol-usd', name: 'Солана (SOL/USD)', unit: 'USD', category: 'Валюты',
    frequency: 'daily', is_active: true, is_listed: true, current_value: 145,
  },
];

describe('Dashboard', () => {
  it('собирает hero, мировые рынки, витрину стран, покрытие и каталог стран', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      ['/dashboard/sparklines', {}],
      ['/dashboard/coverage', {
        countries: 48, series: 12000, regions: 85, year_from: 1897, year_to: 2026,
      }],
      [/^\/indicators/, INDICATORS],
      ['/indicators', INDICATORS],
      ['/world/countries', { countries: [], total: 0 }],
      [/^\/world\/rating\/concepts/, { concepts: [], total: 0 }],
      [/^\/world\/compare\/map-series\//, {
        years: [], values_by_year: {}, concept: {}, benchmark_by_year: {},
      }],
    ]);

    renderPage(<Dashboard />, { path: '/', route: '/' });

    const h1 = await screen.findByRole('heading', { level: 1 });
    expect(h1.textContent).toBe(
      'Официальные макроэкономические индикаторы в одной рабочей среде',
    );
    expect(screen.getByText('Мировые рынки')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Страны и показатели' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Сколько данных доступно' })).toBeTruthy();
    expect(await screen.findByRole('heading', { name: 'Страны' })).toBeTruthy();

    // Блоки, снятые с главной по правкам 9 и 10: категории России и инструменты.
    expect(screen.queryByText('Категории России')).toBeNull();
    expect(screen.queryByText('Инструменты')).toBeNull();
    expect(screen.queryByRole('navigation', { name: 'Переходы по разделам' })).toBeNull();
    expect(screen.queryByText('Россия сегодня')).toBeNull();
  });
});
