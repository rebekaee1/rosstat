// Волна 6, G: сравнение открывается готовым живым графиком, добавление сразу по выбору, понятные настройки и заголовок.
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
  { code: 'cpi', name: 'Индекс потребительских цен', unit: '%', category: 'Цены', frequency: 'monthly', is_active: true, is_listed: true, current_value: 100.2 },
];

function item(slug, country, concept, conceptName, frequency = 'annual', unit = 'млрд $') {
  return {
    code: `w:${slug}:${concept}`,
    country_slug: slug,
    country_name: country,
    concept_slug: concept,
    concept_name: conceptName,
    frequency,
    unit,
  };
}

const CATALOG = {
  items: [
    item('united-states', 'США', 'gdp-usd', 'Валовой внутренний продукт в текущих ценах'),
    item('china', 'Китай', 'gdp-usd', 'Валовой внутренний продукт в текущих ценах'),
    item('germany', 'Германия', 'gdp-usd', 'Валовой внутренний продукт в текущих ценах'),
    item('germany', 'Германия', 'unemployment-rate', 'Уровень безработицы', 'monthly', '%'),
    item('france', 'Франция', 'unemployment-rate', 'Уровень безработицы', 'monthly', '%'),
    item('germany', 'Германия', 'government-debt-gdp', 'Государственный долг в процентах ВВП', 'annual', '% ВВП'),
  ],
  total: 6,
};

function seriesFor(url) {
  const [, , , , slug, concept] = url.split('/');
  const found = CATALOG.items.find((it) => it.country_slug === slug && it.concept_slug === concept);
  if (!found) throw new Error(`no series ${url}`);
  const base = slug === 'china' ? 18000 : slug === 'united-states' ? 29000 : 10;
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
      { date: '2022-01-01', value: base },
      { date: '2023-01-01', value: base * 1.02 },
      { date: '2024-01-01', value: base * 1.05 },
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

describe('ComparePage: открывается живым сравнением', () => {
  it('без выбора сразу строит «ВВП, текущие цены: США и Китай» и предлагает «Изменить»', async () => {
    mockApis();
    const { container } = renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    const title = await screen.findByRole('heading', { level: 2, name: /ВВП, текущие цены: США и Китай/ });
    expect(title).toBeTruthy();
    expect(screen.getByTestId('compare-demo').textContent).toMatch(/Пример/);
    expect(screen.getByRole('button', { name: 'Изменить' })).toBeTruthy();
    // Анкеты нет: ни «Сначала выберите страну», ни выбора страны.
    expect(document.body.textContent).not.toMatch(/Сначала выберите страну/);
    expect(screen.queryByRole('button', { name: 'Германия' })).toBeNull();
    // Линии подписаны странами, а не повтором названия показателя.
    const legend = container.querySelector('[data-block="compare-chart"]').textContent;
    expect(legend).toContain('США');
    expect(legend).toContain('Китай');
    expect(legend).not.toMatch(/Валовой внутренний продукт в текущих ценах — США/);
  });

  it('быстрые наборы под рукой; нажатие строит другой график сразу', async () => {
    mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    await screen.findByRole('heading', { level: 2, name: /США и Китай/ });
    const group = screen.getByRole('group', { name: 'Готовые сравнения' });
    const chips = within(group).getAllByRole('button').map((b) => b.textContent);
    expect(chips).toEqual([
      'ВВП: США и Китай',
      'Безработица: Германия и Франция',
      'Инфляция: Германия и Франция',
      'Население: Индия и Китай',
      'Россия и Турция: инфляция',
      'Россия и Турция: ВВП',
      'Россия и Турция: безработица',
    ]);
    expect(within(group).getByRole('button', { name: 'ВВП: США и Китай' }).getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(within(group).getByRole('button', { name: 'Безработица: Германия и Франция' }));
    expect(await screen.findByRole('heading', { level: 2, name: /Безработица: Германия и Франция/ })).toBeTruthy();
    expect(within(group).getByRole('button', { name: 'Безработица: Германия и Франция' }).getAttribute('aria-pressed')).toBe('true');
  });

  it('«Изменить» делает пример рабочим и раскрывает выбор: страна, показатель', async () => {
    mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    await screen.findByRole('heading', { level: 2, name: /США и Китай/ });
    fireEvent.click(screen.getByRole('button', { name: 'Изменить' }));
    expect(screen.queryByTestId('compare-demo')).toBeNull();
    // Пример стал обычным сравнением: ряды можно убрать. Гость сразу видит лимит и выход из него (круг 9, C2).
    expect(screen.getAllByRole('button', { name: 'Убрать' }).length).toBe(2);
    expect(await screen.findByTestId('compare-cap-notice')).toBeTruthy();
    fireEvent.click(screen.getByTestId('compare-cap-clear'));
    expect(await screen.findByText('Страна')).toBeTruthy();
    expect(screen.queryAllByRole('button', { name: 'Убрать' }).length).toBe(0);
  });

  it('подписи настроек человеческие и стоят после графика', async () => {
    mockApis();
    const { container } = renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    await screen.findByRole('heading', { level: 2, name: /США и Китай/ });
    const settings = await waitFor(() => {
      const node = container.querySelector('[data-block="compare-settings"]');
      expect(node).toBeTruthy();
      return node;
    });
    expect(within(settings).getByRole('button', { name: 'Как есть' })).toBeTruthy();
    expect(within(settings).getByRole('button', { name: 'Рост от начала (старт = 100)' })).toBeTruthy();
    expect(within(settings).getByText('Как в источнике')).toBeTruthy();
    expect(within(settings).getByRole('button', { name: /Сохранить как картинку/ })).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/Исходные значения|Общая база|Частота по источнику/);
    const chartCard = container.querySelector('[data-block="compare-chart"] .fe-panel');
    expect(chartCard.compareDocumentPosition(settings) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('ось «Период» под графиком убрана', async () => {
    mockApis();
    const { container } = renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    await screen.findByRole('heading', { level: 2, name: /США и Китай/ });
    expect(container.querySelector('.recharts-xAxis .recharts-label')).toBeNull();
  });
});

describe('ComparePage: добавление сразу по выбору', () => {
  it('выбор страны и показателя в списке ставит ряд на график без кнопки «Добавить»', async () => {
    mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=' });
    fireEvent.click(await screen.findByRole('button', { name: 'Германия' }));
    expect(screen.getByText('Выберите показатель: он сразу появится на графике')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Добавить' })).toBeNull();

    const input = screen.getByPlaceholderText('Найти показатель');
    fireEvent.focus(input);
    // «Популярное» сверху, названия короткие.
    const listbox = input.closest('.relative');
    expect(listbox.textContent).toContain('Популярное');
    expect(listbox.textContent).toContain('ВВП, текущие цены');
    expect(listbox.textContent).toContain('Безработица');
    fireEvent.mouseDown(within(listbox).getByText('Безработица'));

    expect(await screen.findByRole('heading', { level: 2, name: /Безработица: Германия/ })).toBeTruthy();
    expect(screen.getByTestId('compare-status').textContent).toMatch(/Добавлено на график: Безработица, Германия/);
    expect(screen.getByTestId('compare-status').textContent).toMatch(/Можно добавить ещё/);
  });

  it('когда все подходящие показатели страны уже на графике, подсказка не просит выбирать', async () => {
    mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=w:germany:unemployment-rate&compare=1' });
    // Страна Германия: безработица уже выбрана, остальное несовместимо с ней (другой показатель).
    await screen.findByRole('heading', { level: 2, name: /Безработица: Германия/ });
    fireEvent.click(screen.getByRole('button', { name: 'Добавить или изменить' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Германия' }));
    expect(screen.getByText(/Все подходящие показатели для «Германия» уже на графике/)).toBeTruthy();
    expect(screen.queryByText('Выберите показатель: он сразу появится на графике')).toBeNull();
  });

  it('вопрос про регионы возникает только после выбора России и называется «Регионы России»', async () => {
    mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=' });
    expect(screen.queryByRole('button', { name: /Регионы России/ })).toBeNull();
    fireEvent.click(await screen.findByRole('button', { name: 'Россия' }));
    expect(screen.getByRole('button', { name: /Регионы России/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Макропоказатели/ })).toBeTruthy();
  });

  it('пока каталог стран грузится, место под сетку занято скелетом, а не одной «Россией»', async () => {
    const api = (await import('../lib/api')).default;
    mockApis();
    const original = api.get.getMockImplementation();
    api.get.mockImplementation((url) => (url === '/world/compare/catalog' ? new Promise(() => {}) : original(url)));
    const { container } = renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=' });
    expect(await screen.findByRole('button', { name: 'Россия' })).toBeTruthy();
    const grid = container.querySelector('.fe-compare-countries');
    expect(grid.querySelectorAll('.skeleton').length).toBe(11);
  });
});
