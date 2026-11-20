// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import api from './api';
import useGlobalSearch, { rowsStartingWith, unfinishedTail } from './useGlobalSearch';

const localeState = vi.hoisted(() => ({ value: 'ru' }));
vi.mock('../i18n', () => ({ useLocale: () => ({ locale: localeState.value }) }));
vi.mock('./api', () => ({ default: { get: vi.fn() } }));
let client;
function wrapper({ children }) { return <QueryClientProvider client={client}>{children}</QueryClientProvider>; }
beforeEach(() => {
  localeState.value = 'ru';
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  api.get.mockReset().mockResolvedValue({ data: { results: [], version: 'v2' } });
});
afterEach(() => { cleanup(); client.clear(); });

it('keeps empty and closed searches off the network', () => {
  const { rerender } = renderHook(({ q, enabled }) => useGlobalSearch(q, { enabled }), { wrapper, initialProps: { q: '', enabled: true } });
  expect(api.get).not.toHaveBeenCalled();
  rerender({ q: 'Germany', enabled: false });
  expect(api.get).not.toHaveBeenCalled();
});

it('debounces the complete query without replacing its country or concept', async () => {
  const { result, rerender } = renderHook(({ q }) => useGlobalSearch(q), { wrapper, initialProps: { q: '' } });
  rerender({ q: 'инфляция' });
  rerender({ q: 'инфляция Германии' });
  expect(result.current.isDebouncing).toBe(true);
  expect(api.get).not.toHaveBeenCalled();
  await waitFor(() => expect(api.get).toHaveBeenCalledOnce());
  expect(api.get).toHaveBeenCalledWith('/search', expect.objectContaining({ params: { q: 'инфляция Германии', limit: 100 } }));
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
});

it('isolates cached results by language and cancels an obsolete request', async () => {
  let firstSignal;
  api.get.mockImplementationOnce((_path, options) => {
    firstSignal = options.signal;
    return new Promise(() => {});
  });
  const { rerender } = renderHook(({ q }) => useGlobalSearch(q), { wrapper, initialProps: { q: 'cpi US' } });
  await waitFor(() => expect(firstSignal).toBeDefined());
  rerender({ q: 'GDP Germany' });
  await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
  expect(firstSignal.aborted).toBe(true);
  localeState.value = 'en';
  rerender({ q: 'GDP Germany' });
  await waitFor(() => expect(api.get).toHaveBeenCalledTimes(3));
});

it('does not reuse the previous client namespace when backend semantics change', async () => {
  client.setQueryData(['catalog-search', 'v2', 'ru', 'население Калифорнии', 100], { results: [{ name: 'Old interpretation' }], version: 'federated-v1' });
  api.get.mockResolvedValue({ data: { results: [{ name: 'Current interpretation' }], version: 'federated-v2' } });
  const { result } = renderHook(() => useGlobalSearch('население Калифорнии'), { wrapper });
  expect(result.current.data).toBeUndefined();
  await waitFor(() => expect(result.current.data?.version).toBe('federated-v2'));
  expect(result.current.data.results[0].name).toBe('Current interpretation');
  expect(api.get).toHaveBeenCalledOnce();
});

// ── Недописанное последнее слово (18.11.2026) ────────────────────────────────────────────────────
const EMPTY = { results: [], total: 0, has_more: false, version: 'federated-v2', reason: 'no_coverage' };
const byQuery = (answers) => (_path, options) => Promise.resolve({ data: answers[options.params.q] ?? EMPTY });

it('reads a one- or two-letter last word as unfinished only after a complete word', () => {
  expect(unfinishedTail('коэффициент ро')).toEqual({ stable: 'коэффициент', fragment: 'ро' });
  expect(unfinishedTail('Суммарный  коэффициент  Р')).toEqual({ stable: 'Суммарный коэффициент', fragment: 'р' });
  expect(unfinishedTail('уровень бё')).toEqual({ stable: 'уровень', fragment: 'бе' });
  expect(unfinishedTail('коэффициент рож')).toBeNull();   // три буквы сервер уже читает как начало слова
  expect(unfinishedTail('ро')).toBeNull();
  expect(unfinishedTail('m2 us')).toBeNull();              // дописанная часть короче трёх знаков
  expect(unfinishedTail('инфляция 20')).toBeNull();        // цифры — не начало слова
  expect(unfinishedTail('')).toBeNull();
});

it('keeps rows that have a word starting with the typed letters: by name first, then by region or country', () => {
  const rows = [
    { name: 'Коэффициент Джини', country_name: 'Россия' }, { name: 'Коэффициент рождаемости' }, { name: 'Коэффициент смертности' },
    { name: 'Gini', name_en: 'Road freight' }, { name: 'Средняя зарплата', region_name: 'Ростовская область' },
    { name: 'Потребительские цены' },   // «ро» внутри слова — не начало
    { name: 'Число родившихся', country_name: 'Россия' },
  ];
  expect(rowsStartingWith(rows, 'ро').map((row) => row.name)).toEqual(
    ['Коэффициент рождаемости', 'Число родившихся', 'Коэффициент Джини', 'Средняя зарплата']);
  expect(rowsStartingWith(rows, 'ro').map((row) => row.name)).toEqual(['Gini']);   // английское название
  expect(rowsStartingWith(undefined, 'ро')).toEqual([]);
});

it('shows rows for the typed words when the last word is unfinished instead of an empty answer', async () => {
  api.get.mockImplementation(byQuery({
    'коэффициент': { results: [{ key: 'a', name: 'Коэффициент рождаемости' }, { key: 'b', name: 'Коэффициент смертности' }],
      total: 2, has_more: true, version: 'federated-v2', intent: { terms: ['коэффициент'] } },
  }));
  const { result } = renderHook(() => useGlobalSearch('коэффициент ро'), { wrapper });
  await waitFor(() => expect(result.current.data?.results?.length).toBe(1));
  expect(result.current.data).toMatchObject({ results: [{ key: 'a' }], total: 1, has_more: false,
    unfinished: { stable: 'коэффициент', fragment: 'ро' } });
  expect(result.current.data.reason).toBeUndefined();
  expect(api.get.mock.calls.map(([, options]) => options.params.q)).toEqual(['коэффициент ро', 'коэффициент']);
});

it('stays honestly empty when no row has a word with that start', async () => {
  api.get.mockImplementation(byQuery({ 'коэффициент': { results: [{ key: 'b', name: 'Коэффициент смертности' }], version: 'federated-v2' } }));
  const { result } = renderHook(() => useGlobalSearch('коэффициент ро'), { wrapper });
  await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(result.current.isPending).toBe(false));
  expect(result.current.data).toEqual(EMPTY);
});

it('does not replace a real answer, a finished word or the server "nearest" block', async () => {
  api.get.mockImplementation(byQuery({
    'ввп ес': { results: [{ key: 'eu', name: 'ВВП ЕС' }], version: 'federated-v2' },
    'мрот ом': { ...EMPTY, nearest: { note: 'no_series', results: [{ key: 'n', name: 'Прожиточный минимум', path: '/x' }] } },
  }));
  const real = renderHook(() => useGlobalSearch('ввп ес'), { wrapper });
  await waitFor(() => expect(real.result.current.data?.results?.[0]?.key).toBe('eu'));
  const nearest = renderHook(() => useGlobalSearch('мрот ом'), { wrapper });
  await waitFor(() => expect(nearest.result.current.data?.nearest?.results?.length).toBe(1));
  const finished = renderHook(() => useGlobalSearch('коэффициент напряженности'), { wrapper });
  await waitFor(() => expect(finished.result.current.data).toEqual(EMPTY));
  expect(api.get.mock.calls.map(([, options]) => options.params.q).sort()).toEqual(['ввп ес', 'коэффициент напряженности', 'мрот ом']);
});

// Пульс 19.11.2026: вставленная ссылка поиска ЕМИСС давала ноль. Ищем то, что искали там, и пишем «Показаны результаты для».
it('searches the text of a pasted fedstat search link', async () => {
  api.get.mockResolvedValue({ data: { results: [{ key: 'births' }], version: 'v2' } });
  const link = 'https://www.fedstat.ru/indicators/search?searchText=%D0%9A%D0%BE%D1%8D%D1%84%D1%84%D0%B8%D1%86%D0%B8%D0%B5%D0%BD%D1%82+%D1%80%D0%BE%D0%B6%D0%B4%D0%B0%D0%B5%D0%BC%D0%BE%D1%81%D1%82%D0%B8';
  const { result } = renderHook(() => useGlobalSearch(link), { wrapper });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(api.get).toHaveBeenCalledWith('/search', expect.objectContaining({ params: { q: 'Коэффициент рождаемости', limit: 100 } }));
  expect(result.current.data.corrected_query).toBe('Коэффициент рождаемости');
});

it('передаёт раздел серверу только когда он есть (правка 17)', async () => {
  const { rerender } = renderHook(({ q, section }) => useGlobalSearch(q, { section }), { wrapper, initialProps: { q: 'Турция', section: 'tourism' } });
  await waitFor(() => expect(api.get).toHaveBeenCalledOnce());
  expect(api.get).toHaveBeenCalledWith('/search', expect.objectContaining({ params: { q: 'Турция', limit: 100, section: 'tourism' } }));
  api.get.mockClear();
  rerender({ q: 'Египет', section: null });
  await waitFor(() => expect(api.get).toHaveBeenCalledOnce());
  expect(api.get).toHaveBeenCalledWith('/search', expect.objectContaining({ params: { q: 'Египет', limit: 100 } }));
});
