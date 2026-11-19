import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { renderPage, mockApiGet } from '../test/renderPage';
import SubscribeLine from './SubscribeLine';
import { resetSiteAcqForTests } from '../lib/siteAcq';
import * as track from '../lib/track';

const TODAY = new Date('2026-11-19T12:00:00Z');
const ON = { line: true, topics: ['inflation', 'gold', 'keyrate', 'deposit', 'mortgage', 'usd', 'eur'], bot: 'ForecastEconomyBot', first_screen: true };

function stubConfig(config) {
  const real = globalThis.fetch;
  vi.stubGlobal('fetch', vi.fn((url, ...rest) => {
    if (String(url).includes('/api/v1/site-acq/config')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(config) });
    }
    return real ? real(url, ...rest) : Promise.reject(new Error('no fetch'));
  }));
}

const text = (el) => el.textContent.replace(/\u00a0/g, ' ');

describe('SubscribeLine (совет 19.11.2026)', () => {
  let spy;
  beforeEach(() => {
    resetSiteAcqForTests();
    spy = vi.spyOn(track, 'track').mockImplementation(() => {});
    mockApiGet([[/\/calendar\/upcoming\?limit=1&indicator_code=cpi$/, { events: [{ id: 1, scheduled_date: '2026-11-25', is_estimated: false }], total: 1 }]]);
  });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('флаги выключены — ничего не рисует', async () => {
    stubConfig({ line: false, topics: [], bot: '', first_screen: false });
    const { container } = renderPage(<SubscribeLine code="cpi" frequency="monthly" lastDate="2026-09-01" today={TODAY} onDownloadExcel={() => {}} />);
    await new Promise((r) => setTimeout(r, 20));
    expect(container.querySelector('[data-testid="subscribe-line"]')).toBeNull();
  });

  it('ИПЦ: «Инфляция за октябрь выйдет 25 ноября», ссылка site_inflation, показ и нажатие уходят в события', async () => {
    stubConfig(ON);
    const onDl = vi.fn();
    renderPage(<SubscribeLine code="cpi" frequency="monthly" lastDate="2026-09-01" today={TODAY} onDownloadExcel={onDl} />, { route: '/russia/indicator/cpi/2026', path: '/russia/indicator/:code/:year' });
    const link = await screen.findByTestId('subscribe-line-telegram');
    expect(link.getAttribute('href')).toBe('https://t.me/ForecastEconomyBot?start=site_inflation');
    expect(link.getAttribute('target')).toBe('_blank');
    await waitFor(() => expect(text(screen.getByTestId('subscribe-line-when'))).toBe('Инфляция за октябрь выйдет 25 ноября.'));
    expect(spy).toHaveBeenCalledWith('subscribe_line_view', { topic: 'inflation', channel: 'telegram', path: '/russia/indicator/cpi/2026' });
    fireEvent.click(link);
    expect(spy).toHaveBeenCalledWith('subscribe_line_click', { topic: 'inflation', channel: 'telegram', path: '/russia/indicator/cpi/2026' });
    fireEvent.click(screen.getByTestId('subscribe-line-download'));
    expect(onDl).toHaveBeenCalledTimes(1);
  });

  it('топливо не в списке тем: без Telegram, но «по средам» и «Скачать» остаются', async () => {
    stubConfig(ON);
    renderPage(<SubscribeLine code="fuel-diesel" frequency="weekly" lastDate="2026-11-09" today={TODAY} onDownloadExcel={() => {}} />);
    await screen.findByTestId('subscribe-line-download');
    expect(screen.queryByTestId('subscribe-line-telegram')).toBeNull();
    expect(text(screen.getByTestId('subscribe-line-when'))).toBe('Новая цена выходит раз в неделю, по средам.');
    expect(spy).not.toHaveBeenCalledWith('subscribe_line_view', expect.anything());
  });

  it('источник задерживает — честная строка и никакого обещания присылать', async () => {
    stubConfig({ ...ON, topics: [...ON.topics, 'diesel'] });
    renderPage(<SubscribeLine code="fuel-diesel" frequency="weekly" lastDate="2026-10-26" today={TODAY} onDownloadExcel={() => {}} />);
    await screen.findByTestId('subscribe-line-when');
    expect(text(screen.getByTestId('subscribe-line-when'))).toContain('Источник задерживает');
    expect(screen.queryByTestId('subscribe-line-telegram')).toBeNull();
  });

  it('зарплата: только первый экран, строки «присылать» нет', async () => {
    stubConfig(ON);
    renderPage(<SubscribeLine code="wages-nominal" frequency="monthly" lastDate="2026-08-01" today={TODAY} onDownloadExcel={() => {}} />);
    await screen.findByTestId('subscribe-line-download');
    expect(screen.queryByTestId('subscribe-line-telegram')).toBeNull();
  });

  it('страница не из десяти — ничего', async () => {
    stubConfig(ON);
    const { container } = renderPage(<SubscribeLine code="ipi" frequency="monthly" lastDate="2026-09-01" today={TODAY} onDownloadExcel={() => {}} />);
    await new Promise((r) => setTimeout(r, 20));
    expect(container.querySelector('[data-testid="subscribe-line"]')).toBeNull();
  });

  it('английский: «October inflation is out on 25 November», «Send to Telegram»', async () => {
    stubConfig(ON);
    renderPage(<SubscribeLine code="cpi" frequency="monthly" lastDate="2026-09-01" today={TODAY} />, { locale: 'en' });
    const link = await screen.findByTestId('subscribe-line-telegram');
    expect(text(link)).toBe('Send to Telegram');
    await waitFor(() => expect(text(screen.getByTestId('subscribe-line-when'))).toBe('October inflation is out on 25 November.'));
  });
});
