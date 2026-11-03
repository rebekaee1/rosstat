// Сравнение: частота мировых рядов выбирается («Как в источнике», «Месяц», «Квартал», «Год»), свёртку считает сервер.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
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
    peer_mode: 'yoy-monthly',
    ...extra,
  };
}

const CATALOG = {
  items: [
    item('germany', 'Германия', 'индекс 2015=100', 'monthly'),
    item('japan', 'Япония', 'изменение за год, %', 'annual', { peer_mode: 'level-annual' }),
  ],
  total: 2,
};

const MONTHLY = [
  { date: '2024-01-01', value: 100 }, { date: '2024-02-01', value: 101 }, { date: '2024-03-01', value: 102 },
  { date: '2024-04-01', value: 103 }, { date: '2024-05-01', value: 104 }, { date: '2024-06-01', value: 105 },
];
const QUARTERLY = [{ date: '2024-01-01', value: 101 }, { date: '2024-04-01', value: 104 }];
const ANNUAL = [{ date: '2023-01-01', value: 3.2 }, { date: '2024-01-01', value: 2.8 }];

function seriesFor(url) {
  const slug = url.split('/')[4];
  const found = CATALOG.items.find((entry) => entry.country_slug === slug);
  if (!found) throw new Error(`no series ${url}`);
  return {
    meta: {
      code: found.code, country_slug: slug, country_name: found.country_name, concept_slug: 'hicp-index', concept_name: CONCEPT,
      unit: found.unit, frequency: found.frequency,
    },
    data: slug === 'japan' ? ANNUAL : MONTHLY,
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

const seriesCalls = (spy, slug) => spy.mock.calls.filter(([url]) => url === `/world/compare/series/${slug}/hicp-index`);

describe('ComparePage: частота мировых рядов', () => {
  it('у мировых рядов есть выбор частоты, а не одна заглушка', async () => {
    mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=w:germany:hicp-index' });
    for (const name of ['Как в источнике', 'Месяц', 'Квартал', 'Год']) {
      expect(await screen.findByRole('button', { name })).toBeTruthy();
    }
    expect(screen.getByRole('button', { name: 'Как в источнике' }).getAttribute('aria-pressed')).toBe('true');
  });

  it('«Квартал» у месячного ряда просит у сервера квартал; «Как в источнике» возвращает родную частоту', async () => {
    const spy = mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=w:germany:hicp-index' });
    const quarter = await screen.findByRole('button', { name: 'Квартал' });
    await waitFor(() => expect(seriesCalls(spy, 'germany').length).toBeGreaterThan(0));
    expect(seriesCalls(spy, 'germany').every(([, options]) => !options?.params)).toBe(true);
    fireEvent.click(quarter);
    await waitFor(() => expect(seriesCalls(spy, 'germany').some(([, options]) => options?.params?.frequency === 'quarterly')).toBe(true));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Квартал' }).getAttribute('aria-pressed')).toBe('true'));
    fireEvent.click(screen.getByRole('button', { name: 'Как в источнике' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Как в источнике' }).getAttribute('aria-pressed')).toBe('true'));
  });

  it('годовой ряд не просит месяц и квартал: более мелкий шаг не достраивается', async () => {
    const spy = mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=w:japan:hicp-index' });
    fireEvent.click(await screen.findByRole('button', { name: 'Месяц' }));
    fireEvent.click(screen.getByRole('button', { name: 'Квартал' }));
    fireEvent.click(screen.getByRole('button', { name: 'Год' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Год' }).getAttribute('aria-pressed')).toBe('true'));
    expect(seriesCalls(spy, 'japan').every(([, options]) => !options?.params)).toBe(true);
  });

  it('если сервер отдал квартальный ряд, «К прошлому периоду» считается по кварталам', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators\?/, []],
      ['/indicators', []],
      ['/regions/catalog', { sections: [] }],
      [/^\/regions\/?$/, { districts: [], russia: null, totals: { regions: 0, indicators: 0, points: 0 } }],
      [/^\/regions/, { districts: [], sections: [] }],
      ['/world/compare/catalog', CATALOG],
      [/^\/world\/compare\/series\//, (url) => {
        const payload = seriesFor(url);
        return { meta: { ...payload.meta, frequency: 'quarterly' }, data: QUARTERLY };
      }],
      [/^\/world\/[^/]+\/regions$/, { regions: [], indicators: [], sections: [] }],
    ]);
    renderPage(<ComparePage />, {
      path: '/compare',
      route: '/compare?codes=w:germany:hicp-index&rep=w:germany:hicp-index:pop',
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Квартал' }));
    // Квартал к кварталу: 104 / 101 − 1 ≈ 2,97 %, а не месяц к месяцу.
    expect(await screen.findAllByText(/2[,.]97/)).not.toHaveLength(0);
  });

  it('подпись частоты в легенде берёт частоту, в которой ряд лежит на графике, а не родную', async () => {
    const RUSSIA_CPI = { code: 'cpi', name: 'Индекс потребительских цен', unit: '%', frequency: 'monthly', source: 'Росстат', is_listed: true };
    const YOY = { data: [{ date: '2024-01-01', value: 7.4 }, { date: '2024-02-01', value: 7.7 }, { date: '2024-03-01', value: 7.7 }] };
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators\?/, [RUSSIA_CPI]],
      ['/indicators', [RUSSIA_CPI]],
      ['/indicators/cpi-yoy/data', YOY],
      ['/regions/catalog', { sections: [] }],
      [/^\/regions\/?$/, { districts: [], russia: null, totals: { regions: 0, indicators: 0, points: 0 } }],
      [/^\/regions/, { districts: [], sections: [] }],
      ['/world/compare/catalog', CATALOG],
      [/^\/world\/compare\/series\//, (url) => {
        const payload = seriesFor(url);
        return { meta: { ...payload.meta, frequency: 'annual' }, data: ANNUAL };
      }],
      [/^\/world\/[^/]+\/regions$/, { regions: [], indicators: [], sections: [] }],
    ]);
    renderPage(<ComparePage />, {
      path: '/compare',
      route: '/compare?codes=w:germany:hicp-index,w:russia:hicp-index&rep=w:germany:hicp-index:yoy',
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Год' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Год' }).getAttribute('aria-pressed')).toBe('true'));
    // У Германии ряд пришёл годовым, у России месячный ряд свёрнут в год на клиенте: обе подписи «ежегодно», не «ежемесячно».
    await waitFor(() => expect(document.body.textContent).toMatch(/Россия|Russia/));
    expect(document.body.textContent).not.toMatch(/ежемесячно/);
  });
});

