import { describe, expect, it, afterEach, vi } from 'vitest';
import { fireEvent, screen, within } from '@testing-library/react';
import HomeCountryList from './HomeCountryList';
import { renderPage, mockApiGet } from '../../test/renderPage';

afterEach(() => vi.restoreAllMocks());

function renderCatalog() {
  mockApiGet([
    ['/auth/me', { user: null }],
    ['/world/countries', {
      countries: [
        {
          code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany',
          region: 'Европа', indicators_count: 12,
        },
        {
          code: 'JP', slug: 'japan', name: 'Япония', name_en: 'Japan',
          region: 'Азия', indicators_count: 9,
        },
      ],
      total: 2,
    }],
  ]);
  return renderPage(<HomeCountryList russiaSeriesCount={8} />, { path: '/', route: '/' });
}

describe('HomeCountryList — каталог стран', () => {
  it('по умолчанию все регионы свёрнуты', async () => {
    renderCatalog();

    const europe = await screen.findByRole('button', { name: /Европа/ });
    const asia = screen.getByRole('button', { name: /Азия/ });
    expect(europe.getAttribute('aria-expanded')).toBe('false');
    expect(asia.getAttribute('aria-expanded')).toBe('false');

    const catalog = screen.getByRole('heading', { name: 'Страны' }).closest('section');
    expect(within(catalog).queryByRole('link', { name: /Германия/ })).toBeNull();
    expect(within(catalog).queryByRole('link', { name: /Япония/ })).toBeNull();
  });

  it('раскрывает регион по клику', async () => {
    renderCatalog();

    const europe = await screen.findByRole('button', { name: /Европа/ });
    fireEvent.click(europe);
    expect(europe.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByRole('link', { name: /Германия/ })).toBeTruthy();
    expect(screen.queryByRole('link', { name: /Япония/ })).toBeNull();
  });
});
