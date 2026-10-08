import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import CountryStatesMap from './CountryStatesMap';
import { renderPage, mockApiGet } from '../../test/renderPage';
import { COUNTRY_STATES_MAP_SLUGS, hasCountryStatesMap } from '../../lib/countryStatesMap';

const navigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal()),
  useNavigate: () => navigate,
}));

afterEach(() => {
  vi.restoreAllMocks();
  navigate.mockReset();
});

const HUB = {
  country: { slug: 'united-states', name: 'США' },
  regions: [
    { slug: 'alabama', name: 'Алабама' },
    { slug: 'texas', name: 'Техас' },
  ],
};

function mount() {
  mockApiGet([['/world/united-states/regions', HUB]]);
  return renderPage(<CountryStatesMap slug="united-states" countryName="США" />, { path: '/', route: '/' });
}

describe('К5: карта штатов в профиле страны США', () => {
  it('рисует 51 штат как кнопки и подсказку «нажмите на штат»', async () => {
    const { container } = mount();
    expect(container.querySelector('[data-block="country-states-map"]')).toBeTruthy();
    expect(container.querySelectorAll('path[data-region-slug]').length).toBeGreaterThanOrEqual(50);
    expect(screen.getByText(/штат/i)).toBeTruthy();
  });

  it('клик по штату ведёт на страницу штата в стране', async () => {
    const { container } = mount();
    const alabama = container.querySelector('path[data-region-slug="alabama"]');
    fireEvent.click(alabama);
    expect(navigate).toHaveBeenCalledWith('/united-states/region/alabama');
  });

  it('названия штатов приходят из каталога штатов (подпись у кнопки)', async () => {
    const { container } = mount();
    await waitFor(() => {
      expect(container.querySelector('path[data-region-slug="alabama"]').getAttribute('aria-label')).toBe('Алабама');
    });
  });

  it('карта нужна только США: список стран с картой в профиле короткий и совпадает с геометрией', () => {
    expect(COUNTRY_STATES_MAP_SLUGS).toEqual(['united-states']);
    expect(hasCountryStatesMap('united-states')).toBe(true);
    expect(hasCountryStatesMap('germany')).toBe(false);
  });
});
