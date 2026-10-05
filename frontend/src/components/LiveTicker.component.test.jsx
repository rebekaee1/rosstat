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

describe('LiveTicker запрашивает lane по языку и региону страницы', () => {
  it('ru на странице другой страны — тот же lane=russia: набор ленты не меняется от страницы к странице', async () => {
    const fetchMock = mockTickerFetch();
    renderTicker({ locale: 'ru', route: '/germany' });
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock.mock.calls[0][0]).toContain('lane=russia');
  });

  it('ru на странице России и в «Валютах» — lane=russia', async () => {
    const fetchMock = mockTickerFetch();
    renderTicker({ locale: 'ru', route: '/russia/indicator/cpi' });
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

describe('LiveTicker: понятные подписи, единые знаки и человеческая дата', () => {
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

  it('вместо кодов пар — названия («Доллар», «Евро»), курс со знаком валюты, изменение стрелкой и в процентах', async () => {
    mockSnapshots();
    renderTicker({ locale: 'ru', route: '/' });
    expect(await screen.findByText('84,41')).toBeTruthy();
    expect(screen.getByText('94,32')).toBeTruthy();
    expect(screen.getByText('w6b.ticker.usd')).toBeTruthy();
    expect(screen.getByText('w6b.ticker.eur')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/USD\/RUB|EUR\/RUB/);
    const text = document.body.textContent.replace(/\u00a0/g, ' ');
    expect(text).toContain('84,41 \u20BD');
    // Между стрелкой и числом — скрытая от глаз подпись для скринридера («снизился на»).
    expect(text).toContain('\u25BCw6b.ticker.down0,3 %');
    expect(text).toContain('\u25B2w6b.ticker.up0,2 %');
    expect(text).not.toMatch(/-\d,\d %/);
  });

  it('«биржа» и «ЦБ» стоят мелко под ценой, полное название источника остаётся в подсказке; чужую дату пишет словами', async () => {
    mockSnapshots();
    renderTicker({ locale: 'ru', route: '/' });
    await screen.findByText('84,41');
    // Доллар с биржи подписан «биржа», евро с сегодняшней датой — «ЦБ».
    const caption = screen.getByText('shell.ticker.source.market');
    expect(caption.className).toContain('fe-ticker__caption');
    expect(caption.previousElementSibling.textContent).toContain('84,41');
    expect(screen.getByText('shell.ticker.source.cb').className).toContain('fe-ticker__caption');
    const usd = screen.getByText('84,41').closest('a');
    expect(usd.getAttribute('title')).toContain('shell.ticker.source.market');
    // Нет «04.10»-подобных технических дат.
    expect(document.body.textContent).not.toMatch(/\b\d{2}\.\d{2}\b/);
    // Устаревший ряд Brent получил дату словами (ключ i18n подставляет саму дату) вместо подписи источника.
    expect(screen.getAllByText('shell.ticker.asOf')).toHaveLength(1);
  });

  it('EN: золото в рублях в ленте не показывается, остальные курсы на месте', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        snapshots: [
          { code: 'eur-usd', price: 1.12, change_pct: 0, market_open: false, fetched_at: new Date().toISOString(), as_of_date: today, source: 'ECB' },
          { code: 'gold-rub-live', price: 11143, change_pct: 0, market_open: false, fetched_at: new Date().toISOString(), as_of_date: today, source: 'Bank of Russia' },
        ],
      }),
    }));
    renderTicker({ locale: 'en', route: '/' });
    await screen.findByText('1.12');
    expect(screen.queryByText('w6b.ticker.gold')).toBeNull();
  });

  it('последний пункт ведёт в раздел «Валюты»', async () => {
    mockSnapshots();
    renderTicker({ locale: 'ru', route: '/' });
    await screen.findByText('84,41');
    const all = screen.getByText('w6b.ticker.all').closest('a');
    expect(all.getAttribute('href')).toBe('/currencies');
  });

  it('EN: цена со знаком доллара перед числом, минус не дефис, нулевое изменение не показывается', async () => {
    const twoDaysAgo = new Date(Date.now() - 2 * 86400000).toLocaleDateString('en-CA', { timeZone: 'UTC' });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        snapshots: [
          { code: 'eur-usd', price: 1.12, change_pct: -0.65, market_open: false, fetched_at: new Date().toISOString(), as_of_date: twoDaysAgo, source: 'ECB' },
          { code: 'usd-rub-live', price: 84.41, change_pct: 0, market_open: true, fetched_at: new Date().toISOString(), source: 'MOEX' },
        ],
      }),
    }));
    renderTicker({ locale: 'en', route: '/' });
    await screen.findByText('1.12');
    // Курс за вчера или выходные не подписывается датой.
    expect(screen.queryByText('shell.ticker.asOf')).toBeNull();
    const text = document.body.textContent;
    expect(text).toContain('$1.12');
    expect(text).toContain('\u25BCw6b.ticker.down0.7%');
    expect(text).not.toMatch(/\b0\.0%/);
  });

  it('лента курсов получает затухание по краям: два слоя-индикатора вместо маски на прокручиваемом блоке', async () => {
    mockSnapshots();
    renderTicker({ locale: 'ru', route: '/' });
    await screen.findByText('84,41');
    expect(document.querySelectorAll('.fe-ticker__fade')).toHaveLength(2);
    expect(document.querySelector('[role="group"]').className).not.toContain('fe-fade-x');
  });

  it('строка не прячется при прокрутке: высота зарезервирована всегда, шапка под ней не прыгает', async () => {
    mockSnapshots();
    renderTicker({ locale: 'ru', route: '/' });
    await screen.findByText('84,41');
    const setY = (y) => { Object.defineProperty(window, 'scrollY', { value: y, configurable: true }); window.dispatchEvent(new Event('scroll')); };
    await act(async () => { setY(400); });
    expect(document.documentElement.dataset.feTicker).toBeUndefined();
    expect(document.querySelector('.fe-ticker').className).toContain('h-9');
  });
  it('K3: изменение курса помечено точкой-свечением: рост и падение разного цвета, направление остаётся в тексте для скринридера', async () => {
    mockSnapshots();
    renderTicker({ locale: 'ru', route: '/' });
    await screen.findByText('84,41');
    const deltas = [...document.querySelectorAll('.fe-ticker__delta')];
    expect(deltas.map((d) => d.getAttribute('data-dir'))).toEqual(['down', 'up']);
    expect(deltas[0].textContent).toContain('w6b.ticker.down');
    expect(deltas[1].textContent).toContain('w6b.ticker.up');
  });

  it('K3: на телефоне при прокрутке вниз лента помечается скрытой, при прокрутке вверх возвращается', async () => {
    // Соседний тест оставил scrollY = 400: начинаем с верха страницы.
    Object.defineProperty(window, 'scrollY', { value: 0, configurable: true });
    mockSnapshots();
    renderTicker({ locale: 'ru', route: '/' });
    await screen.findByText('84,41');
    const ticker = document.querySelector('.fe-ticker');
    expect(ticker.getAttribute('data-hidden')).toBe('false');
    const setY = async (y) => {
      Object.defineProperty(window, 'scrollY', { value: y, configurable: true });
      await act(async () => {
        window.dispatchEvent(new Event('scroll'));
        await new Promise((resolve) => { setTimeout(resolve, 40); });
      });
    };
    await setY(400);
    expect(ticker.getAttribute('data-hidden')).toBe('true');
    // Высота зарезервирована всегда: прячет её только CSS-сдвиг, шапка и страница под ней не прыгают.
    expect(ticker.className).toContain('h-9');
    await setY(300);
    expect(ticker.getAttribute('data-hidden')).toBe('false');
    Object.defineProperty(window, 'scrollY', { value: 0, configurable: true });
  });

  it('EN: пара доллар к юаню подписана «USD/CNY» без знака юаня, чтобы не читалась как доллар к иене', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        snapshots: [
          { code: 'usd-cny', price: 6.7, change_pct: 0, market_open: false, fetched_at: new Date().toISOString(), as_of_date: today, source: 'ECB' },
        ],
      }),
    }));
    renderTicker({ locale: 'en', route: '/' });
    expect(await screen.findByText('6.70')).toBeTruthy();
    expect(screen.getByText('w7p.ticker.usdcny')).toBeTruthy();
    expect(document.body.textContent).not.toContain('\u00A5');
  });
});
