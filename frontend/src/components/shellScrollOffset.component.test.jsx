import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { LocaleContext } from '../i18n/localeContext';
import { mockApiGet, renderPage } from '../test/renderPage';
import Navbar from './Navbar';
import LiveTicker from './LiveTicker';

// Круг 6, зона S: шапка и лента сообщают свою высоту в --fe-header-h / --fe-ticker-h, а `html { scroll-padding-top }`
// (styles/k3-shell.css) складывает их с 12 px воздуха: якоря и scrollIntoView не оставляют заголовок под шапкой.
vi.mock('./IndicatorSearch', () => ({ default: () => <div data-testid="indicator-search-stub" /> }));

const root = document.documentElement;
const heights = { nav: 64, ticker: 28 };

function stubHeights() {
  vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockImplementation(function height() {
    if (this.tagName === 'NAV' && this.classList.contains('fe-navbar')) return heights.nav;
    if (this.classList.contains('fe-ticker')) return heights.ticker;
    return 0;
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  root.style.removeProperty('--fe-header-h');
  root.style.removeProperty('--fe-ticker-h');
});

describe('шапка и лента сообщают высоту для scroll-padding-top', () => {
  it('Navbar ставит --fe-header-h = высота + 6 px опускания и снимает при размонтировании', () => {
    stubHeights();
    mockApiGet([['/auth/me', { user: null }]]);
    const { unmount } = renderPage(<Navbar />, { path: '*', route: '/' });
    expect(root.style.getPropertyValue('--fe-header-h')).toBe('70px');
    unmount();
    expect(root.style.getPropertyValue('--fe-header-h')).toBe('');
  });

  it('LiveTicker ставит --fe-ticker-h по своей высоте и снимает при размонтировании', async () => {
    stubHeights();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ snapshots: [] }) }));
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
    const { unmount } = render(
      <QueryClientProvider client={qc}>
        <LocaleContext.Provider value={{ locale: 'ru', t: (key) => key, isPreview: false, setPreviewLocale: () => {} }}>
          <MemoryRouter initialEntries={['/']}>
            <LiveTicker />
          </MemoryRouter>
        </LocaleContext.Provider>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(root.style.getPropertyValue('--fe-ticker-h')).toBe('28px'));
    unmount();
    expect(root.style.getPropertyValue('--fe-ticker-h')).toBe('');
  });
});
