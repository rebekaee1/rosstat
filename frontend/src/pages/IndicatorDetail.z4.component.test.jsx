// Раунд 2, зона Z4: российская карточка показателя использует ту же раскладку, что и мировая:
// главное число в шапке, сцена «график + плитки», таблица рядом с методологией.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { waitFor } from '@testing-library/react';
import IndicatorDetail from './IndicatorDetail';
import { renderPage, mockApiGet } from '../test/renderPage';
import { russiaIndicatorPath } from '../lib/sitePaths';

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

function renderDetail() {
  mockApiGet(ROUTES);
  return renderPage(<IndicatorDetail />, {
    path: russiaIndicatorPath(':code'), route: russiaIndicatorPath('pensioners'),
  });
}

describe('IndicatorDetail: раскладка первого экрана', () => {
  it('в шапке справа главное число, под ним сцена с графиком и плитками, ниже таблица рядом с методологией', async () => {
    const { container } = renderDetail();
    await waitFor(() => expect(container.querySelector('.z4-hero .z4-hv__value')).toBeTruthy());
    const hero = container.querySelector('.z4-hero');
    expect(hero.getAttribute('data-has-value')).toBe('true');
    expect(hero.querySelector('.z4-hero__main h1').textContent).toContain('Численность пенсионеров');

    const stage = container.querySelector('.z4-stage');
    expect(stage.querySelector('section#chart.z4-chart-section')).toBeTruthy();
    expect(stage.querySelector('.z4-tiles .fe-tele-section')).toBeTruthy();

    const lower = container.querySelector('.z4-lower');
    expect(lower.querySelector('.z4-lower__table .fe-histtable')).toBeTruthy();
    expect(lower.querySelector('.z4-lower__aside [data-block="methodology"]')).toBeTruthy();
  });
});
