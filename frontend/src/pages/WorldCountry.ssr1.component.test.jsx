import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import WorldCountry from './WorldCountry';
import { renderPage, mockApiGet } from '../test/renderPage';
import { COUNTRY_BOOTSTRAP_ID, resetCountryBootstrapCache } from '../lib/countryBootstrap';

vi.mock('../components/WorldMap', () => ({
  CountrySilhouette: ({ className, badge }) => (
    <div data-testid="silhouette-stub" data-class={className}>{badge}</div>
  ),
}));

const GDP = {
  concept_slug: 'gdp-volume-quarterly',
  name: 'Валовой внутренний продукт',
  name_en: 'Gross domestic product',
  unit: 'в постоянных ценах 2015 года, млн евро',
  indicator_code: 'de-gdp-q',
  frequency: 'quarterly',
  date: '2026-04-01',
  value: 849680,
};

const POINTS = [
  ['2025-04-01', 800000], ['2025-07-01', 810000], ['2025-10-01', 820000],
  ['2026-01-01', 840000], ['2026-04-01', 849680],
];

function bootstrap(overrides = {}) {
  return {
    v: 1,
    slug: 'germany',
    locale: 'ru',
    country: {
      code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', region: 'Европа', region_en: 'Europe',
    },
    overview: [{ ...GDP, points: POINTS }],
    ...overrides,
  };
}

function mountBootstrap(data) {
  const el = document.createElement('script');
  el.type = 'application/json';
  el.id = COUNTRY_BOOTSTRAP_ID;
  el.textContent = JSON.stringify(data);
  document.head.appendChild(el);
}

beforeEach(() => resetCountryBootstrapCache());

afterEach(() => {
  vi.restoreAllMocks();
  resetCountryBootstrapCache();
  document.getElementById(COUNTRY_BOOTSTRAP_ID)?.remove();
});

function mountPending() {
  return mockApiGet([
    ['/auth/me', { user: null }],
    ['/world/countries/germany', () => new Promise(() => {})],
  ]);
}

describe('Главное из серверной предзагрузки', () => {
  it('пока API молчит, карточки уже с цифрой, периодом и «год назад», сеть ряда не нужна', async () => {
    mountBootstrap(bootstrap());
    const get = mountPending();
    renderPage(<WorldCountry />, { path: '/:countrySlug', route: '/germany' });

    const card = await screen.findByRole('link', { name: /849,7/ });
    const text = card.textContent.replace(/\s/g, ' ');
    expect(text).toContain('млрд €');
    expect(text).toContain('II кв. 2026');
    expect(text).toContain('с поправкой на инфляцию');
    expect(text).toContain('год назад: 800,0 млрд €');
    expect(card.querySelector('.z5-spark-skel')).toBeNull();
    expect(card.querySelector('.sparkline-container')).toBeTruthy();
    // Серых плиток-скелетов нет, название страны на месте.
    expect(document.querySelectorAll('.z5-key--skel')).toHaveLength(0);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('Германи');
    // Ряд не запрашивался: данные пришли вместе с HTML.
    expect(get.mock.calls.some(([url]) => /\/data/.test(url))).toBe(false);
  });

  it('без предзагрузки поведение прежнее: серые плитки и запрос ряда', async () => {
    const get = mockApiGet([
      ['/auth/me', { user: null }],
      ['/world/countries/germany', {
        country: bootstrap().country,
        categories: [],
        overview: [GDP],
        coverage: { history_start: '2000-01-01', history_end: '2026-04-01', frequencies: ['quarterly'] },
        market_indicators: [],
      }],
      [/\/world\/indicators\/germany\/de-gdp-q\/data/, {
        points: POINTS.map(([date, value]) => ({ date, value })),
      }],
    ]);
    renderPage(<WorldCountry />, { path: '/:countrySlug', route: '/germany' });
    expect(screen.getByTestId('country-skeleton').querySelectorAll('.z5-key--skel')).toHaveLength(3);
    await screen.findByRole('heading', { name: 'Главное' });
    await waitFor(() => expect(get.mock.calls.some(([url]) => /\/data/.test(url))).toBe(true));
  });

  it('предзагрузка другой страны не подставляется', () => {
    mountBootstrap(bootstrap({ slug: 'france' }));
    mountPending();
    renderPage(<WorldCountry />, { path: '/:countrySlug', route: '/germany' });
    expect(screen.getByTestId('country-skeleton').querySelectorAll('.z5-key--skel')).toHaveLength(3);
  });

  it('когда каталог страны пришёл новее снимка, карточка берёт ряд из сети', async () => {
    mountBootstrap(bootstrap());
    const newer = { ...GDP, date: '2026-07-01', value: 860000 };
    const get = mockApiGet([
      ['/auth/me', { user: null }],
      ['/world/countries/germany', {
        country: bootstrap().country,
        categories: [],
        overview: [newer],
        coverage: { history_start: '2000-01-01', history_end: '2026-07-01', frequencies: ['quarterly'] },
        market_indicators: [],
      }],
      [/\/world\/indicators\/germany\/de-gdp-q\/data/, {
        points: [...POINTS, ['2026-07-01', 860000]].map(([date, value]) => ({ date, value })),
      }],
    ]);
    renderPage(<WorldCountry />, { path: '/:countrySlug', route: '/germany' });
    await screen.findByRole('link', { name: /860,0/ });
    await waitFor(() => expect(get.mock.calls.some(([url]) => /\/data/.test(url))).toBe(true));
  });
});
