// @vitest-environment jsdom
// Круг 10 (звонок 23, П1): поиск по-русски «ничего не находит». Реальный хук useGlobalSearch, ответ сервера подставлен.
import { beforeEach, afterEach, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import IndicatorSearch from './IndicatorSearch';
import api from '../lib/api';
import { translate } from '../i18n/messages';

vi.mock('../lib/api', () => ({ default: { get: vi.fn() } }));
vi.mock('../lib/worldApi', () => ({
  useWorldCountries: () => ({ data: { countries: [{ slug: 'russia', code: 'RU' }] } }),
  useWorldRatingConcepts: () => ({ data: { concepts: [] } }),
}));
vi.mock('../lib/track', () => ({ track: vi.fn(), events: {} }));
vi.mock('../i18n', () => ({
  useT: () => (key, vars) => translate(key, vars, 'ru'),
  useLocale: () => ({ locale: 'ru' }),
}));

const CPI = {
  key: 'ru:cpi-yoy', kind: 'russia', code: 'cpi-yoy', name: 'ИПЦ год к году', name_ru: 'ИПЦ год к году', name_en: 'CPI YoY',
  country_slug: 'russia', country_name: 'Россия', frequency: 'monthly', unit: '%', path: '/russia/indicator/cpi-yoy', navigation: 'spa', score: 327,
};
let client;
beforeEach(() => {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  api.get.mockReset().mockImplementation((_path, { params }) => Promise.resolve({
    data: params.q.trim().length < 2
      ? { results: [], reason: 'unsupported_query', version: 'federated-v2' }
      : { results: [CPI], version: 'federated-v2', intent: { countries: [], regions: [] } },
  }));
  HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.spyOn(HTMLElement.prototype, 'getClientRects').mockImplementation(() => [{ width: 100, height: 30 }]);
});
afterEach(() => { cleanup(); client.clear(); vi.restoreAllMocks(); });

function mount(variant = 'inline') {
  render(<QueryClientProvider client={client}><MemoryRouter><IndicatorSearch variant={variant} /></MemoryRouter></QueryClientProvider>);
}
const openByClick = () => fireEvent.click(screen.getAllByRole('button')[0]);

it('русский запрос из поля находит показатель', async () => {
  mount();
  openByClick();
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'инфляция' } });
  await waitFor(() => expect(screen.getAllByRole('option').length).toBeGreaterThan(0));
  expect(api.get).toHaveBeenCalledWith('/search', expect.objectContaining({ params: { q: 'инфляция', limit: 100 } }));
});

it('первая буква, набранная на кнопке-строке, не пропадает: запрос собирается целиком', async () => {
  mount();
  fireEvent.keyDown(screen.getAllByRole('button')[0], { key: 'и' });
  const input = screen.getByRole('combobox');
  expect(input.value).toBe('и');
  fireEvent.change(input, { target: { value: 'инфляция' } });
  await waitFor(() => expect(screen.getAllByRole('option').length).toBeGreaterThan(0));
});

it('потерянный compositionend не оставляет поиск ждать вечно', async () => {
  mount();
  openByClick();
  const input = screen.getByRole('combobox');
  fireEvent.compositionStart(input);
  fireEvent.change(input, { target: { value: 'инфляция' } });
  await waitFor(() => expect(screen.getAllByRole('option').length).toBeGreaterThan(0), { timeout: 3000 });
});

it('⌘K открывает поиск и при русской раскладке (key «л», code KeyK)', () => {
  mount('pill');
  fireEvent.keyDown(document, { key: 'л', code: 'KeyK', metaKey: true });
  expect(screen.getByRole('dialog')).toBeTruthy();
  fireEvent.keyDown(document, { key: 'л', code: 'KeyK', metaKey: true });
  expect(screen.queryByRole('dialog')).toBeNull();
});

it('Ctrl+K на другой раскладке с латинской буквой не путается с физической клавишей', () => {
  mount('pill');
  // Dvorak: физическая клавиша K выдаёт «t»; это не наш сочетание.
  fireEvent.keyDown(document, { key: 't', code: 'KeyK', ctrlKey: true });
  expect(screen.queryByRole('dialog')).toBeNull();
});

it('одна буква «и» (служебное слово) не показывает «Уточните запрос», а просит продолжить', async () => {
  mount();
  openByClick();
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'и' } });
  await waitFor(() => expect(api.get).toHaveBeenCalled());
  await waitFor(() => expect(screen.queryByTestId('search-spinner')).toBeNull());
  expect(screen.queryByText(translate('search.unsupportedQuery', {}, 'ru'))).toBeNull();
  expect(screen.getByText(translate('c10s.search.keepTyping', {}, 'ru'))).toBeTruthy();
});
