import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import WorldCountry from './WorldCountry';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/WorldMap', () => ({
  CountrySilhouette: ({ className, badge }) => (
    <div data-testid="silhouette-stub" data-class={className}>{badge}</div>
  ),
}));

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const DE = {
  code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', region: 'Европа', indicators_count: 3,
};

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

function quarterly(values) {
  const dates = ['2025-04-01', '2025-07-01', '2025-10-01', '2026-01-01', '2026-04-01'];
  return { points: dates.map((date, i) => ({ date, value: values[i] })) };
}

function payload(overrides = {}) {
  return {
    country: DE,
    categories: [],
    overview: [GDP],
    coverage: { history_start: '2000-01-01', history_end: '2026-04-01', frequencies: ['quarterly'] },
    market_indicators: [],
    ...overrides,
  };
}

function mount(data, extraRoutes = []) {
  const get = mockApiGet([
    ['/auth/me', { user: null }],
    ['/world/countries/germany', data],
    ...extraRoutes,
  ]);
  renderPage(<WorldCountry />, { path: '/:countrySlug', route: '/germany' });
  return get;
}

describe('Главное: крупные цифры', () => {
  it('сумма с масштабом читается как «849,7 млрд €», а жаргон про постоянные цены заменён словами', async () => {
    mount(payload());
    await screen.findByRole('heading', { name: 'Главное' });
    const card = document.querySelector('.w2-kpi');
    const text = card.textContent.replace(/\u00a0/g, ' ');
    expect(text).toContain('849,7');
    expect(text).toContain('млрд €');
    expect(text).not.toContain('849 680');
    expect(text).toContain('с поправкой на инфляцию');
    expect(text).not.toMatch(/постоянных ценах/);
    // Точная формулировка остаётся в подсказке.
    expect(card.querySelector('.w2-kpi-period').getAttribute('title')).toBe('в постоянных ценах 2015 года');
  });

  it('под цифрой появляется «год назад», когда пришёл ряд', async () => {
    mount(payload(), [
      [/\/world\/indicators\/germany\/de-gdp-q\/data/, quarterly([800000, 810000, 820000, 840000, 849680])],
    ]);
    await screen.findByRole('heading', { name: 'Главное' });
    await waitFor(() => {
      const ago = document.querySelector('.z5-key__ago');
      expect(ago.textContent.replace(/\u00a0/g, ' ')).toBe('▲год назад: 800,0 млрд €');
    });
  });

  it('до четырёх цифр в «Главном»', async () => {
    const item = (slug, code) => ({ ...GDP, concept_slug: slug, indicator_code: code, unit: '%' });
    mount(payload({
      overview: [
        item('hicp-index', 'a'), item('unemployment-rate', 'b'), item('budget-balance-gdp', 'c'),
        item('government-debt-gdp', 'd'), item('population', 'e'),
      ],
    }));
    await screen.findByRole('heading', { name: 'Главное' });
    expect(document.querySelectorAll('.w2-kpi')).toHaveLength(4);
  });
});

describe('Профиль страны и скелет', () => {
  it('профиль получает единый тёмный класс и флаг-бейдж с названием страны', async () => {
    mount(payload());
    const stub = await screen.findByTestId('silhouette-stub');
    expect(stub.getAttribute('data-class')).toBe('z5-profile');
    expect(stub.textContent).toContain('Германия');
  });

  it('пока данные грузятся, скелет повторяет форму страницы: профиль, три плитки «Главного», заголовок скрыт от читалок', () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      ['/world/countries/germany', () => new Promise(() => {})],
    ]);
    renderPage(<WorldCountry />, { path: '/:countrySlug', route: '/germany' });
    const skeleton = screen.getByTestId('country-skeleton');
    expect(skeleton.querySelector('.z5-profile-skel')).toBeTruthy();
    expect(skeleton.querySelectorAll('.z5-key--skel')).toHaveLength(3);
    expect(screen.queryByRole('heading', { name: 'Главное' })).toBeNull();
  });
});

function manyCategories() {
  const make = (name, n) => ({
    name,
    indicators: Array.from({ length: n }, (_, i) => ({
      code: `${name}-${i}`, name: `${name} показатель ${i}`, frequency: 'annual', last_value: i, last_date: '2025-01-01',
    })),
  });
  return [
    make('Национальные счета', 6), make('Цены', 6), make('Рынок труда', 6), make('Население', 6),
    make('Государственные финансы', 6), make('Внешняя торговля', 6), make('Бизнес и инвестиции', 6),
    make('Общество', 6),
  ];
}

describe('Темы страны', () => {
  it('сначала шесть тем, остальные в «Ещё темы»; золотая точка только у главных', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((media) => ({
      matches: media.includes('min-width'), media, addEventListener() {}, removeEventListener() {},
    }));
    mount(payload({ categories: manyCategories(), overview: [] }));
    await screen.findByRole('heading', { name: 'ВВП и рост' });
    const aside = document.querySelector('aside');
    const visible = [...aside.querySelectorAll('.z5-topics__list .z5-topic')];
    expect(visible).toHaveLength(6);
    expect(aside.querySelectorAll('.z5-topics__list .z5-dot')).toHaveLength(3);
    const more = aside.querySelector('details.z5-more');
    expect(within(more).getByText('Ещё темы')).toBeTruthy();
    expect(more.querySelectorAll('.z5-topic--chip')).toHaveLength(2);
    // Счётчик короткий, точное число и слово — в подсказке.
    const count = visible[0].querySelector('.z5-topic__count');
    expect(count.textContent).toBe('6');
    expect(count.getAttribute('title')).toBe('6 показателей');
  });

  it('когда выбрана тема из «Ещё темы», список раскрыт', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((media) => ({
      matches: media.includes('min-width'), media, addEventListener() {}, removeEventListener() {},
    }));
    mount(payload({ categories: manyCategories(), overview: [] }));
    await screen.findByRole('heading', { name: 'ВВП и рост' });
    const aside = document.querySelector('aside');
    const more = aside.querySelector('details.z5-more');
    expect(more.hasAttribute('open')).toBe(false);
    fireEvent.click(within(more).getByRole('button', { name: /Общество/ }));
    expect(aside.querySelector('details.z5-more').hasAttribute('open')).toBe(true);
  });

  it('«Прогноз ВВП» и «Похожие страны» стоят под темами вместо пустоты', async () => {
    mount(payload({ categories: manyCategories(), overview: [GDP] }), [
      ['/world/countries', { countries: [
        DE,
        { code: 'FR', slug: 'france', name: 'Франция', region: 'Европа', indicators_count: 50 },
        { code: 'JP', slug: 'japan', name: 'Япония', region: 'Азия', indicators_count: 90 },
      ] }],
    ]);
    await screen.findByRole('heading', { name: 'ВВП и рост' });
    const aside = document.querySelector('aside');
    const forecast = await within(aside).findByRole('link', { name: /Прогноз ВВП/ });
    // Каталог стран подгружается чуть позже основных данных.
    expect(forecast.getAttribute('href')).toBe('/germany/indicator/de-gdp-q');
    const similar = await within(aside).findByRole('link', { name: /Франция/ }, { timeout: 4000 });
    expect(similar.getAttribute('href')).toBe('/france');
    expect(within(aside).queryByRole('link', { name: /Япония/ })).toBeNull();
    expect(within(aside).queryByRole('link', { name: /Германия/ })).toBeNull();
  });
});

describe('Строки показателей', () => {
  const ROW = {
    code: 'de-hpi',
    name: 'Индекс цен на жильё (база 2025 = 100)',
    unit: 'индекс (2025 = 100)',
    frequency: 'quarterly',
    frequencies: ['quarterly'],
    last_value: 100.6,
    change: -0.7,
    last_date: '2026-04-01',
  };

  it('жаргон про базу индекса уходит под «i», единица стоит у числа, смысл изменения словами', async () => {
    mount(payload({ categories: [{ name: 'Цены', indicators: [ROW] }], overview: [] }));
    const row = await screen.findByRole('link', { name: /Индекс цен на жильё/ });
    expect(row.querySelector('.z5-row__title').textContent).toBe('Индекс цен на жильё');
    expect(row.querySelector('.z5-row__info').getAttribute('title')).toBe('2025 = 100');
    expect(row.querySelector('.z5-row__value small').textContent).toBe('индекс');
    const meaning = row.querySelector('.z5-row__meaning');
    expect(meaning.textContent.replace(/\u00a0/g, ' ')).toContain('на 0,7 пункта ниже, чем в прошлом квартале');
    expect(meaning.className).toContain('fe-tone--');
    expect(row.textContent).not.toContain('п. п.');
  });

  it('мини-график грузится только у увиденной строки, не у всех сразу', async () => {
    vi.stubGlobal('IntersectionObserver', class {
      constructor(callback) { this.callback = callback; }
      observe() { this.callback([{ isIntersecting: true }]); }
      unobserve() {}
      disconnect() {}
    });
    const get = mount(payload({ categories: [{ name: 'Цены', indicators: [ROW] }], overview: [] }), [
      [/\/world\/indicators\/germany\/de-hpi\/data/, quarterly([1, 2, 3, 4, 5])],
    ]);
    await screen.findByRole('link', { name: /Индекс цен на жильё/ });
    // Сразу после появления строки ряд не запрашивается: сначала строка должна «постоять» на экране.
    expect(get.mock.calls.some(([url]) => /de-hpi\/data/.test(url))).toBe(false);
    await waitFor(() => expect(get.mock.calls.some(([url]) => /de-hpi\/data/.test(url))).toBe(true), { timeout: 2000 });
  });

  it('без наблюдателя (старый браузер) ряды строк не запрашиваются совсем', async () => {
    const get = mount(payload({ categories: [{ name: 'Цены', indicators: [ROW] }], overview: [] }));
    await screen.findByRole('link', { name: /Индекс цен на жильё/ });
    expect(get.mock.calls.some(([url]) => /de-hpi\/data/.test(url))).toBe(false);
  });
});
