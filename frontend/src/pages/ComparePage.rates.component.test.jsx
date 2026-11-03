// Сравнение: ряд, уже выраженный темпом (инфляция России за год, МВФ-ряды Японии и Кореи), не получает «к прошлому периоду».
import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import ComparePage from './ComparePage';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../lib/track', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, track: vi.fn() };
});

afterEach(() => vi.restoreAllMocks());

const CONCEPT = 'Гармонизированный индекс потребительских цен';

function item(slug, country, unit, frequency, extra = {}) {
  return {
    code: `w:${slug}:hicp-index`,
    country_slug: slug,
    country_name: country,
    country_name_en: country,
    concept_slug: 'hicp-index',
    concept_name: CONCEPT,
    frequency,
    unit,
    ...extra,
  };
}

const CATALOG = {
  items: [
    item('russia', 'Россия', 'изменение за год, %', 'annual'),
    item('united-states', 'США', 'индекс (1982–84 = 100)', 'monthly', { peer_mode: 'yoy-monthly' }),
    // Каталог называет японский ряд индексом, хотя это годовой темп МВФ (jp-weo-pcpipch).
    item('japan', 'Япония', 'индекс 2015=100', 'annual', { peer_mode: 'level-annual' }),
  ],
  total: 3,
};

// Годовые значения темпа: из 9,51 в 5,6 «к прошлому периоду» получилось бы −41 %.
const RATE_POINTS = [
  { date: '2022-01-01', value: 11.92 },
  { date: '2023-01-01', value: 7.42 },
  { date: '2024-01-01', value: 9.51 },
  { date: '2025-01-01', value: 5.6 },
];
const INDEX_POINTS = [
  { date: '2024-01-01', value: 300 },
  { date: '2024-02-01', value: 301 },
  { date: '2025-01-01', value: 309 },
  { date: '2025-02-01', value: 310 },
];

function seriesFor(url) {
  const [, , , , slug] = url.split('/');
  const found = CATALOG.items.find((it) => it.country_slug === slug);
  if (!found) throw new Error(`no series ${url}`);
  const isIndex = slug === 'united-states';
  return {
    meta: {
      code: found.code,
      country_slug: slug,
      country_name: found.country_name,
      concept_slug: 'hicp-index',
      concept_name: CONCEPT,
      // Единица самого ряда: у Японии она «изменение за год, %», хотя каталог сказал «индекс».
      unit: slug === 'japan' ? 'изменение за год, %' : found.unit,
      frequency: found.frequency,
    },
    data: isIndex ? INDEX_POINTS : RATE_POINTS,
  };
}

function mockApis() {
  return mockApiGet([
    ['/auth/me', { user: null }],
    [/^\/indicators\?/, []],
    ['/indicators', []],
    ['/regions/catalog', { sections: [] }],
    [/^\/regions\/?$/, { districts: [], russia: null, totals: { regions: 0, indicators: 0, points: 0 } }],
    [/^\/regions/, { districts: [], sections: [] }],
    ['/world/compare/catalog', CATALOG],
    [/^\/world\/compare\/series\//, seriesFor],
    [/^\/world\/[^/]+\/regions$/, { regions: [], indicators: [], sections: [] }],
  ]);
}

async function cardOf(name) {
  let card;
  await waitFor(() => {
    card = [...document.querySelectorAll('.fe-compare-picked__card')]
      .find((node) => name.test(node.textContent || ''));
    expect(card).toBeTruthy();
  });
  return within(card);
}

describe('ComparePage: темп не пересчитывается в темп', () => {
  it('у России нет «к прошлому периоду», даже если ссылка просит его; США сразу «к прошлому году»', async () => {
    mockApis();
    renderPage(<ComparePage />, {
      path: '/compare',
      route: '/compare?codes=w:russia:hicp-index,w:united-states:hicp-index&rep=w:russia:hicp-index:pop',
    });
    await screen.findAllByText(/Россия/);
    // Карточка России: только значение, кнопок представлений нет совсем.
    const russiaCard = await cardOf(/Россия/);
    expect(russiaCard.queryByRole('button', { name: 'К прошлому периоду' })).toBeNull();
    expect(russiaCard.queryByRole('button', { name: 'К прошлому году' })).toBeNull();
    // Карточка США: индекс, для него темпы есть, и по соседству с готовым годовым темпом выбран «к прошлому году».
    const usCard = await cardOf(/США/);
    expect(usCard.getByRole('button', { name: 'К прошлому периоду' })).toBeTruthy();
    expect(usCard.getByRole('button', { name: 'К прошлому году' }).getAttribute('aria-pressed')).toBe('true');
  });

  it('Япония: каталог назвал ряд индексом, но сам ряд уже темп — кнопок темпа нет', async () => {
    mockApis();
    renderPage(<ComparePage />, {
      path: '/compare',
      route: '/compare?codes=w:japan:hicp-index,w:united-states:hicp-index',
    });
    await screen.findAllByText(/Япония/);
    const japanCard = await cardOf(/Япония/);
    expect(japanCard.queryByRole('button', { name: 'К прошлому периоду' })).toBeNull();
    expect(japanCard.queryByRole('button', { name: 'К прошлому году' })).toBeNull();
  });
});
