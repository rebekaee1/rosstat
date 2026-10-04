import { describe, expect, it, afterEach, vi } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
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

describe('LiveTicker: единые знаки, источник и человеческая дата', () => {
  const today = new Date().toLocaleDateString('en-CA', { timeZone: 'Europe/Moscow' });
  function mockSnapshots() {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        snapshots: [
          { code: 'usd-rub-live', price: 84.4123, change_pct: -0.34, market_open: true, fetched_at: new Date().toISOString(), source: 'MOEX' },
          { code: 'eur-rub-live', price: 94.3201, change_pct: 0.2, market_open: false, fetched_at: new Date().toISOString(), as_of_date: today, source: 'CBR' },
          { code: 'brent', price: 78.5, change_pct: null, market_open: false, fetched_at: new Date().toISOString(), as_of_date: '2020-01-02', source: 'EIA' },
        ],
      }),
    });
    vi.stubGlobal('fetch', fetchMock);
  }

  it('курсы — два знака после запятой, минус настоящий, а не дефис', async () => {
    mockSnapshots();
    renderTicker({ locale: 'ru', route: '/' });
    expect(await screen.findByText('84,41')).toBeTruthy();
    expect(screen.getByText('94,32')).toBeTruthy();
    expect(document.body.textContent).toContain('\u22120,34%');
    expect(document.body.textContent).not.toMatch(/-\d,\d\d%/);
  });

  it('подписывает, откуда число: биржа или ЦБ; сегодняшнюю дату не пишет, чужую пишет словами', async () => {
    mockSnapshots();
    renderTicker({ locale: 'ru', route: '/' });
    await screen.findByText('84,41');
    expect(screen.getByText('shell.ticker.source.market')).toBeTruthy();
    expect(screen.getByText('shell.ticker.source.cb')).toBeTruthy();
    // Нет «04.10»-подобных технических дат.
    expect(document.body.textContent).not.toMatch(/\b\d{2}\.\d{2}\b/);
    // Устаревший ряд Brent получил дату словами (ключ i18n подставляет саму дату).
    expect(screen.getAllByText('shell.ticker.asOf')).toHaveLength(1);
  });

  it('при прокрутке вниз строка уходит, при прокрутке вверх возвращается', async () => {
    mockSnapshots();
    renderTicker({ locale: 'ru', route: '/' });
    await screen.findByText('84,41');
    const setY = (y) => { Object.defineProperty(window, 'scrollY', { value: y, configurable: true }); window.dispatchEvent(new Event('scroll')); };
    await act(async () => { setY(400); });
    await waitFor(() => expect(document.documentElement.dataset.feTicker).toBe('hidden'));
    await act(async () => { setY(300); });
    await waitFor(() => expect(document.documentElement.dataset.feTicker).toBe('shown'));
  });
});
