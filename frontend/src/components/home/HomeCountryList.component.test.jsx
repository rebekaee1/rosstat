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
  it('показывает кнопки регионов сразу, пока первый ответ стран загружается', () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      ['/world/countries', () => new Promise(() => {})],
    ]);
    renderPage(<HomeCountryList />, { path: '/', route: '/' });

    expect(screen.getByRole('button', { name: /Европа/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Азия/ })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Европа/ }));
    expect(screen.getByRole('button', { name: /Европа/ }).getAttribute('aria-expanded')).toBe('true');
  });

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

  it('карточка страны: флаг вместо кода, без английского названия и без слова «ряд»', async () => {
    renderCatalog();

    fireEvent.click(await screen.findByRole('button', { name: /Европа/ }));
    const card = screen.getByRole('link', { name: /Германия/ });
    expect(card.textContent).toContain('\u{1F1E9}\u{1F1EA}');
    expect(card.textContent).not.toMatch(/Germany|\bDE\b/);
    expect(card.textContent).toContain('12 показателей');
    expect(card.textContent).not.toMatch(/ряд/);
    expect(screen.getByText(/2 страны в каталоге/)).toBeTruthy();
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
