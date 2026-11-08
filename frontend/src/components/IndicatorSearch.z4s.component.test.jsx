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

const regions = (n) => Array.from({ length: n }, (_v, i) => ({
  slug: `r${i}`, name: `Регион ${i}`, path: `/russia/region/r${i}/ceni-yaytsa`, navigation: 'spa', value: 100 + i, date: '2026-09-01',
}));
const GROUP = {
  key: 'region-group:ceni-yaytsa', kind: 'region_indicator', code: 'ceni-yaytsa', name: 'Средняя цена: яйца куриные', name_ru: 'Средняя цена: яйца куриные',
  name_en: 'Average price: eggs', country_slug: 'russia', country_name: 'Россия', region_slug: 'russia', region_name: 'Россия', frequency: 'monthly',
  unit: 'рублей за 10 штук', path: '/russia/region-rating/ceni-yaytsa', navigation: 'spa', score: 300,
  latest: { value: 104.3, date: '2026-09-01' }, regional_group: { count: 12, regions: regions(12) },
};
let client;
beforeEach(() => {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  api.get.mockReset().mockImplementation(() => Promise.resolve({ data: { results: [GROUP], version: 'federated-v2', intent: { countries: [], regions: [] } } }));
  HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.spyOn(HTMLElement.prototype, 'getClientRects').mockImplementation(() => [{ width: 100, height: 30 }]);
});
afterEach(() => { cleanup(); client.clear(); vi.restoreAllMocks(); });

it('региональный показатель — одна строка «Россия» со значением и раскрываемым списком регионов', async () => {
  render(<QueryClientProvider client={client}><MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter></QueryClientProvider>);
  fireEvent.click(screen.getAllByRole('button')[0]);
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'яйца' } });
  await waitFor(() => expect(screen.getAllByRole('option').length).toBe(1));
  expect(screen.getByText(/104,3/)).toBeTruthy();
  expect(screen.getByText('Регион 0')).toBeTruthy();
  expect(screen.queryByText('Регион 11')).toBeNull();
  fireEvent.click(screen.getByText('Ещё 8 регионов'));
  expect(screen.getByText('Регион 11')).toBeTruthy();
});
