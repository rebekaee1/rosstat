// Раунд 2, зона Z4: страница показателя страны. Шапка с главным числом, полоса выбора с короткими названиями,
// сцена «график + плитки», нижний блок «таблица рядом с методологией».
import { describe, it, expect, afterEach, vi } from 'vitest';
import { waitFor, screen } from '@testing-library/react';
import WorldIndicatorPage from './WorldIndicatorPage';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/WorldChartSection', () => ({
  default: () => <section id="chart" data-testid="chart-stub" />,
}));

afterEach(() => vi.restoreAllMocks());

const META = {
  country: { code: 'US', slug: 'united-states', name: 'США', name_en: 'United States', region: 'Америка' },
  primary_code: 'us-gdp',
  indicator: {
    code: 'us-gdp',
    name: 'Валовой внутренний продукт в текущих ценах',
    unit: 'млрд $',
    frequency: 'annual',
    category: 'Национальные счета',
    source: 'МВФ',
    concept_slug: 'gdp-usd',
  },
  modes: [
    { id: 'level-annual', label: 'По годам', group: 'Уровень', type: 'level', freq: 'annual', unit: 'млрд $' },
    { id: 'yoy-annual', label: 'Год к году', group: 'Год к году', type: 'yoy', freq: 'annual', unit: '%' },
    { id: 'index-annual', label: 'Индекс', group: 'Индекс', type: 'index', freq: 'annual', unit: 'индекс' },
  ],
  variants: [
    { code: 'us-debt', label: 'Государственный долг сектора государственного управления', current: false },
    { code: 'us-pop', label: 'Численность населения', current: false },
    { code: 'us-gdp', label: 'Валовой внутренний продукт в текущих ценах', current: true },
    { code: 'us-un', label: '% от рабочей силы', current: false },
  ],
  forecast_available: false,
};

const DATA = {
  code: 'us-gdp',
  mode: 'level-annual',
  unit: 'млрд $',
  frequency: 'annual',
  points: Array.from({ length: 12 }, (_, i) => ({ date: `${2014 + i}-01-01`, value: 17000 + i * 1100 })),
  count: 12,
};

function renderCard() {
  mockApiGet([
    ['/auth/me', { user: null }],
    [/^\/world\/indicators\/united-states\/us-gdp$/, META],
    [/^\/world\/indicators\/united-states\/us-gdp\/data/, DATA],
    [/^\/world\/compare/, { items: [] }],
    [/^\/world\/countries\/united-states$/, { country: META.country, categories: [], overview: [] }],
  ]);
  return renderPage(<WorldIndicatorPage />, {
    path: '/:countrySlug/indicator/:code',
    route: '/united-states/indicator/us-gdp',
  });
}

describe('WorldIndicatorPage: шапка и полоса выбора', () => {
  it('справа в шапке главное число с единицей и изменением, слева название; строка под названием остаётся для телефона', async () => {
    const { container } = renderCard();
    await waitFor(() => expect(container.querySelector('header.z4-hero .z4-hv__value')).toBeTruthy());
    const hero = container.querySelector('header.z4-hero');
    expect(hero.getAttribute('data-has-value')).toBe('true');
    expect(hero.querySelector('.z4-hero__main h1').textContent).toBe('Валовой внутренний продукт в текущих ценах');
    const value = hero.querySelector('.z4-hero__aside .z4-hv__value').textContent.replace(/\u00A0/g, ' ');
    expect(value).toContain('трлн $');
    expect(hero.querySelector('.z4-hero__line [data-testid="indicator-hero"]')).toBeTruthy();
    expect(hero.querySelector('.z4-hv__delta')).toBeTruthy();
  });

  it('«Что показать»: короткие названия по важности, у «% от рабочей силы» есть объект, полное имя в title', async () => {
    renderCard();
    await waitFor(() => expect(screen.getAllByRole('link', { name: 'Госдолг' }).length).toBeGreaterThan(0));
    const group = document.querySelector('.fe-pick-card--variant');
    const names = [...group.querySelectorAll('a.fe-chip')].map((a) => a.textContent);
    expect(names).toEqual(['ВВП', 'Население', 'Безработица', 'Госдолг']);
    const debt = [...group.querySelectorAll('a.fe-chip')].find((a) => a.textContent === 'Госдолг');
    expect(debt.getAttribute('title')).toBe('Государственный долг сектора государственного управления');
  });

  it('режим «Рост от старта (= 100)» называется «Рост к началу периода»', async () => {
    renderCard();
    await waitFor(() => expect(document.querySelector('.fe-pick-card--mode')).toBeTruthy());
    const labels = [...document.querySelectorAll('.fe-pick-card--mode .fe-chip')].map((b) => b.textContent);
    expect(labels).toContain('Рост к началу периода');
    expect(labels.join(' ')).not.toContain('= 100');
  });

  it('свёрнутая строка телефона не повторяет заголовок страницы', async () => {
    renderCard();
    const toggle = await screen.findByRole('button', { name: /Изменить вид/ });
    expect(toggle.textContent).not.toContain('Валовой внутренний продукт');
    expect(toggle.textContent).toContain('Значения');
  });
});

describe('WorldIndicatorPage: сцена и нижний блок', () => {
  it('график и плитки лежат в одной сцене, плитки четыре как раньше', async () => {
    const { container } = renderCard();
    await waitFor(() => expect(container.querySelectorAll('.w2-stat').length).toBeGreaterThan(0));
    const stage = container.querySelector('.z4-stage');
    expect(stage.querySelector('#chart')).toBeTruthy();
    expect(stage.querySelector('.z4-tiles .fe-substat-grid')).toBeTruthy();
  });

  it('таблица истории стоит рядом с методологией и блоком «О показателе», а не одна на 62% ширины', async () => {
    const { container } = renderCard();
    await waitFor(() => expect(container.querySelector('.z4-lower')).toBeTruthy());
    const lower = container.querySelector('.z4-lower');
    expect(lower.querySelector('.z4-lower__table .fe-histtable')).toBeTruthy();
    expect(lower.querySelector('.z4-lower__method [data-block="methodology"]')).toBeTruthy();
    expect(lower.querySelector('.z4-lower__aside .z4-about')).toBeTruthy();
    expect(lower.getAttribute('data-lower')).toBe('wide');
  });

  it('контейнер страницы берёт ширину из токена Z1', async () => {
    const { container } = renderCard();
    await waitFor(() => expect(container.querySelector('.z4-page')).toBeTruthy());
  });
});
