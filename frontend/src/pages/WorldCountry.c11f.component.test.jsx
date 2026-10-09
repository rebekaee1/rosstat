// Круг 11, зона F: страница страны. Численность словом, подсветка темы при прокрутке, слот кнопок кабинета.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { act, fireEvent, screen, within } from '@testing-library/react';
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

const IN = { code: 'IN', slug: 'india', name: 'Индия', name_en: 'India', region: 'Азия', indicators_count: 3 };

const POPULATION = {
  concept_slug: 'population', name: 'Численность населения', name_en: 'Population', unit: 'человек',
  indicator_code: 'in-pop', frequency: 'annual', date: '2025-01-01', value: 1476625577,
};

const indicator = (code, name) => ({
  code, name, unit: '%', frequency: 'monthly', frequencies: ['monthly'], last_value: 3.1, last_date: '2026-06-01', change: 0.1,
});

function payload(extra = {}) {
  return {
    country: IN,
    categories: [
      { name: 'Национальные счета', indicators: [indicator('in-a', 'Рост ВВП')] },
      { name: 'Цены', indicators: [indicator('in-b', 'Индекс цен')] },
      { name: 'Рынок труда', indicators: [indicator('in-c', 'Безработица')] },
    ],
    overview: [POPULATION],
    coverage: { history_start: '2000-01-01', history_end: '2026-04-01', frequencies: ['annual'] },
    market_indicators: [],
    ...extra,
  };
}

function mount(data, props = {}) {
  mockApiGet([
    ['/auth/me', { user: null }],
    ['/world/countries/india', data],
    [/\/world\/indicators\/india\/in-pop\/data/, { points: [{ date: '2024-01-01', value: 1450000000 }, { date: '2025-01-01', value: 1476625577 }] }],
  ]);
  return renderPage(<WorldCountry {...props} />, { path: '/:countrySlug', route: '/india' });
}

describe('Страница страны: круг 11 (F)', () => {
  it('«1 476 625 577 человек» крупной цифры читается как «1,48 млрд»', async () => {
    mount(payload());
    await screen.findByRole('heading', { name: 'Главное' });
    const card = document.querySelector('.w2-kpi');
    const text = card.textContent.replace(/\u00a0/g, ' ');
    expect(text).toContain('1,48');
    expect(text).toContain('млрд');
    expect(text).not.toContain('1 476 625 577');
  });

  it('боковое меню «Темы» подсвечивает ту тему, до которой дошла прокрутка (событие прокрутки ловится в фазе перехвата)', async () => {
    const frames = [];
    vi.spyOn(window, 'matchMedia').mockImplementation((media) => ({
      matches: media.includes('min-width'), media, addEventListener() {}, removeEventListener() {},
    }));
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => { frames.push(cb); return frames.length; });
    let reached = 'Цены';
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function rect() {
      const order = ['Национальные счета', 'Цены', 'Рынок труда'];
      const index = order.indexOf(this.dataset.worldCountryCategory);
      return { top: 90 + (index - order.indexOf(reached)) * 600, bottom: 0 };
    });
    mount(payload());
    await screen.findByRole('heading', { name: 'Цены' });
    act(() => { frames.splice(0).forEach((cb) => cb()); });
    const sidebar = document.querySelector('aside');
    expect(within(sidebar).getByRole('button', { name: /Цены/ }).getAttribute('aria-current')).toBe('true');
    // Прокрутили до «Рынка труда»: событие идёт из вложенного контейнера и до окна пузырём не доходит,
    // но слушатель в фазе перехвата его видит.
    reached = 'Рынок труда';
    const inner = document.createElement('div');
    document.body.appendChild(inner);
    fireEvent.scroll(inner);
    act(() => { frames.splice(0).forEach((cb) => cb()); });
    expect(within(sidebar).getByRole('button', { name: /Рынок труда/ }).getAttribute('aria-current')).toBe('true');
    inner.remove();
  });

  it('слот кнопок кабинета рядом с кнопками героя получает страну', async () => {
    const seen = [];
    mount(payload(), { renderActions: (subject) => { seen.push(subject); return <button type="button">В избранное</button>; } });
    expect(await screen.findByRole('button', { name: 'В избранное' })).toBeTruthy();
    expect(seen[0]).toMatchObject({ kind: 'country', itemKey: 'india', title: 'Индия' });
    expect(document.querySelector('.z5-hero__actions [data-testid="cabinet-actions"]')).toBeTruthy();
  });
});
