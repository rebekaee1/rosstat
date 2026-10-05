// Волна 6, G: страница «Численность населения» показывает «28,1 млн», а не «28 076 986» и «+346 630,00».
import { describe, it, expect, afterEach, vi } from 'vitest';
import { waitFor } from '@testing-library/react';
import WorldIndicatorPage from './WorldIndicatorPage';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/WorldChartSection', () => ({
  default: () => <section id="chart" data-testid="chart-stub" />,
}));

afterEach(() => vi.restoreAllMocks());

const META = {
  country: { code: 'AU', slug: 'australia', name: 'Австралия', name_en: 'Australia', region: 'Океания' },
  primary_code: 'au-pop',
  indicator: {
    code: 'au-pop',
    name: 'Численность населения',
    concept_slug: 'population',
    unit: 'человек',
    frequency: 'annual',
    category: 'Население',
    source: 'Международный валютный фонд',
  },
  modes: [{ id: 'level-annual', label: 'По годам', group: 'Уровень', type: 'level', freq: 'annual', unit: 'человек' }],
  forecast_available: false,
};

function points() {
  const out = [];
  for (let year = 2016; year <= 2026; year += 1) out.push({ date: `${year}-01-01`, value: 24_000_000 + (year - 2016) * 380_000 + (year === 2026 ? 276_986 : 0) });
  return out;
}

describe('WorldIndicatorPage: население', () => {
  it('плитки по-человечески; чужие показатели остаются на прежних плитках', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/world\/indicators\/australia\/au-pop$/, META],
      [/^\/world\/indicators\/australia\/au-pop\/data/, { code: 'au-pop', mode: 'level-annual', unit: 'человек', frequency: 'annual', points: points(), count: 11 }],
      [/^\/world\/countries\/australia$/, { country: META.country, categories: [], overview: [] }],
      ['/world/compare/snapshot/population', { items: [{ country_slug: 'australia', value: 27_800_000 }, { country_slug: 'austria', value: 9_100_000 }] }],
    ]);
    const { container } = renderPage(<WorldIndicatorPage />, {
      path: '/:countrySlug/indicator/:code', route: '/australia/indicator/au-pop',
    });
    await waitFor(() => expect(container.querySelector('[data-block="population-stats"]')).toBeTruthy());
    const text = container.querySelector('[data-block="population-stats"]').textContent.replace(/\u00A0/g, ' ');
    expect(text).toContain('Население, оценка на 2026 год');
    expect(text).toMatch(/28,1\s?млн/);
    expect(text).toMatch(/\+657\sтыс\./);
    expect(text).toMatch(/\+2,4\s%/);
    expect(text).not.toMatch(/\d{2}\s\d{3}\s\d{3}/);
    expect(text).not.toContain(',00');
    expect(text).not.toMatch(/Исторический максимум|В среднем/);
    await waitFor(() => expect(container.querySelector('[data-block="population-stats"]').textContent).toContain('Место среди стран'));
  });
});
