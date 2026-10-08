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

function mount(country, slug) {
  mockApiGet([
    ['/auth/me', { user: null }],
    [`/world/countries/${slug}`, {
      country, categories: [], overview: [], coverage: {}, market_indicators: [],
    }],
    [`/world/${slug}/regions`, { regions: [{ slug: 'alabama', name: 'Алабама' }] }],
  ]);
  renderPage(<WorldCountry />, { path: '/:countrySlug', route: `/${slug}` });
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
