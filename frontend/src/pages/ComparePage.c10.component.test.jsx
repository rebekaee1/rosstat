// Круг 10, сравнение: порядок выбора страны и показателя не важен, период по умолчанию 25 лет, понятное «старт = 100».
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
  { code: 'gdp-nominal', name: 'ВВП номинальный', unit: 'млрд руб.', category: 'ВВП', frequency: 'quarterly', is_active: true, is_listed: true, current_value: 100 },
  { code: 'key-rate', name: 'Ключевая ставка', unit: '%', category: 'Финансы', frequency: 'daily', is_active: true, is_listed: true, current_value: 14 },
];

const EN_NAMES = { 'united-states': 'United States', russia: 'Russia', china: 'China' };
const GDP_NAME = 'Валовой внутренний продукт в текущих ценах';

function item(slug, country, concept, conceptName, extra = {}) {
  return {
    code: `w:${slug}:${concept}`,
    country_slug: slug,
    country_name: country,
    country_name_en: EN_NAMES[slug] || country,
    concept_slug: concept,
    concept_name: conceptName,
    frequency: 'annual',
    unit: 'млрд $',
    ...extra,
  };
}

const CATALOG = {
  items: [
    item('united-states', 'США', 'gdp-usd', GDP_NAME),
    item('russia', 'Россия', 'gdp-usd', GDP_NAME),
    item('china', 'Китай', 'gdp-usd', GDP_NAME),
    item('united-states', 'США', 'activity-rate', 'Уровень экономической активности', { unit: '%' }),
    item('china', 'Китай', 'population', 'Численность населения', { unit: 'человек' }),
  ],
  total: 5,
};

function seriesFor(url) {
  const [, , , , slug, concept] = url.split('/');
  const found = CATALOG.items.find((it) => it.country_slug === slug && it.concept_slug === concept);
  if (!found) throw new Error(`no series ${url}`);
  const base = slug === 'united-states' ? 20000 : slug === 'china' ? 5000 : 2000;
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
    data: Array.from({ length: 30 }, (_, i) => ({ date: `${1996 + i}-01-01`, value: base + i * base * 0.05 })),
  };
}

function mockApis() {
  return mockApiGet([
    ['/auth/me', { user: null }],
    [/^\/indicators\?/, INDICATORS],
    ['/indicators', INDICATORS],
    [/^\/indicators\/[a-z0-9-]+\/data/, { indicator: 'gdp-nominal', data: [{ date: '2024-01-01', value: 100 }, { date: '2025-01-01', value: 110 }] }],
    ['/regions/catalog', { sections: [] }],
    [/^\/regions\/?$/, { districts: [], russia: null, totals: { regions: 0, indicators: 0, points: 0 } }],
    [/^\/regions/, { districts: [], sections: [] }],
    ['/world/compare/catalog', CATALOG],
    [/^\/world\/compare\/series\//, seriesFor],
    [/^\/world\/[^/]+\/regions$/, { regions: [], indicators: [], sections: [] }],
  ]);
}

function pickedCards(container) {
  return container.querySelectorAll('.fe-compare-picked__card');
}

describe('ComparePage: порядок выбора не важен (круг 10, Ср1)', () => {
  it('сначала США, потом Россия: тот же показатель России находится одним нажатием', async () => {
    mockApis();
    const { container } = renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=w:united-states:gdp-usd' });
    await waitFor(() => expect(pickedCards(container)).toHaveLength(1));
    fireEvent.click(await screen.findByRole('button', { name: /Добавить или изменить/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Россия' }));
    const same = await screen.findByTestId('compare-add-russia-same');
    expect(same.textContent).toMatch(/Россию/);
    fireEvent.click(same);
    await waitFor(() => expect(pickedCards(container)).toHaveLength(2));
    expect(screen.getByTestId('compare-status').textContent).toMatch(/Добавлено на график/);
  });

  it('сначала США, потом Россия: слово «ВВП» находит ВВП России из общего набора, а не рублёвый ряд', async () => {
    mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=w:united-states:gdp-usd' });
    fireEvent.click(await screen.findByRole('button', { name: /Добавить или изменить/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Россия' }));
    const search = await screen.findByPlaceholderText('Найти показатель…');
    fireEvent.focus(search);
    fireEvent.change(search, { target: { value: 'ВВП' } });
    const list = search.closest('.relative');
    await waitFor(() => expect(within(list).getByText(GDP_NAME)).toBeTruthy());
    expect(within(list).queryByText('ВВП номинальный')).toBeNull();
  });

  it('сначала ВВП России, потом США: российский ряд заменён на ВВП в долларах, и об этом сказано', async () => {
    mockApis();
    const { container } = renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=gdp-nominal' });
    await waitFor(() => expect(pickedCards(container)).toHaveLength(1));
    fireEvent.click(await screen.findByRole('button', { name: /Добавить или изменить/ }));
    // В списке стран остались те, у кого есть подходящий ряд: Китай и США, но не «все подряд».
    fireEvent.click(await screen.findByRole('button', { name: 'США' }));
    fireEvent.click(await screen.findByTestId('compare-add-only'));
    await waitFor(() => expect(pickedCards(container)).toHaveLength(2));
    expect(screen.getByTestId('compare-status').textContent).toMatch(/в долларах США/);
  });

  it('адрес с рядами в любом порядке открывает один и тот же набор', async () => {
    mockApis();
    const first = renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=gdp-nominal,w:united-states:gdp-usd' });
    await waitFor(() => expect(pickedCards(first.container)).toHaveLength(2));
    first.unmount();
    const second = renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=w:united-states:gdp-usd,gdp-nominal' });
    await waitFor(() => expect(pickedCards(second.container)).toHaveLength(2));
  });

  it('к выбранному ряду предлагаются только страны, у которых есть такой показатель', async () => {
    mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=w:united-states:activity-rate' });
    fireEvent.click(await screen.findByRole('button', { name: /Добавить или изменить/ }));
    await screen.findByTestId('compare-country-restrict');
    expect(screen.queryByRole('button', { name: 'Россия' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Китай' })).toBeNull();
  });
});

describe('ComparePage: период и «старт = 100» (круг 10, Ср2)', () => {
  it('по умолчанию период — 25 лет', async () => {
    mockApis();
    const { container } = renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=w:united-states:gdp-usd,w:russia:gdp-usd' });
    await waitFor(() => expect(container.querySelector('.fe-compare-card__caption')).toBeTruthy());
    expect(container.querySelector('.fe-compare-card__caption').textContent).toMatch(/Период: 25 лет/);
    expect(screen.getByRole('button', { name: '25 лет' }).getAttribute('aria-pressed')).toBe('true');
  });

  it('рост от старта объяснён словами с примером и кнопкой «Показать значения»', async () => {
    mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=w:united-states:gdp-usd,w:china:gdp-usd' });
    await screen.findByTestId('compare-auto-index');
    fireEvent.click(await screen.findByRole('button', { name: 'Рост от начала (старт = 100)' }));
    const note = await screen.findByTestId('compare-index-note');
    expect(note.textContent).toMatch(/каждый ряд равен 100/);
    expect(note.textContent).toMatch(/150/);
    fireEvent.click(within(note).getByRole('button', { name: 'Показать значения' }));
    await waitFor(() => expect(screen.queryByTestId('compare-index-note')).toBeNull());
  });
});

describe('ComparePage: английская версия (круг 10, Ср3)', () => {
  it('Russia не первая в списке стран, подборка «Russia’s neighbours» убрана, BRICS на месте', async () => {
    mockApis();
    const { container } = renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=', locale: 'en' });
    await waitFor(() => {
      const list = [...container.querySelectorAll('.fe-compare-countries button')]
        .map((button) => button.textContent.replace(/[\u{1F1E6}-\u{1F1FF}]/gu, '').trim());
      expect(list[0]).toBe('United States');
      expect(list).toContain('Russia');
    });
    expect(screen.getByRole('button', { name: 'BRICS' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /neighbo/i })).toBeNull();
  });

  it('готовые пары с Россией в английской версии не предлагаются, в русской остаются', async () => {
    mockApis();
    const en = renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=', locale: 'en' });
    await screen.findByRole('button', { name: 'GDP: US and China' });
    expect(screen.queryByRole('button', { name: /Russia and/ })).toBeNull();
    en.unmount();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=' });
    expect(await screen.findByRole('button', { name: 'Россия и Турция: ВВП' })).toBeTruthy();
  });
});
