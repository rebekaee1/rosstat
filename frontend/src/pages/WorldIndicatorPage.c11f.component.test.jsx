// Круг 11, зона F: страница показателя страны. Значок свежести, «Этот показатель в других странах» под «О показателе», слот кнопок кабинета.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { waitFor, screen, within } from '@testing-library/react';
import WorldIndicatorPage from './WorldIndicatorPage';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/WorldChartSection', () => ({
  default: () => <section id="chart" data-testid="chart-stub" />,
}));

afterEach(() => vi.restoreAllMocks());

const peer = (code, slug, name, nameEn) => ({
  country_code: code, country_slug: slug, country_name: name, country_name_en: nameEn, indicator_code: `${slug}-gdp`, frequency: 'annual',
});

const META = {
  country: { code: 'TR', slug: 'turkey', name: 'Турция', name_en: 'Türkiye', region: 'Европа' },
  primary_code: 'tr-gdp',
  indicator: {
    code: 'tr-gdp', name: 'Валовой внутренний продукт в текущих ценах', unit: 'млрд $', frequency: 'annual',
    category: 'Национальные счета', source: 'МВФ', concept_slug: 'gdp-usd',
  },
  modes: [{ id: 'level-annual', label: 'По годам', group: 'Уровень', type: 'level', freq: 'annual', unit: 'млрд $' }],
  variants: [],
  forecast_available: false,
  peers: [
    peer('DE', 'germany', 'Германия', 'Germany'), peer('US', 'united-states', 'США', 'United States'),
    peer('TR', 'turkey', 'Турция', 'Türkiye'), peer('PL', 'poland', 'Польша', 'Poland'),
  ],
};

const DATA = (lastYear) => ({
  code: 'tr-gdp', mode: 'level-annual', unit: 'млрд $', frequency: 'annual',
  points: Array.from({ length: 8 }, (_, i) => ({ date: `${lastYear - 7 + i}-01-01`, value: 800 + i * 40 })),
  count: 8,
});

function renderCard({ lastYear = 2025, renderActions } = {}) {
  mockApiGet([
    ['/auth/me', { user: null }],
    [/^\/world\/indicators\/turkey\/tr-gdp$/, META],
    [/^\/world\/indicators\/turkey\/tr-gdp\/data/, DATA(lastYear)],
    [/^\/world\/compare/, { items: [{ country_code: 'TR', value: 1 }], concept: { value_mode: 'level' } }],
    [/^\/world\/countries\/turkey$/, { country: META.country, categories: [], overview: [] }],
  ]);
  return renderPage(<WorldIndicatorPage renderActions={renderActions} />, {
    path: '/:countrySlug/indicator/:code', route: '/turkey/indicator/tr-gdp',
  });
}

describe('WorldIndicatorPage: круг 11 (F)', () => {
  it('рядом с главным числом значок «Данные до …»; устаревший ряд называется устаревшим', async () => {
    const { unmount } = renderCard({ lastYear: 2025 });
    const badge = await waitFor(() => {
      const found = document.querySelector('.z4-hv [data-testid="data-freshness"]');
      expect(found).toBeTruthy();
      return found;
    });
    expect(badge.getAttribute('data-level')).toBe('fresh');
    expect(badge.textContent).toBe('Данные до 2025');
    unmount();
    renderCard({ lastYear: 2022 });
    const stale = await waitFor(() => {
      const found = document.querySelector('.z4-hv [data-testid="data-freshness"]');
      expect(found).toBeTruthy();
      return found;
    });
    expect(stale.getAttribute('data-level')).toBe('stale');
    expect(stale.textContent).toContain('Устарело');
    // Та же пометка стоит в строке под названием (телефон и планшет).
    expect(document.querySelector('.z4-hero__line [data-testid="data-freshness"]')).toBeTruthy();
  });

  it('под «О показателе» страны с тем же показателем: без текущей, крупные экономики первыми, ссылка ведёт на их страницу', async () => {
    renderCard();
    const block = await screen.findByTestId('indicator-peers');
    const links = within(block).getAllByRole('link').filter((a) => a.getAttribute('href')?.includes('/indicator/'));
    // G7 первыми, внутри по алфавиту русских названий: Германия, США, затем остальные.
    expect(links.map((a) => a.querySelector('.min-w-0').textContent)).toEqual(['Германия', 'США', 'Польша']);
    expect(links[0].getAttribute('href')).toBe('/germany/indicator/germany-gdp');
    const about = document.querySelector('.z4-about');
    expect(about.nextElementSibling).toBe(block);
    // Раскладка: «О показателе» и список стран в одной липкой колонке справа от таблицы.
    expect(about.closest('.z4-lower__side')).toBe(block.closest('.z4-lower__side'));
    expect(document.querySelector('.z4-lower[data-lower="wide"] .z4-lower__aside')).toBeTruthy();
  });

  it('слот кнопок кабинета: страница называет предмет, кнопки рисует зона кабинета', async () => {
    const seen = [];
    renderCard({ renderActions: (subject) => { seen.push(subject); return <button type="button">Следить</button>; } });
    expect(await screen.findByRole('button', { name: 'Следить' })).toBeTruthy();
    expect(seen[0]).toMatchObject({
      kind: 'world',
      itemKey: 'tr-gdp',
      watch: { subjectKind: 'world', subjectKey: 'tr-gdp', countrySlug: 'turkey' },
    });
    expect(document.querySelector('header.z4-hero [data-testid="cabinet-actions"].z4-hero__actions')).toBeTruthy();
  });

  it('без кнопок кабинета слот пуст', async () => {
    renderCard();
    await screen.findByTestId('indicator-peers');
    expect(document.querySelector('[data-testid="cabinet-actions"]')).toBeNull();
  });
});
