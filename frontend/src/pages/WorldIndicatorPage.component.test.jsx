import ScrollToAnchor from '../components/ScrollToAnchor';
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
  return renderPage(<><ScrollToAnchor /><WorldIndicatorPage /></>, {
    path: '/:countrySlug/indicator/:code',
    route,
  });
}

describe('WorldIndicatorPage #chart anchor', () => {
  it('с URL с хэшем скроллит к графику после загрузки данных', async () => {
    renderCard('/germany/indicator/de-une#chart');

    await waitFor(() => {
      expect(document.querySelector('[data-testid="chart-stub"]')).toBeTruthy();
      expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'auto', block: 'start' });
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

describe('WorldIndicatorPage plain language', () => {
  it('stat tiles say what they are: no «НАБЛ.», «ПЕРИОД.», «ПИК», no capital letters with spacing', async () => {
    renderCard('/germany/indicator/de-une');
    await waitFor(() => expect(document.querySelectorAll('.w2-stat')).toHaveLength(4));
    const text = document.body.textContent.replace(/\u00A0/g, ' ');
    expect(text).toContain('Сейчас');
    expect(text).toContain('Максимум за всё время');
    expect(text).toContain('В среднем');
    expect(text).not.toMatch(/НАБЛ|ПЕРИОД\.|ПИК|ДАТА:/);
    // Плитка «Сейчас»: значение с единицей и датой, знаков после запятой ровно как в данных («3,1», а не «3,10»).
    const now = document.querySelectorAll('.w2-stat')[0].textContent.replace(/\u00A0/g, ' ');
    expect(now).toContain('3,1');
    expect(now).not.toContain('3,10');
    expect(now).toContain('%');
  });

  it('keeps breadcrumbs in one short line: a long indicator name is cut, not wrapped in capitals', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/world\/indicators\/germany\/de-une$/, {
        ...META,
        indicator: {
          ...META.indicator,
          name: 'Импорт и экспорт товаров и услуг, в текущих ценах, в миллионах евро по методике источника',
        },
      }],
      [/^\/world\/indicators\/germany\/de-une\/data/, DATA],
      [/^\/world\/countries\/germany$/, { country: META.country, categories: [], overview: [] }],
    ]);
    renderPage(<WorldIndicatorPage />, { path: '/:countrySlug/indicator/:code', route: '/germany/indicator/de-une' });
    await waitFor(() => expect(document.querySelector('[data-testid="chart-stub"]')).toBeTruthy());
    const nav = document.querySelector('nav[aria-label]');
    const last = nav.querySelector('[aria-current="page"]');
    expect(last.textContent.endsWith('…')).toBe(true);
    expect(last.textContent.length).toBeLessThanOrEqual(41);
    expect(nav.className).not.toMatch(/uppercase|font-mono/);
  });
});

describe('WorldIndicatorPage about-series block', () => {
  it('в блоке «О показателе» источник виден сразу, технические строки скрыты под «Подробнее»', async () => {
    renderCard('/germany/indicator/de-une');

    // Блок «О ряде» ждём после загрузки meta.
    const aboutHeading = await waitFor(() => {
      const h3 = [...document.querySelectorAll('h3')]
        .find((el) => el.textContent === 'О показателе');
      expect(h3).toBeTruthy();
      return h3;
    });
    const aboutBlock = aboutHeading.closest('div');

    // Издатель — тот же localizeSource, что идёт в панель методологии
    // (на EN было бы Eurostat; в RU-локали остаётся «Евростат»).
    expect(aboutBlock.textContent).toContain('Евростат');

    // В META.indicator нет name_en — строки «Наименование в источнике» быть не должно.
    expect(aboutBlock.textContent).not.toContain('Наименование в источнике');
    // «Точек» и «ряд» человеку не нужны: число значений живёт под «Подробнее».
    expect(aboutBlock.textContent).not.toContain('Точек');
    const more = aboutBlock.querySelector('details');
    expect(more).toBeTruthy();
    expect(more.textContent).toContain('Всего значений');
    expect(more.open).toBe(false);
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
    renderPage(<><ScrollToAnchor /><WorldIndicatorPage /></>, {
      path: '/:countrySlug/indicator/:code',
      route: '/germany/indicator/de-une',
    });

    // Английское название оригинала — только под «Подробнее», закрытым по умолчанию.
    await waitFor(() => {
      const more = document.querySelector('details.w2-details');
      expect(more).toBeTruthy();
      expect(more.open).toBe(false);
      expect(more.textContent).toContain('Наименование в источнике');
      expect(more.textContent).toContain(
        'Unemployment rate from the Labour Force Survey (monthly)',
      );
    });
  });
});

describe('WorldIndicatorPage EN overlay', () => {
  it('при русском payload и locale=en показывает английский H1, единицы, числа и слайс', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/world\/indicators\/canada\/ca-weo-ngdpd$/, {
        country: {
          code: 'CA', slug: 'canada', name: 'Канада', name_en: 'Canada', region: 'Америка',
        },
        primary_code: 'ca-weo-ngdpd',
        indicator: {
          code: 'ca-weo-ngdpd',
          name: 'Валовой внутренний продукт в текущих ценах',
          name_en: 'Gross domestic product at current prices',
          name_ru: 'Валовой внутренний продукт в текущих ценах',
          unit: 'млрд $',
          unit_ru: 'млрд $',
          frequency: 'annual',
          category: 'Национальные счета',
          category_en: 'National accounts',
          source: 'Международный валютный фонд',
        },
        variants: [
          {
            code: 'ca-weo-ngdpd',
            label: 'Валовой внутренний продукт в текущих ценах',
            label_en: 'Gross domestic product at current prices',
            current: true,
          },
          { code: 'ca-weo-lur', label: '% ЭАН', label_en: 'Unemployment rate', current: false },
          {
            code: 'ca-weo-ggxcnl',
            label: 'Баланс бюджета сектора государственного управления',
            label_en: 'General government budget balance',
            current: false,
          },
          { code: 'ca-weo-lp', label: 'Численность населения', label_en: 'Population', current: false },
        ],
        modes: [
          {
            id: 'level-annual', label: 'По годам', group: 'Уровень',
            type: 'level', freq: 'annual', unit: 'млрд $',
          },
        ],
        forecast_available: false,
      }],
      [/^\/world\/indicators\/canada\/ca-weo-ngdpd\/data/, {
        code: 'ca-weo-ngdpd',
        mode: 'level-annual',
        unit: 'млрд $',
        frequency: 'annual',
        points: [
          { date: '2024-01-01', value: 2200.1 },
          { date: '2025-01-01', value: 2319.9 },
        ],
        count: 2,
      }],
      [/^\/world\/countries\/canada$/, {
        country: {
          code: 'CA', slug: 'canada', name: 'Канада', name_en: 'Canada', region: 'Америка',
        },
        categories: [],
        overview: [],
      }],
    ]);
    renderPage(<><ScrollToAnchor /><WorldIndicatorPage /></>, {
      path: '/:countrySlug/indicator/:code',
      route: '/canada/indicator/ca-weo-ngdpd?mode=level-annual',
      locale: 'en',
    });

    const heading = await waitFor(() => {
      const h1 = document.querySelector('h1');
      expect(h1?.textContent).toBe('Gross domestic product at current prices');
      return h1;
    });
    expect(heading.textContent).not.toMatch(/[А-Яа-яЁё]/);
    await waitFor(() => {
      const text = document.body.textContent.replace(/\u00a0/g, ' ');
      expect(text).toContain('billion $');
      expect(text).toContain('2,319.9');
      expect(text).toContain('Unemployment rate');
      expect(text).toContain('Population');
      expect(text).toContain('National accounts');
    });
    expect(document.body.textContent).not.toContain('млрд $');
    expect(document.body.textContent).not.toContain('% ЭАН');
    expect(document.body.textContent).not.toContain('Численность населения');
    expect(document.body.textContent).not.toContain('2319,9');
  });
});

describe('WorldIndicatorPage US annual series', () => {
  it('keeps the chart without exposing annual landing links', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/world\/indicators\/united-states\/us-test$/, {
        country: { code: 'US', slug: 'united-states', name: 'США', name_en: 'United States' },
        primary_code: 'us-test',
        indicator: { code: 'us-test', name: 'Тестовый ряд', unit: '%', frequency: 'annual', source: 'FRED' },
        modes: [{ id: 'level-annual', label: 'По годам', group: 'Уровень', type: 'level', freq: 'annual', unit: '%' }],
        observed_years: [1901, 1950, 2025],
        forecast_available: false,
      }],
      [/^\/world\/indicators\/united-states\/us-test\/data/, {
        code: 'us-test', mode: 'level-annual', unit: '%', frequency: 'annual',
        points: [{ date: '2025-01-01', value: 4.1 }], count: 1,
      }],
    ]);
    renderPage(<WorldIndicatorPage />, {
      path: '/:countrySlug/indicator/:code',
      route: '/united-states/indicator/us-test',
    });

    await waitFor(() => expect(document.querySelector('[data-testid="chart-stub"]')).toBeTruthy());
    expect(document.querySelector('a[href^="/united-states/indicator/us-test/"]')).toBeNull();
  });
});
