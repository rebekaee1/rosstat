import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import Dashboard from './Dashboard';
import { renderPage, mockApiGet } from '../test/renderPage';

afterEach(() => vi.restoreAllMocks());

const INDICATORS = [
  {
    code: 'usd-rub', name: 'Доллар США', unit: 'руб.', category: 'Валюты',
    frequency: 'daily', is_active: true, is_listed: true, current_value: 90.1,
  },
  {
    code: 'key-rate', name: 'Ключевая ставка ЦБ', unit: '%', category: 'Ставки',
    frequency: 'daily', is_active: true, is_listed: true, current_value: 14.25,
  },
  {
    code: 'cpi', name: 'Индекс потребительских цен', unit: '%', category: 'Цены',
    frequency: 'monthly', is_active: true, is_listed: true,
    current_value: 100.2, hero_value: 5.32, hero_unit: '%',
  },
  {
    code: 'unemployment', name: 'Безработица', unit: '%', category: 'Рынок труда',
    frequency: 'monthly', is_active: true, is_listed: true, current_value: 2.3,
  },
  {
    code: 'imoex', name: 'Индекс МосБиржи', unit: 'п.', category: 'Индексы',
    frequency: 'daily', is_active: true, is_listed: true, current_value: 2800,
  },
  {
    code: 'gold-price', name: 'Цена золота', unit: 'руб./г', category: 'Товарные рынки',
    frequency: 'daily', is_active: true, is_listed: true, current_value: 6500,
  },
];

describe('Dashboard', () => {
  it('собирает hero, Россия сегодня, workbench и категории', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      ['/dashboard/sparklines', {}],
      [/^\/indicators/, INDICATORS],
      ['/indicators', INDICATORS],
    ]);

    renderPage(<Dashboard />, { path: '/', route: '/' });

    expect(await screen.findByRole('heading', { level: 1 })).toBeTruthy();
    expect(screen.getByText('Россия сегодня')).toBeTruthy();
    expect(screen.getByRole('tablist', { name: 'Плоскости данных' })).toBeTruthy();
    expect(screen.getByRole('tab', { name: 'Страны' })).toBeTruthy();
    expect(screen.getByText('Категории')).toBeTruthy();
    expect(screen.getByText('Инструменты')).toBeTruthy();
  });
});
