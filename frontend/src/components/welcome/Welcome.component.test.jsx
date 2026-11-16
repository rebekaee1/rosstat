import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LocaleContext } from '../../i18n/localeContext';
import { translate } from '../../i18n/messages';
import WelcomeGate, { WelcomeEntry } from './WelcomeGate';
import WelcomeScreen from './WelcomeScreen';
import * as pwa from '../../lib/pwa';
import { track } from '../../lib/track';
import { fetchWorldCompareSeries } from '../../lib/worldApi';
import { WELCOME_KEY, WELCOME_OPEN_DELAY_MS, readWelcomeSeen } from '../../lib/welcome';

vi.mock('../../lib/track', () => ({
  track: vi.fn(),
  events: {
    WELCOME_VIEW: 'welcome_view', WELCOME_STEP: 'welcome_step', WELCOME_SKIP: 'welcome_skip',
    WELCOME_DONE: 'welcome_done', WELCOME_CTA: 'welcome_cta',
  },
}));
const auth = { isAuthed: false, isLoading: false };
vi.mock('../../context/authContext', () => ({ useAuth: () => auth }));
const cabinet = { enabled: true, ready: true, features: {}, limits: {} };
vi.mock('../../lib/useCabinet', () => ({ useCabinetConfig: () => cabinet }));
const automation = { on: false };
vi.mock('../../lib/behavior', () => ({ isAutomationClient: () => automation.on }));
vi.mock('../../lib/worldApi', () => ({ fetchWorldCompareSeries: vi.fn() }));

const ru = (key, vars) => translate(key, vars, 'ru');
const en = (key, vars) => translate(key, vars, 'en');
const { _store, emit } = pwa.__testing;

/** Месячный ряд: 130 точек с января 2016, последняя — октябрь 2026. */
const series = (lastValue, source) => ({
  meta: source ? { source } : {},
  data: Array.from({ length: 130 }, (_, i) => ({
    date: new Date(Date.UTC(2016, i, 1)).toISOString().slice(0, 10),
    value: i === 129 ? lastValue : 5 - i / 60,
  })),
});
const SERIES = {
  russia: series(2.2, 'Росстат'),
  'united-kingdom': series(4.6),
  germany: series(3.9),
  'united-states': series(4.1),
};

function Where() {
  const { pathname, search } = useLocation();
  return <output data-testid="where">{pathname}{search}</output>;
}

function wrap(ui, { path = '/', t = ru, locale = 'ru' } = {}) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LocaleContext.Provider value={{ locale, t, isPreview: false, setPreviewLocale() {} }}>
        <div id="root">{ui}</div>
        <Where />
      </LocaleContext.Provider>
    </MemoryRouter>,
  );
}

const setFlag = (welcome_enabled, visits = 1) => {
  _store.config = { sw_enabled: true, install_prompt_enabled: false, welcome_enabled };
  _store.state = { ..._store.state, visits };
  _store.standalone = false;
  act(() => emit());
};
const advance = async (ms) => { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); };
const settle = () => advance(0);
const screenEl = () => screen.queryByTestId('welcome-screen');
const phrase = () => screen.getByRole('heading', { level: 2 }).textContent;
const next = () => fireEvent.click(screen.getByTestId('welcome-next'));

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date', 'setTimeout', 'clearTimeout'] });
  pwa.resetPwaForTests();
  track.mockClear();
  fetchWorldCompareSeries.mockReset();
  fetchWorldCompareSeries.mockImplementation(async (slug) => {
    if (!SERIES[slug]) throw new Error('404');
    return SERIES[slug];
  });
  auth.isAuthed = false;
  auth.isLoading = false;
  cabinet.enabled = true;
  automation.on = false;
  window.scrollY = 0;
});
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe('WelcomeScreen', () => {
  it('первый экран — ответ с настоящим числом из ряда сайта, месяцем и источником', async () => {
    wrap(<WelcomeScreen onClose={() => {}} />);
    await settle();
    expect(fetchWorldCompareSeries).toHaveBeenCalledTimes(1);
    expect(fetchWorldCompareSeries.mock.calls[0].slice(0, 2)).toEqual(['russia', 'unemployment-rate']);
    const dialog = screenEl();
    expect(dialog.getAttribute('role')).toBe('dialog');
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(dialog.getAttribute('data-wl-data')).toBe('ready');
    expect(phrase()).toBe(ru('welcome.find.phrase', { value: '2,2 %' }));
    expect(screen.getByText(ru('welcome.find.caption', { month: 'октябрь 2026', source: 'Росстат' }))).toBeTruthy();
    expect(document.querySelector('.fe-wl3-chart__line')).not.toBeNull();
    expect(track.mock.calls.filter(([name]) => name === 'welcome_view')).toEqual([['welcome_view', { trigger: 'auto', audience: 'ru' }]]);
  });

  it('четыре шага по порядку; на шаге про свежесть — месяц последнего значения; последний шаг предлагает аккаунт', async () => {
    wrap(<WelcomeScreen onClose={() => {}} />);
    await settle();
    next();
    expect(phrase()).toBe(ru('welcome.fresh.phrase', { month: 'октябрь 2026' }));
    expect(document.querySelector('.fe-wl3-chart').getAttribute('data-mode')).toBe('fresh');
    next();
    expect(phrase()).toBe(ru('welcome.telegram.phrase'));
    next();
    expect(phrase()).toBe(ru('welcome.account.phrase'));
    expect(screen.queryByTestId('welcome-next')).toBeNull();
    expect(screen.getByTestId('welcome-register').getAttribute('href')).toBe('/register?next=%2F');
    expect(track.mock.calls.filter(([name]) => name === 'welcome_step').map(([, p]) => p.step)).toEqual(['fresh', 'telegram', 'account']);
  });

  it('число идёт за рукой: под указателем — значение и месяц этой точки, фраза при этом не меняется', async () => {
    wrap(<WelcomeScreen onClose={() => {}} />);
    await settle();
    const chart = document.querySelector('.fe-wl3-chart');
    chart.getBoundingClientRect = () => ({ left: 0, top: 0, width: 1000, height: 300, right: 1000, bottom: 300 });
    const before = phrase();
    fireEvent.pointerMove(chart, { clientX: 0, clientY: 100 });
    expect(screen.getByTestId('welcome-read').textContent).toContain('октябрь 2016'); // десять лет назад от октября 2026
    fireEvent.pointerMove(chart, { clientX: 1000, clientY: 100 });
    expect(screen.getByTestId('welcome-read').textContent).toBe('2,2 %октябрь 2026');
    expect(phrase()).toBe(before);
    fireEvent.pointerLeave(chart);
    expect(screen.queryByTestId('welcome-read')).toBeNull();
  });

  it('поле «Спросите своё» ведёт в поиск сайта с этим вопросом и запоминает исход', async () => {
    const navigateTo = vi.fn();
    wrap(<WelcomeScreen onClose={() => {}} navigateTo={navigateTo} />);
    await settle();
    const field = screen.getByTestId('welcome-field');
    fireEvent.change(field, { target: { value: 'к' } });
    fireEvent.submit(field.closest('form'));
    expect(navigateTo).not.toHaveBeenCalled(); // одной буквы мало
    fireEvent.change(field, { target: { value: 'курс доллара' } });
    fireEvent.submit(field.closest('form'));
    expect(navigateTo).toHaveBeenCalledWith('/?q=%D0%BA%D1%83%D1%80%D1%81+%D0%B4%D0%BE%D0%BB%D0%BB%D0%B0%D1%80%D0%B0');
    expect(track).toHaveBeenCalledWith('welcome_cta', { target: 'search' });
    expect(readWelcomeSeen().outcome).toBe('search');
  });

  it('сервер не ответил — экран остаётся честным: общие фразы без чисел и без линии', async () => {
    fetchWorldCompareSeries.mockRejectedValue(new Error('down'));
    wrap(<WelcomeScreen onClose={() => {}} />);
    await settle();
    expect(screenEl().getAttribute('data-wl-data')).toBe('empty');
    expect(phrase()).toBe(ru('welcome.find.phraseEmpty'));
    expect(document.querySelector('.fe-wl3-chart__line')).toBeNull();
    for (const sel of ['.fe-wl3__phrase', '.fe-wl3__body']) expect(document.querySelector(sel).textContent).not.toMatch(/\d/);
    expect(document.querySelector('.fe-wl3__question')).toBeNull();
    next();
    expect(phrase()).toBe(ru('welcome.fresh.phraseEmpty'));
  });

  it('«Пропустить» есть на каждом шаге, закрывает экран и запоминает исход', async () => {
    const onClose = vi.fn();
    wrap(<WelcomeScreen onClose={onClose} />);
    await settle();
    for (let i = 0; i < 3; i += 1) {
      expect(screen.getByRole('button', { name: ru('welcome.skipAria') })).toBeTruthy();
      next();
    }
    fireEvent.click(screen.getByRole('button', { name: ru('welcome.skipAria') }));
    await advance(400);
    expect(onClose).toHaveBeenCalledWith('skip');
    expect(readWelcomeSeen().outcome).toBe('skip');
    expect(track).toHaveBeenCalledWith('welcome_skip', { step: 'account', via: 'button' });
  });

  it('клавиатура: Esc пропускает, стрелки листают, но в поле вопроса стрелки остаются тексту', async () => {
    const onClose = vi.fn();
    wrap(<WelcomeScreen onClose={onClose} />);
    await settle();
    screen.getByTestId('welcome-field').focus();
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    expect(phrase()).toBe(ru('welcome.find.phrase', { value: '2,2 %' }));
    screen.getByTestId('welcome-next').focus();
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    expect(phrase()).toBe(ru('welcome.fresh.phrase', { month: 'октябрь 2026' }));
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    expect(phrase()).toBe(ru('welcome.find.phrase', { value: '2,2 %' }));
    fireEvent.keyDown(document, { key: 'Escape' });
    await advance(400);
    expect(onClose).toHaveBeenCalledWith('skip');
  });

  it('пока экран открыт, страница под ним неактивна и не прокручивается; после закрытия всё возвращается', async () => {
    const view = wrap(<WelcomeScreen onClose={() => {}} />);
    await settle();
    const app = document.getElementById('root');
    expect(app.hasAttribute('inert')).toBe(true);
    expect(document.documentElement.style.overflow).toBe('hidden');
    expect(app.contains(screenEl())).toBe(false); // портал в body
    view.unmount();
    expect(document.documentElement.style.overflow).toBe('');
  });

  it('шаг Telegram ведёт на бота и канал в новой вкладке и не закрывает экран', async () => {
    const onClose = vi.fn();
    wrap(<WelcomeScreen initialStep={2} onClose={onClose} />);
    await settle();
    const bot = screen.getByRole('link', { name: new RegExp(ru('welcome.telegram.bot')) });
    const channel = screen.getByRole('link', { name: new RegExp(ru('welcome.telegram.channel')) });
    expect(bot.getAttribute('href')).toBe('https://t.me/ForecastEconomyBot?start=site_welcome');
    expect(channel.getAttribute('href')).toBe('https://t.me/forecasteconomy');
    for (const link of [bot, channel]) {
      expect(link.getAttribute('target')).toBe('_blank');
      expect(link.getAttribute('rel')).toBe('noopener noreferrer');
    }
    bot.addEventListener('click', (e) => e.preventDefault());
    fireEvent.click(bot);
    expect(track).toHaveBeenCalledWith('welcome_cta', { target: 'bot' });
    expect(onClose).not.toHaveBeenCalled();
  });

  it('без кабинета на сервере не обещает «сохранять» и «следить»', async () => {
    cabinet.enabled = false;
    wrap(<WelcomeScreen initialStep={3} onClose={() => {}} />);
    await settle();
    const points = [...document.querySelectorAll('.fe-wl3__copy:not([data-out]) .fe-wl3__points li')].map((li) => li.textContent);
    expect(points).toEqual([ru('welcome.account.download')]);
  });

  it('«меньше движения»: экран помечен data-wl-motion="off" и закрывается сразу', async () => {
    const original = window.matchMedia;
    window.matchMedia = (q) => ({ matches: /reduced-motion/.test(q), media: q, addEventListener() {}, removeEventListener() {} });
    const onClose = vi.fn();
    wrap(<WelcomeScreen onClose={onClose} />);
    await settle();
    expect(screenEl().getAttribute('data-wl-motion')).toBe('off');
    fireEvent.click(screen.getByRole('button', { name: ru('welcome.skipAria') }));
    expect(onClose).toHaveBeenCalledWith('skip');
    window.matchMedia = original;
  });

  it('маленький знак сайта — значок сайта (стеклянная F на тёмно-синем квадрате), его выбрал владелец', async () => {
    wrap(<WelcomeScreen onClose={() => {}} />);
    await settle();
    const mark = document.querySelector('.fe-wl3__brand img');
    expect(mark.getAttribute('src')).toBe('/favicon-512.png');
    expect(document.querySelector('.fe-wl3 .fe-brand')).toBeNull();
  });

  it('иностранный посетитель: ряд его страны, сравнение с соседней, ведомства его страны; Telegram не предлагается', async () => {
    // Часовой пояс устройства — Лондон; форматирование дат остаётся настоящим.
    const RealFormat = Intl.DateTimeFormat;
    vi.spyOn(Intl, 'DateTimeFormat').mockImplementation((...args) => (args.length ? new RealFormat(...args) : { resolvedOptions: () => ({ timeZone: 'Europe/London' }) }));
    wrap(<WelcomeScreen onClose={() => {}} />, { t: en, locale: 'en' });
    await settle();
    expect(fetchWorldCompareSeries.mock.calls.map((c) => c[0]).sort()).toEqual(['germany', 'united-kingdom']);
    expect(phrase()).toBe(en('welcome.find.phrase', { country: 'United Kingdom', value: '4.6%' }));
    expect(track).toHaveBeenCalledWith('welcome_view', { trigger: 'auto', audience: 'GB' });
    next();
    expect(screen.getByText(en('welcome.fresh.sources', { list: 'ONS, Bank of England, IMF' }))).toBeTruthy();
    next();
    expect(phrase()).toBe(en('welcome.compare.phrase', { home: 'United Kingdom', homeValue: '4.6%', peer: 'Germany', peerValue: '3.9%' }));
    expect(document.querySelector('.fe-wl3-chart__line--peer')).not.toBeNull();
    expect(document.querySelector('.fe-wl3__copy:not([data-out]) a[href*="t.me"]')).toBeNull();
    next();
    expect(phrase()).toBe(en('welcome.account.phrase'));
  });
});

describe('WelcomeGate', () => {
  it('флаг выключен: ни экрана, ни пункта в подвале, ни ручного показа', async () => {
    wrap(<><WelcomeGate /><ul><WelcomeEntry /></ul></>, { path: '/?welcome=1' });
    setFlag(false);
    await advance(WELCOME_OPEN_DELAY_MS + 100);
    expect(screenEl()).toBeNull();
    expect(screen.queryByTestId('welcome-entry')).toBeNull();
    expect(fetchWorldCompareSeries).not.toHaveBeenCalled();
  });

  it('новый гость на главной: экран открывается сам после паузы и только один раз', async () => {
    wrap(<WelcomeGate />);
    setFlag(true);
    expect(screenEl()).toBeNull();
    await advance(WELCOME_OPEN_DELAY_MS + 50);
    await vi.dynamicImportSettled();
    await settle();
    expect(screenEl()).not.toBeNull();
    expect(track).toHaveBeenCalledWith('welcome_view', { trigger: 'auto', audience: 'ru' });
    fireEvent.click(screen.getByRole('button', { name: ru('welcome.skipAria') }));
    await advance(400);
    expect(screenEl()).toBeNull();
    await advance(WELCOME_OPEN_DELAY_MS + 50);
    expect(screenEl()).toBeNull();
    expect(JSON.parse(localStorage.getItem(WELCOME_KEY)).outcome).toBe('skip');
  });

  it.each([
    ['на странице показателя', { path: '/russia/indicator/cpi' }],
    ['вошедшему', { authed: true }],
    ['давнему посетителю', { visits: 9 }],
    ['автоматике', { automation: true }],
  ])('сам не открывается %s', async (_name, { path = '/', authed = false, visits = 1, automation: auto = false }) => {
    auth.isAuthed = authed;
    automation.on = auto;
    wrap(<WelcomeGate />, { path });
    setFlag(true, visits);
    await advance(WELCOME_OPEN_DELAY_MS + 50);
    expect(screenEl()).toBeNull();
  });

  it('не перебивает человека, который уже прокрутил страницу', async () => {
    wrap(<WelcomeGate />);
    setFlag(true);
    window.scrollY = 600;
    await advance(WELCOME_OPEN_DELAY_MS + 50);
    expect(screenEl()).toBeNull();
  });

  it('пункт подвала и ?welcome=1 открывают экран вручную; адрес после закрытия чистый', async () => {
    auth.isAuthed = true; // вручную можно и вошедшему
    wrap(<><WelcomeGate /><ul><WelcomeEntry /></ul></>, { path: '/russia?welcome=1&x=2' });
    setFlag(true, 9);
    await vi.dynamicImportSettled();
    await settle();
    expect(screenEl()).not.toBeNull();
    expect(track).toHaveBeenCalledWith('welcome_view', { trigger: 'manual', audience: 'ru' });
    fireEvent.click(screen.getByRole('button', { name: ru('welcome.skipAria') }));
    await advance(400);
    expect(screenEl()).toBeNull();
    expect(screen.getByTestId('where').textContent).toBe('/russia?x=2');
    fireEvent.click(screen.getByTestId('welcome-entry'));
    await settle();
    expect(screenEl()).not.toBeNull();
  });
});
