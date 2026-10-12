// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

const state = { snap: null };
vi.mock('../lib/tickerLive', () => ({ useLiveQuote: (code) => (code ? state.snap : null) }));
vi.mock('../i18n', () => ({
  useLocale: () => ({ locale: 'ru' }),
  useT: () => (key, vars) => `${key}${vars ? `|${JSON.stringify(vars)}` : ''}`,
}));

import BrentLiveNote from './BrentLiveNote';

describe('BrentLiveNote (круг 13, R-BRENT)', () => {
  beforeEach(() => { state.snap = null; });

  it('без биржевого снимка (флаг выключен, в ленте спот EIA) ничего не рисует', () => {
    state.snap = { code: 'brent', price: 93.26, source: 'EIA', market_open: false, as_of_day: '2026-10-06' };
    const { container } = render(<BrentLiveNote code="brent" />);
    expect(container.firstChild).toBeNull();
  });

  it('другая страница не запрашивает и не рисует блок', () => {
    state.snap = { code: 'brent', price: 106.57, source: 'MOEX', market_open: true };
    const { container } = render(<BrentLiveNote code="gold-price" />);
    expect(container.firstChild).toBeNull();
  });

  it('биржевая котировка: контракт, задержка и пометка про недельный график', () => {
    state.snap = { code: 'brent', price: 106.57, source: 'MOEX', market_open: true, as_of: '2026-10-12T17:17:34+00:00', delay_minutes: 15, contract: 'BR-11.26', stale: false };
    render(<BrentLiveNote code="brent" />);
    const note = screen.getByTestId('brent-live-note');
    expect(note.textContent).toContain('c13b.brentLive.body');
    expect(note.textContent).toContain('"minutes":15');
    expect(note.textContent).toContain('"contract":"BR-11.26"');
    expect(note.textContent).toContain('"time":"20:17"');
    expect(note.textContent).toContain('c13b.brentLive.tail');
  });

  it('торги закрыты: итог сессии с датой', () => {
    state.snap = { code: 'brent', price: 106.57, source: 'MOEX', market_open: false, as_of_day: '2026-10-09', contract: 'BR-11.26', stale: false };
    render(<BrentLiveNote code="brent" />);
    expect(screen.getByTestId('brent-live-note').textContent).toContain('c13b.brentLive.bodyClosed');
  });

  it('давнее биржевое значение не показывается', () => {
    state.snap = { code: 'brent', price: 106.57, source: 'MOEX', market_open: false, as_of_day: '2026-09-01', stale: true };
    const { container } = render(<BrentLiveNote code="brent" />);
    expect(container.firstChild).toBeNull();
  });
});
