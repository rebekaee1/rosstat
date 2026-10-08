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
    // Круг 9, S5: у изменения есть знак (настоящий минус U+2212, плюс), а не только цвет точки.
    expect(text).toContain('\u25BCw6b.ticker.down\u22120,3 %');
    expect(text).toContain('\u25B2w6b.ticker.up+0,2 %');
    expect(text).not.toMatch(/-\d,\d %/);
  });

  it('круг 10, Л1: лента в одну строку, «биржи» и «ЦБ» под ценой нет, источник лежит в подсказке; давняя дата стоит рядом с ценой', async () => {
    mockSnapshots();
    renderTicker({ locale: 'ru', route: '/' });
    await screen.findByText('84,41');
    // Второй строки с подписью источника нет ни у биржевой котировки, ни у курса ЦБ.
    expect(document.querySelector('.fe-ticker__caption')).toBeNull();
    expect(screen.queryByText('shell.ticker.source.market')).toBeNull();
    expect(screen.queryByText('shell.ticker.source.cb')).toBeNull();
    // Источник и значение «на дату» видны при наведении.
    const usd = screen.getByText('84,41').closest('a');
    expect(usd.getAttribute('title')).toContain('ticker.source');
    expect(usd.querySelector('.fe-ticker__asof')).toBeNull();
    // Нет «04.10»-подобных технических дат.
    expect(document.body.textContent).not.toMatch(/\b\d{2}\.\d{2}\b/);
    // Давний ряд Brent (старше трёх суток) приглушён (data-stale) и подписан короткой датой («на 29 сент.») в той же строке, что и цена.
    expect(screen.queryByText('c8s.ticker.stale')).toBeNull();
    const stale = document.querySelectorAll('[data-stale="true"]');
    expect(stale).toHaveLength(1);
    const asof = stale[0].querySelector('.fe-ticker__asof');
    expect(asof.textContent).toBe('shell.ticker.asOf');
    expect(asof.previousElementSibling.textContent).toContain('78,50');
    expect(stale[0].querySelector('.fe-ticker__name').textContent).toBe('c10t.ticker.brent');
    expect(stale[0].querySelector('.fe-ticker__name').hasAttribute('data-asof')).toBe(false);
  });

  it('круг 9, S5: давнее значение по полям сервера (stale, as_of_day) без процента и с серой датой', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        snapshots: [
          { code: 'brent', price: 78.5, change_pct: -0.9, market_open: false, fetched_at: new Date().toISOString(), as_of_date: today, as_of_day: '2026-09-29', age_days: 9, stale: true, source: 'EIA' },
          { code: 'eur-rub-live', price: 94.32, change_pct: 0.4, market_open: false, fetched_at: new Date().toISOString(), as_of_date: today, as_of_day: today, age_days: 0, stale: false, source: 'CBR' },
        ],
      }),
    }));
    renderTicker({ locale: 'ru', route: '/' });
    await screen.findByText('78,50');
    const stale = document.querySelectorAll('[data-stale="true"]');
    expect(stale).toHaveLength(1);
    expect(stale[0].querySelector('.fe-ticker__delta')).toBeNull();
    expect(stale[0].textContent).not.toMatch(/0,9/);
    expect(stale[0].querySelector('.fe-ticker__asof').textContent).toBe('shell.ticker.asOf');
    const fresh = screen.getByText('94,32').closest('a');
    expect(fresh.getAttribute('data-stale')).toBeNull();
    expect(fresh.querySelector('.fe-ticker__delta').textContent).toContain('+0,4');
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

  it('«Все валюты» вне прокручиваемой полосы курсов (волна 2, W-A2): ни один курс не уходит под него', async () => {
    mockSnapshots();
    renderTicker({ locale: 'ru', route: '/' });
    await screen.findByText('84,41');
    const all = screen.getByText('w6b.ticker.all').closest('a');
    expect(all.closest('.fe-ticker__scroll')).toBeNull();
    expect(all.closest('.fe-ticker__scroller--aside')).toBeTruthy();
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
    expect(text).toContain('\u25BCw6b.ticker.down\u22120.7%');
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

  it('круг 10, Л3: EN-лента называет валюты кодами EUR, GBP, CNY и Brent, а не дробью «USD/CNY»; пара расшифрована в подсказке', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        snapshots: [
          { code: 'eur-usd', price: 1.1225, change_pct: 0.3, market_open: false, fetched_at: new Date().toISOString(), as_of_date: today, source: 'ЕЦБ' },
          { code: 'gbp-usd', price: 1.3201, change_pct: -0.2, market_open: false, fetched_at: new Date().toISOString(), as_of_date: today, source: 'ЕЦБ' },
          { code: 'usd-cny', price: 6.7046, change_pct: 0, market_open: false, fetched_at: new Date().toISOString(), as_of_date: today, source: 'ЕЦБ' },
          { code: 'brent', price: 125.44, change_pct: 1.2, market_open: false, fetched_at: new Date().toISOString(), as_of_date: today, source: 'EIA' },
        ],
      }),
    }));
    renderTicker({ locale: 'en', route: '/' });
    expect(await screen.findByText('6.70')).toBeTruthy();
    const names = [...document.querySelectorAll('.fe-ticker__name')].map((n) => n.textContent);
    expect(names).toEqual(['c10t.ticker.eur', 'c10t.ticker.gbp', 'c10t.ticker.cny', 'c10t.ticker.brent']);
    expect(screen.queryByText('w7p.ticker.usdcny')).toBeNull();
    const text = document.body.textContent;
    expect(text).toContain('$1.12');
    expect(text).toContain('\u00A56.70');
    expect(text).not.toMatch(/USD\/CNY/);
    const cny = screen.getByText('6.70').closest('a');
    expect(cny.getAttribute('title')).toContain('c10t.ticker.rate');
    expect(screen.getByText('125.44').closest('a').getAttribute('title')).toContain('c10t.ticker.brentNote');
  });
});
