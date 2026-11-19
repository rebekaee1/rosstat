import ScrollToAnchor from '../components/ScrollToAnchor';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import RegionIndicatorPage from './RegionIndicatorPage';
import { renderPage, mockApiGet } from '../test/renderPage';

// jsdom не умеет scrollIntoView: вешаем spy на прототип, чтобы и
// предсозданный SSR-узел, и узлы из React-дерева шли в одну точку.
let scrollIntoView;

beforeEach(() => {
  scrollIntoView = vi.fn();
  Element.prototype.scrollIntoView = scrollIntoView;
});

afterEach(() => {
  delete Element.prototype.scrollIntoView;
  vi.restoreAllMocks();
});

const INDICATOR_PAYLOAD = {
  region: { slug: 'moskva', name: 'Москва', kind: 'region' },
  indicator: {
    code: 'chislennost-naseleniya',
    name: 'Численность населения',
    unit: 'тыс. человек',
    note: null,
    section_num: 1,
    section_name: 'Население',
    table_code: '1.1',
    macro_code: 'population',
  },
  series: [
    { year: 2022, value: 41300 },
    { year: 2023, value: 41460 },
    { year: 2024, value: 41750 },
  ],
  russia_series: [
    { year: 2022, value: 146450 },
    { year: 2023, value: 146150 },
    { year: 2024, value: 146030 },
  ],
  rank: {
    position: 1,
    total: 85,
    year: 2024,
    rank_as_achievement: false,
    lower_better: false,
    top: [{ slug: 'moskva', name: 'Москва', value: 41750 }],
    bottom: [],
  },
  siblings: [],
};

function renderCard(route, extraRoutes = []) {
  mockApiGet([
    ['/auth/me', { user: null }],
    [/^\/regions\/moskva\/i\/chislennost-naseleniya$/, INDICATOR_PAYLOAD],
    // useRegionsLanding для выбора региона сравнения.
    [/^\/regions\/?$/, { districts: [], russia: null, totals: { regions: 0, indicators: 0, points: 0 } }],
    ...extraRoutes,
  ]);
  return renderPage(<><ScrollToAnchor /><RegionIndicatorPage /></>, {
    path: '/russia/region/:slug/:code',
    route,
  });
}

function chartBlockMounted() {
  return Boolean(document.querySelector('[data-block="region-chart"]'));
}

describe('RegionIndicatorPage #chart anchor', () => {
  it('с URL с хэшем скроллит к графику после загрузки данных', async () => {
    renderCard('/russia/region/moskva/chislennost-naseleniya#chart');

    // Пока данные грузятся, блока ещё нет; скролл происходит один раз,
    // когда график смонтирован (isLoading=false → блок с якорем в DOM).
    await waitFor(() => {
      expect(chartBlockMounted()).toBe(true);
      expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'auto', block: 'start' });
    });
    expect(scrollIntoView).toHaveBeenCalledTimes(1);
    // Контейнер графика размечен якорем, куда ведёт ссылка из SSR-картинки.
    const block = document.querySelector('[data-block="region-chart"]');
    expect(block.id).toBe('chart');
    expect(block.className).toContain('scroll-mt-24');
  });

  it('без хэша в URL скролл не вызывается', async () => {
    renderCard('/russia/region/moskva/chislennost-naseleniya');

    await screen.findByRole('heading', { name: /Численность населения/ });
    await waitFor(() => {
      expect(chartBlockMounted()).toBe(true);
    });
    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it('ошибка загрузки данных при хэше не роняет страницу и не скроллит', async () => {
    renderCard('/russia/region/moskva/chislennost-naseleniya#chart', [
      [/^\/regions\/moskva\/i\//, {}],
    ]);

    // Ряд отсутствует → блок графика не монтируется, эффект уходит в no-op.
    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: /Численность населения/ })).toBeNull();
    });
    expect(chartBlockMounted()).toBe(false);
    expect(scrollIntoView).not.toHaveBeenCalled();
    expect(document.body.textContent.length).toBeGreaterThan(0);
  });
});

// ИПЦ региона помесячно (ЕМИСС 31074, 19.11.2026): значение уже изменение цен в % — без «изменения индекса за год»,
// без столбца «К году» и без переключателя «Без инфляции».
function monthlyCpiSeries() {
  const out = [];
  for (let i = 0; i < 26; i += 1) {
    const year = 2024 + Math.floor((i + 7) / 12);
    const month = ((i + 7) % 12) + 1;
    out.push({ year, month, value: 106 + (i % 5) / 10, label: `${year}-${String(month).padStart(2, '0')}` });
  }
  return out;
}

const CPI_MONTHLY = {
  region: { slug: 'lipetskaya-oblast', name: 'Липецкая область', kind: 'region' },
  indicator: {
    code: 'ipc-vse-za-god',
    name: 'Индекс потребительских цен за год: все товары и услуги',
    unit: '% к тому же месяцу прошлого года',
    note: null,
    section_num: 20,
    section_name: 'Цены и тарифы',
    table_code: '20.c1',
    macro_code: 'cpi',
    short_name: null,
    price_group: null,
    is_discontinued: false,
  },
  frequency: 'monthly',
  cpi_russia: [[202408, 100], [202409, 100.2], [202410, 100.9]],
  compare: { russia: null, moskva: null },
  series: monthlyCpiSeries(),
  russia_series: [],
  weekly: [],
  weekly_russia: [],
  siblings: [],
};

describe('RegionIndicatorPage: помесячный ИПЦ региона', () => {
  it('показывает индекс без «изменения индекса» и без пересчёта «без инфляции»', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/regions\/lipetskaya-oblast\/i\/ipc-vse-za-god\/monthly$/, CPI_MONTHLY],
      [/^\/regions\/lipetskaya-oblast\/i\/ipc-vse-za-god$/, {}],
      [/^\/regions\/?$/, { districts: [], russia: null, totals: { regions: 0, indicators: 0, points: 0 } }],
    ]);
    renderPage(<RegionIndicatorPage />, {
      path: '/russia/region/:slug/:code',
      route: '/russia/region/lipetskaya-oblast/ipc-vse-za-god',
    });
    await screen.findByRole('heading', { name: /Индекс потребительских цен за год/ });
    await waitFor(() => expect(chartBlockMounted()).toBe(true));
    expect(screen.queryByText('Без инфляции')).toBeNull();
    expect(screen.queryByText(/^За год \(с /)).toBeNull();
    expect(screen.queryByRole('columnheader', { name: 'К году' })).toBeNull();
  });
});
