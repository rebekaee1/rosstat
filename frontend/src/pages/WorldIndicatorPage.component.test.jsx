import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { waitFor } from '@testing-library/react';
import WorldIndicatorPage from './WorldIndicatorPage';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/WorldChartSection', () => ({
  default: () => <section id="chart" data-testid="chart-stub" />,
}));

// jsdom не умеет scrollIntoView — spy на прототип (как в RegionIndicatorPage).
let scrollIntoView;

beforeEach(() => {
  scrollIntoView = vi.fn();
  Element.prototype.scrollIntoView = scrollIntoView;
});

afterEach(() => {
  delete Element.prototype.scrollIntoView;
  vi.restoreAllMocks();
});

const META = {
  country: {
    code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', region: 'Европа',
  },
  primary_code: 'de-une',
  indicator: {
    code: 'de-une',
    name: 'Безработица',
    unit: '%',
    frequency: 'monthly',
    category: 'Рынок труда',
    source: 'Евростат',
  },
  modes: [
    { id: 'level-monthly', label: 'По месяцам', group: 'Уровень', type: 'level', freq: 'monthly', unit: '%' },
  ],
  forecast_available: false,
};

const DATA = {
  code: 'de-une',
  mode: 'level-monthly',
  unit: '%',
  frequency: 'monthly',
  points: [
    { date: '2026-04-01', value: 3.4 },
    { date: '2026-05-01', value: 3.3 },
    { date: '2026-06-01', value: 3.1 },
  ],
  count: 3,
};

function renderCard(route, extraRoutes = []) {
  mockApiGet([
    ['/auth/me', { user: null }],
    [/^\/world\/indicators\/germany\/de-une$/, META],
    [/^\/world\/indicators\/germany\/de-une\/data/, DATA],
    [/^\/world\/countries\/germany$/, {
      country: META.country,
      categories: [],
      overview: [],
    }],
    ...extraRoutes,
  ]);
  return renderPage(<WorldIndicatorPage />, {
    path: '/:countrySlug/indicator/:code',
    route,
  });
}

describe('WorldIndicatorPage #chart anchor', () => {
  it('с URL с хэшем скроллит к графику после загрузки данных', async () => {
    renderCard('/germany/indicator/de-une#chart');

    await waitFor(() => {
      expect(document.querySelector('[data-testid="chart-stub"]')).toBeTruthy();
      expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });
    });
  });

  it('без хэша в URL скролл не вызывается', async () => {
    renderCard('/germany/indicator/de-une');

    await waitFor(() => {
      expect(document.querySelector('[data-testid="chart-stub"]')).toBeTruthy();
    });
    expect(scrollIntoView).not.toHaveBeenCalled();
  });
});

describe('WorldIndicatorPage about-series block', () => {
  it('в блоке «О ряде» источник показывает издателя, оригинальный титул — отдельной строкой', async () => {
    renderCard('/germany/indicator/de-une');

    // Блок «О ряде» ждём после загрузки meta.
    const aboutHeading = await waitFor(() => {
      const h3 = [...document.querySelectorAll('h3')]
        .find((el) => el.textContent === 'О ряде');
      expect(h3).toBeTruthy();
      return h3;
    });
    const aboutBlock = aboutHeading.closest('div');

    // Издатель — тот же localizeSource, что идёт в панель методологии
    // (на EN было бы Eurostat; в RU-локали остаётся «Евростат»).
    expect(aboutBlock.textContent).toContain('Евростат');

    // В META.indicator нет name_en — строки «Оригинальное название ряда»
    // быть не должно.
    expect(aboutBlock.textContent).not.toContain('Оригинальное название ряда');
  });

  it('показывает оригинальное название, когда оно отличается от имени ряда', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/world\/indicators\/germany\/de-une$/, {
        ...META,
        indicator: {
          ...META.indicator,
          name_en: 'Unemployment rate from the Labour Force Survey (monthly)',
        },
      }],
      [/^\/world\/indicators\/germany\/de-une\/data/, DATA],
      [/^\/world\/countries\/germany$/, {
        country: META.country,
        categories: [],
        overview: [],
      }],
    ]);
    renderPage(<WorldIndicatorPage />, {
      path: '/:countrySlug/indicator/:code',
      route: '/germany/indicator/de-une',
    });

    await waitFor(() => {
      expect(document.body.textContent).toContain('Оригинальное название ряда');
      expect(document.body.textContent).toContain(
        'Unemployment rate from the Labour Force Survey (monthly)',
      );
    });
  });
});
