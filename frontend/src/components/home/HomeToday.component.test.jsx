import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import HomeToday from './HomeToday';
import { mockApiGet, renderPage } from '../../test/renderPage';

afterEach(() => vi.restoreAllMocks());

const item = (code, slug, value, extra = {}) => ({
  country_code: code, country_slug: slug, indicator_code: `${slug}-x`, date: '2025-12-31', value, ...extra,
});
const COUNTRIES = {
  countries: [
    { code: 'US', slug: 'united-states', name: 'США', name_en: 'United States' },
    { code: 'TR', slug: 'turkey', name: 'Турция', name_en: 'Turkey' },
    { code: 'JP', slug: 'japan', name: 'Япония', name_en: 'Japan' },
    { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany' },
  ],
  total: 4,
};

function mount(locale = 'ru', { prices } = {}) {
  mockApiGet([
    ['/auth/me', { user: null }],
    ['/world/countries', COUNTRIES],
    ['/world/compare/snapshot/gdp-usd', { items: [
      item('US', 'united-states', 30767, { unit: 'млрд $' }),
      item('DE', 'germany', 4900, { unit: 'млрд $' }),
      item('JP', 'japan', 4200, { unit: 'млрд $' }),
    ] }],
    ['/world/compare/snapshot/hicp-index', { items: prices || [
      item('TR', 'turkey', 34.9), item('US', 'united-states', 2.9), item('DE', 'germany', 2.2), item('JP', 'japan', 1.9),
    ] }],
    ['/world/compare/snapshot/unemployment-rate', { items: [
      item('JP', 'japan', 2.5), item('DE', 'germany', 3.1), item('US', 'united-states', 4.1),
    ] }],
  ]);
  return renderPage(<HomeToday />, { path: '/', route: '/', locale });
}

describe('HomeToday: «Мир сейчас»', () => {
  it('пока срезы грузятся, показывает каркас трёх плиток, а не пустое место', () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      ['/world/countries', () => new Promise(() => {})],
      [/^\/world\/compare\/snapshot\//, () => new Promise(() => {})],
    ]);
    renderPage(<HomeToday />, { path: '/', route: '/' });
    const block = screen.getByRole('region', { name: 'Мир сейчас' });
    expect(block.getAttribute('aria-busy')).toBe('true');
    expect(block.querySelectorAll('.fe-today__skeleton')).toHaveLength(3);
  });

  it('три плитки: число, страна с флагом, подпись без года (год общей строкой), место из N и шкала', async () => {
    mount();
    const block = await screen.findByRole('region', { name: 'Мир сейчас' });
    await waitFor(() => expect(block.querySelectorAll('.fe-today__tile')).toHaveLength(3));
    const prices = block.querySelector('[data-tile="prices"]');
    expect(prices.textContent).toContain('34,9');
    expect(prices.textContent).toContain('Турция');
    expect(prices.textContent).toContain('рост цен за год');
    expect(prices.textContent).not.toContain('2025');
    expect(prices.textContent).toContain('Место 1 из 4');
    expect(prices.textContent).toContain('\u{1F1F9}\u{1F1F7}');
    // Шкала места: трубка и один камень; Турция первая, камень в самом начале.
    const scale = prices.querySelector('.fe-today__scale');
    expect(scale).toBeTruthy();
    expect(prices.querySelectorAll('.fe-today__gem')).toHaveLength(1);
    expect(scale.className).toContain('is-first');
    expect(scale.style.getPropertyValue('--fe-rank-pos')).toBe('0');
    // Штрихов-столбиков (похожих на штрих-код) нет.
    expect(prices.querySelectorAll('svg rect')).toHaveLength(0);
    // Карточек про «домашнюю» страну нет: третьей была вторая про Россию (круг 8).
    expect(block.querySelector('[data-tile="home"], [data-tile="median"]')).toBeNull();
    expect(block.textContent).toContain('Данные за последний год, по которому они есть');
    const jobs = block.querySelector('[data-tile="jobs"]');
    expect(jobs.textContent).toContain('Япония');
    expect(jobs.textContent).toContain('2,5');
    // Весь блок читается как обычные ссылки и ведёт в рейтинг.
    expect(within(block).getByRole('link', { name: /Весь рейтинг стран/ }).getAttribute('href')).toBe('/world/rating/gdp-usd');
  });

  it('английский сайт: США на месте, подписи и числа по-английски, карточки «домашней» страны нет', async () => {
    mount('en');
    const block = await screen.findByRole('region', { name: 'The world right now' });
    await waitFor(() => expect(block.querySelectorAll('.fe-today__tile')).toHaveLength(3));
    const economy = block.querySelector('[data-tile="economy"]');
    expect(economy.textContent).toContain('$30.8');
    expect(economy.textContent).toContain('trillion');
    expect(economy.textContent).toContain('United States');
    expect(economy.textContent).toContain('Rank 1 of 3');
    expect(block.querySelector('[data-tile="home"]')).toBeNull();
    expect(block.textContent).toContain('Figures for the latest year with data');
  });

  it('данных мало или срезы недоступны: блока нет совсем, без пустых плиток', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      ['/world/countries', COUNTRIES],
      [/^\/world\/compare\/snapshot\//, { items: [] }],
    ]);
    renderPage(<HomeToday />, { path: '/', route: '/' });
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Мир сейчас' })).toBeNull());
  });

  it('нет запрещённого разделителя mid-dot и текста-заглушки', async () => {
    mount();
    const block = await screen.findByRole('region', { name: 'Мир сейчас' });
    await waitFor(() => expect(block.querySelectorAll('.fe-today__tile')).toHaveLength(3));
    expect(block.textContent).not.toContain(String.fromCharCode(0xb7));
    expect(block.textContent).not.toMatch(/lorem|заглушк|mock/i);
  });
});
