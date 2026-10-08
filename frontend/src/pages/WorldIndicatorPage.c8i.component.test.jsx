// Круг 8, зона Z3: ряд МВФ «изменение за год, %» не называется индексом, не получает «−40 % за год» и режимов от процента.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { waitFor } from '@testing-library/react';
import WorldIndicatorPage from './WorldIndicatorPage';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/WorldChartSection', () => ({
  default: () => <section id="chart" data-testid="chart-stub" />,
}));

afterEach(() => vi.restoreAllMocks());

const META = {
  country: { code: 'TR', slug: 'turkey', name: 'Турция', name_en: 'Türkiye', region: 'Азия' },
  primary_code: 'tr-weo-pcpipch',
  indicator: {
    code: 'tr-weo-pcpipch',
    name: 'Изменение потребительских цен за год',
    unit: 'изменение за год, %',
    frequency: 'annual',
    category: 'Цены',
    source: 'МВФ',
    concept_slug: 'hicp-index',
  },
  modes: [
    { id: 'level-annual', label: 'По годам', group: 'Уровень', type: 'level', freq: 'annual', unit: 'изменение за год, %' },
    { id: 'yoy-annual', label: 'Год к году', group: 'Год к году', type: 'yoy', freq: 'annual', unit: '%' },
    { id: 'step-annual', label: 'К прошлому значению', group: 'Шаг', type: 'step', freq: 'annual', unit: '%' },
    { id: 'index-annual', label: 'Индекс', group: 'Индекс', type: 'index', freq: 'annual', unit: 'индекс' },
  ],
  variants: [],
  forecast_available: false,
};

// Старый ответ данных: единица понятия «индекс 2015=100» у процентного ряда.
const DATA = {
  code: 'tr-weo-pcpipch',
  mode: 'level-annual',
  unit: 'индекс 2015=100',
  frequency: 'annual',
  points: [
    { date: '2022-01-01', value: 72.3 }, { date: '2023-01-01', value: 53.9 },
    { date: '2024-01-01', value: 58.5 }, { date: '2025-01-01', value: 34.88 },
  ],
  count: 4,
};

function renderCard() {
  mockApiGet([
    ['/auth/me', { user: null }],
    [/^\/world\/indicators\/turkey\/tr-weo-pcpipch$/, META],
    [/^\/world\/indicators\/turkey\/tr-weo-pcpipch\/data/, DATA],
    [/^\/world\/compare/, { items: [] }],
    [/^\/world\/countries\/turkey$/, { country: META.country, categories: [], overview: [] }],
  ]);
  return renderPage(<WorldIndicatorPage />, {
    path: '/:countrySlug/indicator/:code',
    route: '/turkey/indicator/tr-weo-pcpipch',
  });
}

describe('WorldIndicatorPage: проценты изменения не выдаются за индекс (D2)', () => {
  it('заголовок без «индекс 2015 = 100» и без «−40 % за год», единица в процентах', async () => {
    const { container } = renderCard();
    await waitFor(() => expect(container.querySelector('[data-testid="indicator-hero"]')).toBeTruthy());
    const line = container.querySelector('[data-testid="indicator-hero"]').textContent.replace(/\u00A0/g, ' ');
    expect(line).toContain('34,88');
    expect(line).not.toMatch(/индекс|2015/i);
    expect(line).not.toContain('за год)');
    expect(line).not.toMatch(/−\d+,\d %/);
  });

  it('режимы «год к году», «к прошлому значению» и «индекс» от процента не показываются', async () => {
    const { container } = renderCard();
    await waitFor(() => expect(container.querySelector('[data-testid="indicator-hero"]')).toBeTruthy());
    const text = document.body.textContent;
    expect(text).not.toContain('Год к году');
    expect(text).not.toContain('К прошлому значению');
    expect(document.querySelector('.fe-pick-card--mode .fe-chip[aria-pressed]')?.textContent || '').not.toContain('Индекс');
  });
});

describe('WorldIndicatorPage: пока данные грузятся, таблица не пишет «Нет данных» (S10)', () => {
  it('показывает «Таблица загружается», а не пустой период', async () => {
    const spy = mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/world\/indicators\/turkey\/tr-weo-pcpipch$/, META],
      [/^\/world\/compare/, { items: [] }],
    ]);
    const base = spy.getMockImplementation();
    spy.mockImplementation((url, ...rest) => (/\/data/.test(url) ? new Promise(() => {}) : base(url, ...rest)));
    renderPage(<WorldIndicatorPage />, { path: '/:countrySlug/indicator/:code', route: '/turkey/indicator/tr-weo-pcpipch' });
    await waitFor(() => expect(document.querySelector('.fe-histtable')).toBeTruthy());
    expect(document.body.textContent).toContain('Таблица загружается');
    expect(document.body.textContent).not.toContain('Нет данных за период');
  });
});
