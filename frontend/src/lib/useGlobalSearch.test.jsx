// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import api from './api';
import useGlobalSearch from './useGlobalSearch';

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
