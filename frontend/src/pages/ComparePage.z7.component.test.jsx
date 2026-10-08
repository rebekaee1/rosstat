/** @vitest-environment jsdom */
// Раунд 2, Z7: разрыв словами, проценты сами при разных размерах, короткие названия, понятный лимит, единый заголовок.
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

const GDP = 'Валовой внутренний продукт в текущих ценах';
const CATALOG = {
  items: [
    item('united-states', 'США', 'gdp-usd', GDP),
    item('china', 'Китай', 'gdp-usd', GDP),
    item('germany', 'Германия', 'gdp-usd', GDP),
    item('germany', 'Германия', 'unemployment-rate', 'Уровень безработицы', 'monthly', '%'),
  ],
  total: 4,
};

function seriesFor(url) {
  const [, , , , slug, concept] = url.split('/');
  const found = CATALOG.items.find((it) => it.country_slug === slug && it.concept_slug === concept);
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

describe('ComparePage: раунд 2', () => {
  it('США и Китай близки по размеру: над графиком разрыв словами, процентов сама не включает', async () => {
    mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    const gap = await screen.findByTestId('compare-gap');
    expect(gap.textContent).toBe('США больше, чем Китай, в 1,6 раза');
    expect(screen.queryByTestId('compare-auto-index')).toBeNull();
  });

  it('очень разные размеры: сразу рост в процентах, пояснение и кнопка «Показать значения»', async () => {
    mockApis();
    const codes = encodeURIComponent('w:united-states:gdp-usd,w:germany:gdp-usd');
    renderPage(<ComparePage />, { path: '/compare', route: `/compare?codes=${codes}` });
    const note = await screen.findByTestId('compare-auto-index');
    expect(note.textContent).toMatch(/рост в процентах/);
    expect(screen.queryByTestId('compare-gap')).toBeNull();
    fireEvent.click(within(note).getByRole('button', { name: 'Показать значения' }));
    await waitFor(() => expect(screen.queryByTestId('compare-auto-index')).toBeNull());
    expect(screen.getByTestId('compare-gap').textContent).toMatch(/США больше, чем Германия/);
    // Выбор человека не отменяется сам: после «Показать значения» проценты не возвращаются.
    expect(screen.queryByTestId('compare-auto-index')).toBeNull();
  });

  it('заголовок вкладки совпадает с заголовком страницы', async () => {
    mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    const heading = await screen.findByRole('heading', { level: 1 });
    await waitFor(() => expect(document.title).toBe(heading.textContent));
  });

  it('выбранные ряды подписаны коротко, полное название в подсказке', async () => {
    mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    await screen.findByTestId('compare-gap');
    fireEvent.click(screen.getByRole('button', { name: 'Изменить' }));
    const shorts = await screen.findAllByText('ВВП, текущие цены, США');
    // Плашка выбранного ряда и карточка сводки: у обеих полное название в подсказке.
    expect(shorts.length).toBeGreaterThanOrEqual(2);
    shorts.forEach((node) => expect(node.getAttribute('title')).toBe(`${GDP} — США`));
  });

  it('гость в лимите: поле объясняет, что делать, а кнопка открывает регистрацию', async () => {
    mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    await screen.findByTestId('compare-gap');
    fireEvent.click(screen.getByRole('button', { name: 'Изменить' }));
    // Круг 9 (C2): лимит виден сразу, выбирать страну, чтобы упереться в него, не нужно.
    const notice = await screen.findByTestId('compare-cap-notice');
    expect(notice.textContent).toMatch(/Уберите один показатель или зарегистрируйтесь/);
    fireEvent.click(within(notice).getByRole('button', { name: /Зарегистрироваться/ }));
    expect(await screen.findByRole('dialog')).toBeTruthy();
  });

  it('ручки периода: две, начало и конец; сдвиг ручки задаёт свой период', async () => {
    const api = mockApis();
    const original = api.getMockImplementation();
    api.mockImplementation((url) => {
      if (/^\/world\/compare\/series\//.test(url)) {
        const base = seriesFor(url);
        return Promise.resolve({
          data: {
            ...base,
            data: Array.from({ length: 40 }, (_, i) => ({ date: `${1985 + i}-01-01`, value: 100 + i * 5 })),
          },
        });
      }
      return original(url);
    });
    const { container } = renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    await screen.findByTestId('compare-gap');
    const sliders = await waitFor(() => {
      const found = container.querySelectorAll('.fe-compare-brush [role="slider"]');
      expect(found).toHaveLength(2);
      return found;
    });
    const caption = container.querySelector('.fe-compare-card__caption');
    expect(caption.textContent).toMatch(/Период: 25 лет/);
    fireEvent.keyDown(sliders[0], { key: 'ArrowLeft' });
    await waitFor(() => expect(container.querySelector('.fe-compare-card__caption').textContent).not.toMatch(/Период: 25 лет/));
    expect(container.querySelector('.fe-compare-card__caption').textContent).toMatch(/Период: .*–/);
  });

  it('телефон: список показателей открывается слоем на весь экран, выбор ставит ряд и ведёт к графику', async () => {
    mockApis();
    const original = window.matchMedia;
    window.matchMedia = (query) => ({
      matches: /max-width/.test(query),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    });
    const scrollTo = vi.fn();
    window.scrollTo = scrollTo;
    try {
      renderPage(<ComparePage />, { path: '/compare', route: '/compare?codes=' });
      fireEvent.click(await screen.findByRole('button', { name: 'Германия' }));
      fireEvent.focus(screen.getByPlaceholderText('Найти показатель'));
      const sheet = await screen.findByRole('dialog', { name: 'Показатель страны' });
      expect(within(sheet).getByText('Популярное')).toBeTruthy();
      fireEvent.click(within(sheet).getByRole('button', { name: /Безработица/ }));
      expect(screen.queryByRole('dialog', { name: 'Показатель страны' })).toBeNull();
      expect(await screen.findByRole('heading', { level: 2, name: /Безработица: Германия/ })).toBeTruthy();
      await waitFor(() => expect(scrollTo).toHaveBeenCalled());
    } finally {
      window.matchMedia = original;
    }
  });
});
