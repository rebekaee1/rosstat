// Круг 13, D2: блок «Актуальные данные» стоит на страницах показателя России и мира, когда сервер прислал `freshness`.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { waitFor, screen } from '@testing-library/react';
import WorldIndicatorPage from './WorldIndicatorPage';
import IndicatorDetail from './IndicatorDetail';
import { renderPage, mockApiGet } from '../test/renderPage';
import { russiaIndicatorPath } from '../lib/sitePaths';

vi.mock('../components/WorldChartSection', () => ({
  default: () => <section id="chart" data-testid="chart-stub" />,
}));

afterEach(() => vi.restoreAllMocks());

const WORLD_NOTE = {
  level: 'stale', last_period: '2023-12-01', age_days: 1015, reason: 'series_lag', source_updated_at: '2026-10-01',
  lead: 'Источник обновляет набор, но по этому ряду данных позже декабря 2023 нет.',
  message: 'Источник обновляет набор, но по этому ряду данных позже декабря 2023 нет. Ближайший актуальный показатель: Оборот, сезонно скорректировано.',
  nearest: { code: 'bg-turnover-sa', name: 'Оборот, сезонно скорректировано', url: '/bulgaria/indicator/bg-turnover-sa', last_period: '2026-08-01', frequency: 'monthly' },
};

function worldMeta(freshness) {
  return {
    country: { code: 'BG', slug: 'bulgaria', name: 'Болгария', name_en: 'Bulgaria', region: 'Европа' },
    primary_code: 'bg-turnover',
    indicator: {
      code: 'bg-turnover', name: 'Оборот в торговле', unit: 'индекс (2021 = 100)', frequency: 'monthly',
      category: 'Торговля', source: 'Евростат', history_end: '2023-12-01', freshness,
    },
    modes: [{ id: 'level-monthly', label: 'По месяцам', group: 'Уровень', type: 'level', freq: 'monthly', unit: 'индекс' }],
    variants: [], forecast_available: false, peers: [],
  };
}

function renderWorld(freshness) {
  mockApiGet([
    ['/auth/me', { user: null }],
    [/^\/world\/indicators\/bulgaria\/bg-turnover$/, worldMeta(freshness)],
    [/^\/world\/indicators\/bulgaria\/bg-turnover\/data/, {
      code: 'bg-turnover', mode: 'level-monthly', unit: 'индекс', frequency: 'monthly',
      points: Array.from({ length: 12 }, (_, i) => ({ date: `2023-${String(i + 1).padStart(2, '0')}-01`, value: 100 + i })), count: 12,
    }],
    [/^\/world\/compare/, { items: [], concept: { value_mode: 'level' } }],
    [/^\/world\/countries\/bulgaria$/, { country: worldMeta(null).country, categories: [], overview: [] }],
  ]);
  return renderPage(<WorldIndicatorPage />, { path: '/:countrySlug/indicator/:code', route: '/bulgaria/indicator/bg-turnover' });
}

describe('Блок «Актуальные данные» на страницах показателей (круг 13, D2)', () => {
  it('мир: блок стоит между шапкой и графиком, ссылка ведёт на ближайший актуальный показатель', async () => {
    renderWorld(WORLD_NOTE);
    const block = await screen.findByTestId('freshness-note');
    expect(screen.getByTestId('freshness-note-lead').textContent).toBe(WORLD_NOTE.lead);
    expect(screen.getByTestId('freshness-note-link').getAttribute('href')).toBe('/bulgaria/indicator/bg-turnover-sa');
    const header = document.querySelector('header.z4-hero');
    expect(header.compareDocumentPosition(block) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(block.compareDocumentPosition(screen.getByTestId('chart-stub')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('мир: у свежего ряда (freshness = null) блока нет', async () => {
    renderWorld(null);
    await screen.findByTestId('chart-stub');
    await waitFor(() => expect(document.querySelector('header.z4-hero')).toBeTruthy());
    expect(screen.queryByTestId('freshness-note')).toBeNull();
  });

  it('Россия: блок виден у показателя с полем freshness', async () => {
    const detail = {
      code: 'pensioners', name: 'Численность пенсионеров', name_en: 'Pensioners', unit: 'тыс. человек', frequency: 'annual',
      category: 'Население', source: 'Росстат', is_active: true, is_listed: true, current_value: 41000, current_date: '2022-01-01',
      description: 'x', methodology: 'x', seo_blocks: null,
      freshness: {
        level: 'stale', last_period: '2022-01-01', age_days: 1400, reason: 'source_stopped', source_updated_at: null,
        lead: 'Источник не обновлял ряд с 2022.', message: 'Источник не обновлял ряд с 2022.', nearest: null,
      },
    };
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators\/pensioners$/, detail],
      [/^\/indicators\/pensioners\/data/, { indicator: 'pensioners', data: [{ date: '2021-01-01', value: 42000 }, { date: '2022-01-01', value: 41000 }] }],
      [/^\/indicators\/pensioners\/stats/, { code: 'pensioners', data_count: 2, average: 41500, highest: { date: '2021-01-01', value: 42000 }, lowest: { date: '2022-01-01', value: 41000 }, std_dev: 500 }],
      [/^\/indicators\/pensioners\/forecast/, { indicator: 'pensioners', forecast: null }],
      [/^\/indicators(\?|$)/, [detail]],
      [/^\/regions/, { districts: [], sections: [] }],
    ]);
    renderPage(<IndicatorDetail />, { path: russiaIndicatorPath(':code'), route: russiaIndicatorPath('pensioners') });
    const lead = await screen.findByTestId('freshness-note-lead');
    expect(lead.textContent).toBe('Источник не обновлял ряд с 2022.');
    expect(screen.queryByTestId('freshness-note-link')).toBeNull();
  });
});
