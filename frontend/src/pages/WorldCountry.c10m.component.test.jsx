import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import WorldCountry from './WorldCountry';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../components/WorldMap', () => ({
  CountrySilhouette: ({ mapSlot, className }) => (
    <div data-testid="silhouette-stub" data-class={className}>{mapSlot}</div>
  ),
}));

afterEach(() => {
  vi.restoreAllMocks();
});

const US = {
  code: 'US', slug: 'united-states', name: 'США', name_en: 'United States', region: 'Америка', indicators_count: 3, has_regions: true,
};
const DE = {
  code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', region: 'Европа', indicators_count: 3, has_regions: false,
};

const GDP = {
  concept_slug: 'gdp-usd', name: 'ВВП', name_en: 'GDP', unit: 'млрд $', indicator_code: 'x-gdp', frequency: 'annual', date: '2025-01-01', value: 100,
};

function mount(country, slug, locale) {
  mockApiGet([
    ['/auth/me', { user: null }],
    [`/world/countries/${slug}`, {
      country, categories: [], overview: [GDP], coverage: {}, market_indicators: [],
    }],
    [`/world/${slug}/regions`, { regions: [{ slug: 'alabama', name: 'Алабама' }] }],
  ]);
  renderPage(<WorldCountry />, { path: '/:countrySlug', route: `/${slug}`, locale });
}

describe('К5: профиль страны США показывает карту штатов', () => {
  it('у США в профиле стоит карта штатов с нажимаемыми штатами', async () => {
    mount(US, 'united-states');
    const stub = await screen.findByTestId('silhouette-stub');
    await waitFor(() => expect(stub.querySelector('[data-block="country-states-map"]')).toBeTruthy());
    expect(stub.querySelectorAll('path[data-region-slug]').length).toBeGreaterThanOrEqual(50);
  });

  it('у других стран вместо карты штатов остаётся силуэт (слот пуст)', async () => {
    mount(DE, 'germany');
    const stub = await screen.findByTestId('silhouette-stub');
    expect(stub.querySelector('[data-block="country-states-map"]')).toBeNull();
    expect(stub.children).toHaveLength(0);
  });
});

describe('Эн1: пара для сравнения на странице страны', () => {
  it('на английском сайте предлагают сравнить с США, а не с Россией', async () => {
    mount(DE, 'germany', 'en');
    const link = await screen.findByRole('link', { name: /Compare with the United States/ });
    expect(decodeURIComponent(link.getAttribute('href'))).toBe('/compare?codes=w:germany:gdp-usd,w:united-states:gdp-usd');
    expect(screen.queryByRole('link', { name: /Compare with Russia/ })).toBeNull();
  });

  it('на странице самих США английской версии кнопки сравнения с США нет', async () => {
    mount(US, 'united-states', 'en');
    await screen.findByTestId('silhouette-stub');
    expect(screen.queryByRole('link', { name: /Compare with the United States/ })).toBeNull();
    expect(screen.queryByRole('link', { name: /Compare with Russia/ })).toBeNull();
  });

  it('на русском сайте остаётся «Сравнить с Россией»', async () => {
    mount(DE, 'germany', 'ru');
    const link = await screen.findByRole('link', { name: /Сравнить с Россией/ });
    expect(decodeURIComponent(link.getAttribute('href'))).toBe('/compare?codes=w:germany:gdp-usd,w:russia:gdp-usd');
  });
});
