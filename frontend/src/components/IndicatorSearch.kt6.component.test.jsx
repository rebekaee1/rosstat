// @vitest-environment jsdom
import { beforeEach, afterEach, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import IndicatorSearch from './IndicatorSearch';

const localeState = vi.hoisted(() => ({ value: 'ru' }));
const searchState = vi.hoisted(() => ({ data: { results: [], version: 'v2' }, isPending: false, isDebouncing: false, isError: false }));
vi.mock('../lib/useGlobalSearch', () => ({ default: vi.fn(() => searchState) }));
vi.mock('../lib/hooks', () => ({ useIndicators: () => ({ data: [] }) }));
vi.mock('../lib/worldApi', () => ({
  useWorldSearch: () => ({ data: null, isPending: false }),
  useWorldCompareCatalog: () => ({ data: { items: [] }, isPending: false }),
  useWorldCountries: () => ({ data: { countries: [] } }),
  useWorldRatingConcepts: () => ({ data: { concepts: [] } }),
  WORLD_GLOBAL_SEARCH_LIMIT: 50,
}));
vi.mock('../lib/track', () => ({ track: vi.fn(), events: {} }));
vi.mock('../i18n', () => ({ useT: () => (key) => key, useLocale: () => ({ locale: localeState.value }) }));

beforeEach(() => {
  localeState.value = 'ru';
  window.localStorage.clear();
  HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.spyOn(HTMLElement.prototype, 'getClientRects').mockImplementation(() => [{ width: 100, height: 30 }]);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function openAt(path) {
  render(<MemoryRouter initialEntries={[path]}><IndicatorSearch variant="inline" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'search.openAria' }));
}

it('из раздела «Туризм» поиск просит раздел у сервера, а «Популярное» туристское (правки 17, 50)', async () => {
  const { default: useGlobalSearch } = await import('../lib/useGlobalSearch');
  openAt('/russia/category/tourism');
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'Турция' } });
  expect(useGlobalSearch).toHaveBeenLastCalledWith('Турция', expect.objectContaining({ section: 'tourism' }));
  fireEvent.change(screen.getByRole('combobox'), { target: { value: '' } });
  expect(screen.getAllByText('kt6_search_example_1').length).toBeGreaterThan(0);
  expect(screen.queryByText('z4s.example.1')).toBeNull();
});

it('вне раздела прежнее «Популярное» и вызов без section', async () => {
  const { default: useGlobalSearch } = await import('../lib/useGlobalSearch');
  openAt('/russia/category/prices');
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'Турция' } });
  expect(useGlobalSearch).toHaveBeenLastCalledWith('Турция', { enabled: true });
  fireEvent.change(screen.getByRole('combobox'), { target: { value: '' } });
  expect(screen.getAllByText('z4s.example.1').length).toBeGreaterThan(0);
});

it('«Вы смотрели»: без дублей и без названий на другом языке (правка 50)', () => {
  localeState.value = 'en';
  window.localStorage.setItem('fe:recent-pages:v1', JSON.stringify([
    { path: '/russia/category/tourism', title: 'Tourism in Russia', kind: 'other', ts: 3 },
    { path: '/russia/category/tourism?x=1', title: 'Tourism in Russia', kind: 'other', ts: 2 },
    { path: '/russia/indicator/key-rate', title: 'Ключевая ставка России', kind: 'other', ts: 1 },
  ]));
  openAt('/');
  expect(screen.getAllByText('Tourism in Russia')).toHaveLength(1);
  expect(screen.queryByText('Ключевая ставка России')).toBeNull();
});
