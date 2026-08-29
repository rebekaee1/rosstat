import { describe, expect, it, afterEach, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { LocaleContext } from '../i18n/localeContext';
import LiveTicker from './LiveTicker';

function renderTicker({ locale, route }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  const t = (key) => key;
  return render(
    <QueryClientProvider client={qc}>
      <LocaleContext.Provider value={{ locale, t, isPreview: false, setPreviewLocale: () => {} }}>
        <MemoryRouter initialEntries={[route]}>
          <LiveTicker />
        </MemoryRouter>
      </LocaleContext.Provider>
    </QueryClientProvider>,
  );
}

function mockTickerFetch() {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ snapshots: [] }),
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('LiveTicker запрашивает lane по locale, не по path', () => {
  it('ru на мировой странице — lane=russia', async () => {
    const fetchMock = mockTickerFetch();
    renderTicker({ locale: 'ru', route: '/germany' });
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock.mock.calls[0][0]).toContain('lane=russia');
  });

  it('ru на главной — lane=russia', async () => {
    const fetchMock = mockTickerFetch();
    renderTicker({ locale: 'ru', route: '/' });
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock.mock.calls[0][0]).toContain('lane=russia');
  });

  it('en на /russia — lane=world', async () => {
    const fetchMock = mockTickerFetch();
    renderTicker({ locale: 'en', route: '/russia' });
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock.mock.calls[0][0]).toContain('lane=world');
  });

  it('en на главной — lane=world', async () => {
    const fetchMock = mockTickerFetch();
    renderTicker({ locale: 'en', route: '/' });
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock.mock.calls[0][0]).toContain('lane=world');
  });
});
