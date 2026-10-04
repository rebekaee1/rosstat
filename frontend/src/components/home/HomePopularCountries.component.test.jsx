import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import HomePopularCountries from './HomePopularCountries';
import { mockApiGet, renderPage } from '../../test/renderPage';

afterEach(() => vi.restoreAllMocks());

const COUNTRIES = [
  { code: 'RU', slug: 'russia', name: 'Россия', name_en: 'Russia' },
  { code: 'US', slug: 'united-states', name: 'США', name_en: 'United States' },
  { code: 'CN', slug: 'china', name: 'Китай', name_en: 'China' },
  { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany' },
  { code: 'XX', slug: 'atlantis', name: 'Атлантида', name_en: 'Atlantis' },
];

function render(countries, locale) {
  mockApiGet([['/auth/me', { user: null }], ['/world/countries', { countries, total: countries.length }]]);
  return renderPage(<HomePopularCountries />, { path: '/', route: '/', locale });
}

describe('HomePopularCountries', () => {
  it('рисует популярные страны с флагами, Россия первой для русской версии, плюс ссылка на весь каталог', async () => {
    render(COUNTRIES);
    await screen.findByRole('link', { name: /Россия/ });
    const links = screen.getAllByRole('link');
    expect(links[0].textContent).toContain('Россия');
    expect(links[0].getAttribute('href')).toBe('/russia');
    expect(links[0].textContent).toContain('\u{1F1F7}\u{1F1FA}');
    expect(links.map((a) => a.textContent).join('|')).not.toContain('Атлантида');
    expect(links.at(-1).getAttribute('href')).toBe('/#countries');
  });

  it('EN: США первыми, названия английские', async () => {
    render(COUNTRIES, 'en');
    await screen.findByRole('link', { name: /United States/ });
    const links = screen.getAllByRole('link');
    expect(links[0].textContent).toContain('United States');
    expect(links[0].getAttribute('href')).toBe('/united-states');
  });

  it('если в каталоге почти нет популярных стран, ряд не выводится вовсе', async () => {
    const { container } = render([COUNTRIES[4]]);
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(container.querySelector('[data-block="home-popular-countries"]')).toBeNull();
  });
});
