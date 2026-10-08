import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import HomeTools from './HomeTools';
import { mockApiGet } from '../../test/renderPage';
import { LocaleProvider } from '../../i18n';

afterEach(() => vi.restoreAllMocks());

const COUNTRIES = [
  { code: 'US', slug: 'united-states', name: 'США', name_en: 'United States' },
  { code: 'CN', slug: 'china', name: 'Китай', name_en: 'China' },
  { code: 'RU', slug: 'russia', name: 'Россия', name_en: 'Russia' },
];

function mount(locale) {
  mockApiGet([
    ['/auth/me', { user: null }],
    [/^\/indicators/, [
      { code: 'usd-rub', name: 'USD/RUB', unit: '₽', current_value: 80, current_date: '2026-10-03', is_active: true },
      { code: 'eur-rub', name: 'EUR/RUB', unit: '₽', current_value: 90, current_date: '2026-10-03', is_active: true },
      { code: 'gbp-rub', name: 'GBP/RUB', unit: '₽', current_value: 100, current_date: '2026-10-03', is_active: true },
      { code: 'cny-rub', name: 'CNY/RUB', unit: '₽', current_value: 11, current_date: '2026-10-03', is_active: true },
    ]],
    ['/world/countries', { countries: COUNTRIES, total: 3 }],
    [/^\/world\/compare\/snapshot\//, { items: [] }],
  ]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  const tree = (loc) => (
    <QueryClientProvider client={client}>
      <LocaleProvider locale={loc}>
        <MemoryRouter><HomeTools /></MemoryRouter>
      </LocaleProvider>
    </QueryClientProvider>
  );
  const view = render(tree(locale));
  return { ...view, tree };
}

describe('Эн1: английская версия «Try it yourself» без России в центре', () => {
  it('конвертер: рубля нет в списках валют, порядок USD, EUR, GBP, CNY', async () => {
    mount('en');
    const from = await screen.findByLabelText('From');
    await screen.findByText(/Converted at official rates/);
    const options = within(from).getAllByRole('option').map((node) => node.textContent);
    expect(options).toEqual(['USD', 'EUR', 'GBP', 'CNY']);
    expect(options).not.toContain('RUB');
  });

  it('сравнение: первая страна США, вторая Китай, России в выборе по умолчанию нет', async () => {
    mount('en');
    const first = await screen.findByLabelText('First country');
    expect(first.value).toBe('united-states');
    expect(screen.getByLabelText('Second country').value).toBe('china');
  });

  it('русский сайт остаётся прежним: рубль в конвертере, первой в сравнении стоит Россия', async () => {
    mount('ru');
    const from = await screen.findByLabelText('Из');
    expect(within(from).getAllByRole('option').map((node) => node.textContent)).toContain('RUB');
    expect((await screen.findByLabelText('Первая страна')).value).toBe('russia');
  });
});
