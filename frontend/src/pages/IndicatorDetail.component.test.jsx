// Т-13: IndicatorDetail — smoke диспатча карточки: страница монтируется на
// мокнутом API, показывает имя индикатора; неизвестный код не роняет рендер.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import IndicatorDetail from './IndicatorDetail';
import { renderPage, mockApiGet } from '../test/renderPage';

afterEach(() => vi.restoreAllMocks());

const DETAIL = {
  code: 'pensioners', name: 'Численность пенсионеров', name_en: 'Pensioners',
  unit: 'тыс. человек', frequency: 'annual', category: 'Население',
  source: 'Росстат', is_active: true, is_listed: true,
  current_value: 41000, current_date: '2024-01-01',
  description: 'Тестовое описание', methodology: 'Тестовая методология',
  seo_blocks: null,
};

const ROUTES = [
  ['/auth/me', { user: null }],
  [/^\/indicators\/pensioners$/, DETAIL],
  [/^\/indicators\/pensioners\/data/, {
    indicator: 'pensioners',
    data: [
      { date: '2022-01-01', value: 42000 },
      { date: '2023-01-01', value: 41500 },
      { date: '2024-01-01', value: 41000 },
    ],
  }],
  [/^\/indicators\/pensioners\/stats/, {
    code: 'pensioners', data_count: 3, average: 41500,
    highest: { date: '2022-01-01', value: 42000 },
    lowest: { date: '2024-01-01', value: 41000 },
    std_dev: 500,
  }],
  [/^\/indicators\/pensioners\/forecast/, { indicator: 'pensioners', forecast: null }],
  [/^\/indicators(\?|$)/, [DETAIL]],
  [/^\/regions/, { districts: [], sections: [] }],
];

describe('IndicatorDetail', () => {
  it('рендерит карточку с именем индикатора', async () => {
    mockApiGet(ROUTES);
    renderPage(<IndicatorDetail />, {
      path: '/indicator/:code', route: '/indicator/pensioners',
    });
    const names = await screen.findAllByText(/Численность пенсионеров/);
    expect(names.length).toBeGreaterThan(0);
  });

  it('не падает на неизвестном коде (все запросы 404)', async () => {
    mockApiGet([['/auth/me', { user: null }]]);
    renderPage(<IndicatorDetail />, {
      path: '/indicator/:code', route: '/indicator/no-such-code',
    });
    // Достаточно того, что рендер не бросил и что-то показал (loading/error UI).
    expect(document.body.textContent.length).toBeGreaterThan(0);
  });
});
