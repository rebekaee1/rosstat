import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import RegionRatingPage from './RegionRatingPage';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/RegionsMap', () => ({
  default: vi.fn(() => <div data-testid="regions-map-stub">map</div>),
}));

afterEach(() => vi.restoreAllMocks());

function makeValues() {
  // ≥10 строк — порог рейтинга на странице
  const base = [
    { slug: 'ingushetiya', name: 'Ингушетия', value: 26.4, raw: 26.4 },
    { slug: 'moskva', name: 'Москва', value: 1.0, raw: 1.0 },
    { slug: 'spb', name: 'Санкт-Петербург', value: 1.5, raw: 1.5 },
  ];
  for (let i = 0; i < 10; i += 1) {
    base.push({
      slug: `r${i}`,
      name: `Регион ${i}`,
      value: 5 + i * 0.1,
      raw: 5 + i * 0.1,
    });
  }
  return base;
}

function dataRows() {
  return screen.getAllByRole('row').slice(1);
}

describe('RegionRatingPage', () => {
  it('для lower_better сортирует по возрастанию: лучший регион первым', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/regions\/heatmap\/uroven-bezrabotitsy/, {
        indicator: { code: 'uroven-bezrabotitsy', name: 'Уровень безработицы', unit: '%' },
        year: 2024,
        polarity: 'lower_better',
        default_sort: 'asc',
        rank_as_achievement: true,
        values: makeValues(),
      }],
    ]);

    renderPage(
      <RegionRatingPage />,
      { path: '/russia/region-rating/:code', route: '/russia/region-rating/uroven-bezrabotitsy' },
    );

    expect(await screen.findByRole('heading', { name: /рейтинг регионов России/i })).toBeTruthy();
    expect(screen.getByText('Лучшее значение')).toBeTruthy();

    await waitFor(() => {
      const rows = dataRows();
      expect(within(rows[0]).getByRole('link', { name: 'Москва' })).toBeTruthy();
    });

    fireEvent.click(screen.getByRole('button', { name: 'По убыванию' }));
    await waitFor(() => {
      const rows = dataRows();
      expect(within(rows[0]).getByRole('link', { name: 'Ингушетия' })).toBeTruthy();
    });
  });

  it('переключатель в шапке таблицы разворачивает направление и карту', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/regions\/heatmap\/uroven-bezrabotitsy/, {
        indicator: { code: 'uroven-bezrabotitsy', name: 'Уровень безработицы', unit: '%' },
        year: 2024,
        polarity: 'lower_better',
        default_sort: 'asc',
        rank_as_achievement: true,
        values: makeValues(),
      }],
    ]);
    const RegionsMap = (await import('../components/RegionsMap')).default;

    renderPage(
      <RegionRatingPage />,
      { path: '/russia/region-rating/:code', route: '/russia/region-rating/uroven-bezrabotitsy' },
    );

    expect(await screen.findByTestId('regions-map-stub')).toBeTruthy();
    expect(RegionsMap).toHaveBeenCalledWith(
      expect.objectContaining({ colorDirection: 'asc' }),
      undefined,
    );

    // Клик по заголовку колонки значений разворачивает направление —
    // раскраска карты переворачивается вместе с порядком строк.
    const valueHeader = screen
      .getAllByRole('columnheader')
      .find((node) => node.textContent.includes('%'));
    fireEvent.click(within(valueHeader).getByRole('button'));
    expect(RegionsMap).toHaveBeenLastCalledWith(
      expect.objectContaining({ colorDirection: 'desc' }),
      undefined,
    );
  });

  it('для неизвестной полярности — нейтральные подписи и убывание по умолчанию', async () => {
    const values = makeValues().map((row) => (
      row.slug === 'moskva'
        ? { ...row, value: 13000, raw: 13000 }
        : row.slug === 'ingushetiya'
          ? { ...row, value: 500, raw: 500 }
          : row
    ));
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/regions\/heatmap\/chislennost-naseleniya/, {
        indicator: { code: 'chislennost-naseleniya', name: 'Численность населения', unit: 'тыс. человек' },
        year: 2024,
        polarity: null,
        default_sort: 'desc',
        rank_as_achievement: false,
        values,
      }],
    ]);

    renderPage(
      <RegionRatingPage />,
      { path: '/russia/region-rating/:code', route: '/russia/region-rating/chislennost-naseleniya' },
    );

    expect(await screen.findByRole('heading', { name: /сравнение регионов России/i })).toBeTruthy();
    expect(screen.getByText('Наибольшее значение')).toBeTruthy();
    expect(screen.queryByText('Лучшее значение')).toBeNull();
    expect(screen.getByRole('columnheader', { name: /тыс. человек/i })).toBeTruthy();

    await waitFor(() => {
      const rows = dataRows();
      expect(within(rows[0]).getByRole('link', { name: 'Москва' })).toBeTruthy();
    });
  });
});
