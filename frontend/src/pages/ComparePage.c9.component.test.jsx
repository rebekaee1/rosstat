// Круг 9, зона D: сравнение России с другой страной, лимит гостя и выход из него.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import ComparePage from './ComparePage';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../lib/track', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, track: vi.fn() };
});

afterEach(() => vi.restoreAllMocks());

const INDICATORS = [
  { code: 'cpi', name: 'Индекс потребительских цен', unit: 'индекс', category: 'Цены', frequency: 'monthly', is_active: true, is_listed: true, current_value: 100.2 },
  { code: 'key-rate', name: 'Ключевая ставка', unit: '%', category: 'Финансы', frequency: 'daily', is_active: true, is_listed: true, current_value: 14 },
];

function item(slug, country, concept, conceptName, frequency, unit, extra = {}) {
  return {
    code: `w:${slug}:${concept}`,
    country_slug: slug,
    country_name: country,
    country_name_en: country,
    concept_slug: concept,
    concept_name: conceptName,
    frequency,
    unit,
    ...extra,
  };
}

const CATALOG = {
  items: [
    item('russia', 'Россия', 'hicp-index', 'Гармонизированный индекс потребительских цен', 'annual', 'изменение за год, %'),
    item('turkey', 'Турция', 'hicp-index', 'Гармонизированный индекс потребительских цен', 'monthly', 'индекс 2015=100', { peer_mode: 'yoy-monthly' }),
    item('turkey', 'Турция', 'gdp-usd', 'Валовой внутренний продукт в текущих ценах', 'annual', 'млрд $'),
    item('germany', 'Германия', 'gdp-usd', 'Валовой внутренний продукт в текущих ценах', 'annual', 'млрд $'),
  ],
  total: 4,
};

function seriesFor(url) {
  const [, , , , slug, concept] = url.split('/');
  const found = CATALOG.items.find((it) => it.country_slug === slug && it.concept_slug === concept);
  if (!found) throw new Error(`no series ${url}`);
  return {
    meta: {
      code: found.code,
      country_slug: slug,
      country_name: found.country_name,
      concept_slug: concept,
      concept_name: found.concept_name,
      unit: found.unit,
      frequency: found.frequency,
    },
    data: [
      { date: '2022-01-01', value: 10 },
      { date: '2023-01-01', value: 12 },
      { date: '2024-01-01', value: 15 },
    ],
  };
}

function mockApis() {
  return mockApiGet([
    ['/auth/me', { user: null }],
    [/^\/indicators\?/, INDICATORS],
    ['/indicators', INDICATORS],
    [/^\/indicators\/[a-z0-9-]+\/data/, { indicator: 'cpi', data: [{ date: '2025-01-01', value: 100 }, { date: '2025-02-01', value: 101 }] }],
    ['/regions/catalog', { sections: [] }],
    [/^\/regions\/?$/, { districts: [], russia: null, totals: { regions: 0, indicators: 0, points: 0 } }],
    [/^\/regions/, { districts: [], sections: [] }],
    ['/world/compare/catalog', CATALOG],
    [/^\/world\/compare\/series\//, seriesFor],
    [/^\/world\/[^/]+\/regions$/, { regions: [], indicators: [], sections: [] }],
  ]);
}

describe('ComparePage: Россия и другая страна (круг 9, C1)', () => {
  it('«ИПЦ России» не мешает выбрать инфляцию Турции: у страны есть что выбрать', async () => {
    mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=cpi' });
    await screen.findByText('Индекс потребительских цен');
    fireEvent.click(await screen.findByRole('button', { name: /Добавить или изменить/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Турция' }));
    // Раньше здесь стояло «У этой страны нет показателя» и выбор был закрыт. Круг 10: подходит ровно один показатель — его можно добавить одним нажатием.
    const only = await screen.findByTestId('compare-add-only');
    expect(only.textContent).toMatch(/Потребительские цены/);
    fireEvent.click(only);
    // Российский ряд заменён своим двойником из общего набора стран, и об этом сказано словами.
    expect(await screen.findByTestId('compare-status')).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId('compare-status').textContent).toMatch(/заменён на тот же/));
  });

  it('гость в лимите: сразу «Начать заново», после нажатия выбор страны снова открыт', async () => {
    mockApis();
    renderPage(<ComparePage />, {
      path: '/compare',
      route: '/compare?codes=w:turkey:gdp-usd,w:germany:gdp-usd',
    });
    await screen.findByRole('button', { name: /Добавить или изменить/ });
    fireEvent.click(screen.getByRole('button', { name: /Добавить или изменить/ }));
    const notice = await screen.findByTestId('compare-cap-notice');
    fireEvent.click(within(notice).getByTestId('compare-cap-clear'));
    expect(await screen.findByText('Страна')).toBeTruthy();
    expect(screen.queryByTestId('compare-cap-notice')).toBeNull();
    expect(screen.queryAllByRole('button', { name: 'Убрать' }).length).toBe(0);
  });

  it('готовые пары «Россия и Турция» входят в список быстрых наборов', async () => {
    mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    const group = await screen.findByRole('group', { name: 'Готовые сравнения' });
    expect(within(group).getByRole('button', { name: 'Россия и Турция: инфляция' })).toBeTruthy();
  });
});
