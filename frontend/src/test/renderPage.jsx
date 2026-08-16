// Т-13: обвязка для component-тестов страниц — QueryClient + Router + Auth.
// API мокается spy'ем на `api.get` (см. mockApiGet): named-хелперы lib/api
// зовут его внутри, поэтому одна точка перехвата покрывает все хуки.
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi } from 'vitest';
import api from '../lib/api';
import { AuthProvider } from '../context/AuthProvider';
import { LocaleProvider } from '../i18n';

export function mockApiGet(routes) {
  return vi.spyOn(api, 'get').mockImplementation((url) => {
    for (const [pattern, data] of routes) {
      const matched = typeof pattern === 'string' ? url === pattern : pattern.test(url);
      if (matched) {
        return Promise.resolve({ data: typeof data === 'function' ? data(url) : data });
      }
    }
    const err = new Error(`unmocked GET ${url}`);
    err.response = { status: 404 };
    return Promise.reject(err);
  });
}

export function renderPage(ui, { path = '/', route = '/' } = {}) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <LocaleProvider>
        <AuthProvider>
          <MemoryRouter initialEntries={[route]}>
            <Routes>
              <Route path={path} element={ui} />
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </LocaleProvider>
    </QueryClientProvider>,
  );
}
