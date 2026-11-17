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
  'united-states': series(4.1),
  'united-kingdom': series(4.6),
  germany: series(3.9),
};

const ru = (key, vars) => translate(key, vars, 'ru');
const en = (key, vars) => translate(key, vars, 'en');
const { _store, emit } = pwa.__testing;

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
const screenEl = () => screen.queryByTestId('welcome-screen');
const title = (t, step) => t(`welcome.${step}.title`).replace('|', ' ');
const heading = () => screen.getByRole('heading', { level: 2 }).textContent;
const start = () => fireEvent.click(screen.getByTestId('welcome-start'));
const settle = () => advance(0);
const sceneText = () => [...document.querySelectorAll('.fe-wl__art-in:not([data-out]) text')].map((el) => el.textContent);

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
afterEach(() => { vi.useRealTimers(); });

describe('WelcomeScreen', () => {
  it('приветствие, затем четыре шага по порядку; «Дальше» листает, последний шаг предлагает аккаунт', () => {
    wrap(<WelcomeScreen onClose={() => {}} />);
    const dialog = screenEl();
    expect(dialog.getAttribute('role')).toBe('dialog');
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(dialog.getAttribute('data-wl-kind')).toBe('hello');
    expect(heading()).toBe(title(ru, 'hello'));
    expect(screen.queryByTestId('welcome-next')).toBeNull(); // на приветствии одна кнопка
    start();
    expect(dialog.getAttribute('data-wl-kind')).toBe('step');
    expect(heading()).toBe(title(ru, 'find'));
    for (const step of ['fresh', 'telegram', 'account']) {
      fireEvent.click(screen.getByTestId('welcome-next'));
      expect(heading()).toBe(title(ru, step));
    }
    expect(screen.queryByTestId('welcome-next')).toBeNull();
    const register = screen.getByTestId('welcome-register');
    expect(register.getAttribute('href')).toBe('/register?next=%2F');
    expect(register.className).toContain('fe-wl__btn--gold');
    expect(document.querySelectorAll('.fe-wl__btn--gold')).toHaveLength(1);
    expect(track.mock.calls.filter(([name]) => name === 'welcome_step').map(([, p]) => p.step)).toEqual(['find', 'fresh', 'telegram', 'account']);
    expect(track.mock.calls.filter(([name]) => name === 'welcome_view')).toEqual([['welcome_view', { trigger: 'auto', audience: 'ru' }]]);
  });

  it('уходящий экран остаётся на месте на время перехода и не ловит фокус', async () => {
    wrap(<WelcomeScreen onClose={() => {}} />);
    start();
    const out = document.querySelector('.fe-wl__copy[data-out="true"]');
    expect(out.getAttribute('data-screen')).toBe('hello');
    expect(out.getAttribute('aria-hidden')).toBe('true');
    expect(out.hasAttribute('inert')).toBe(true);
    await advance(400);
    expect(document.querySelector('.fe-wl__copy[data-out="true"]')).toBeNull();
  });

  it('«Пропустить» есть на каждом экране, закрывает и запоминает исход', async () => {
    const onClose = vi.fn();
    wrap(<WelcomeScreen onClose={onClose} />);
    expect(screen.getByRole('button', { name: ru('welcome.skipAria') })).toBeTruthy();
    start();
    for (let i = 0; i < 3; i += 1) {
      expect(screen.getByRole('button', { name: ru('welcome.skipAria') })).toBeTruthy();
      fireEvent.click(screen.getByTestId('welcome-next'));
    }
    fireEvent.click(screen.getByRole('button', { name: ru('welcome.skipAria') }));
    expect(screenEl().getAttribute('data-wl-leaving')).toBe('skip');
    await advance(700);
    expect(onClose).toHaveBeenCalledWith('skip');
    expect(readWelcomeSeen().outcome).toBe('skip');
    expect(track).toHaveBeenCalledWith('welcome_skip', { step: 'account', via: 'button' });
  });

  it('«На сайт» на последнем шаге поднимает занавес и закрывает', async () => {
    const onClose = vi.fn();
    wrap(<WelcomeScreen initialStep={4} onClose={onClose} />);
    fireEvent.click(screen.getByTestId('welcome-done'));
    expect(screenEl().getAttribute('data-wl-leaving')).toBe('done');
    await advance(1400);
    expect(onClose).toHaveBeenCalledWith('done');
    expect(track).toHaveBeenCalledWith('welcome_done');
  });

  it('клавиатура: Esc пропускает, стрелки листают', async () => {
    const onClose = vi.fn();
    wrap(<WelcomeScreen onClose={onClose} />);
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    expect(heading()).toBe(title(ru, 'fresh'));
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    fireEvent.keyDown(document, { key: 'ArrowLeft' }); // с первого шага назад на приветствие не уходим
    expect(heading()).toBe(title(ru, 'find'));
    fireEvent.keyDown(document, { key: 'Escape' });
    await advance(700);
    expect(onClose).toHaveBeenCalledWith('skip');
  });

  it('пока экран открыт, страница под ним неактивна и не прокручивается; после закрытия всё возвращается', () => {
    const view = wrap(<WelcomeScreen onClose={() => {}} />);
    const app = document.getElementById('root');
    expect(app.hasAttribute('inert')).toBe(true);
    expect(document.documentElement.style.overflow).toBe('hidden');
    expect(app.contains(screenEl())).toBe(false); // портал в body
    view.unmount();
    expect(document.documentElement.style.overflow).toBe('');
  });

  it('шаг Telegram ведёт на бота и канал в новой вкладке и не закрывает экран', () => {
    const onClose = vi.fn();
    wrap(<WelcomeScreen initialStep={3} onClose={onClose} />);
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

  it('без кабинета на сервере не обещает «сохранять» и «следить»', () => {
    cabinet.enabled = false;
    wrap(<WelcomeScreen initialStep={4} onClose={() => {}} />);
    const points = [...document.querySelectorAll('.fe-wl__copy:not([data-out]) .fe-wl__points li')].map((li) => li.textContent);
    expect(points).toEqual([ru('welcome.account.download')]);
  });

  it('«меньше движения»: экран помечен data-wl-motion="off" и закрывается сразу', () => {
    const original = window.matchMedia;
    window.matchMedia = (q) => ({ matches: /reduced-motion/.test(q), media: q, addEventListener() {}, removeEventListener() {} });
    const onClose = vi.fn();
    wrap(<WelcomeScreen onClose={onClose} />);
    expect(screenEl().getAttribute('data-wl-motion')).toBe('off');
    fireEvent.click(screen.getByRole('button', { name: ru('welcome.skipAria') }));
    expect(onClose).toHaveBeenCalledWith('skip');
    window.matchMedia = original;
  });

  it('английская версия: вместо Telegram — сравнение стран, бот и канал не предлагаются', () => {
    wrap(<WelcomeScreen onClose={() => {}} />, { t: en, locale: 'en' });
    expect(heading()).toBe(title(en, 'hello'));
    expect(screen.getByRole('button', { name: en('welcome.skipAria') })).toBeTruthy();
    start();
    const seen = [heading()];
    for (let i = 0; i < 3; i += 1) {
      fireEvent.click(screen.getByTestId('welcome-next'));
      seen.push(heading());
      expect(document.querySelector('.fe-wl__copy:not([data-out]) a[href*="t.me"]')).toBeNull();
    }
    expect(seen).toEqual(['find', 'fresh', 'compare', 'account'].map((step) => title(en, step)));
  });

  it('иностранному посетителю показываются ведомства его страны (пояс устройства и язык браузера)', () => {
    const original = Intl.DateTimeFormat;
    vi.spyOn(Intl, 'DateTimeFormat').mockImplementation(() => ({ resolvedOptions: () => ({ timeZone: 'Europe/London' }) }));
    wrap(<WelcomeScreen initialStep={2} onClose={() => {}} />, { t: en, locale: 'en' });
    const chips = [...document.querySelectorAll('.fe-wl-svg__chip')].map((el) => el.textContent);
    expect(chips).toEqual(['ONS', 'Bank of England', 'IMF']);
    expect(track).toHaveBeenCalledWith('welcome_view', { trigger: 'auto', audience: 'GB' });
    Intl.DateTimeFormat.mockRestore?.();
    expect(Intl.DateTimeFormat).toBe(original);
  });

  it('русская версия берёт подписи источников из словаря, страну посетителя не определяет', () => {
    wrap(<WelcomeScreen initialStep={2} onClose={() => {}} />);
    const chips = [...document.querySelectorAll('.fe-wl-svg__chip')].map((el) => el.textContent);
    expect(chips).toEqual([ru('welcome.fresh.source1'), ru('welcome.fresh.source2'), ru('welcome.fresh.source3')]);
  });
});

describe('показ идёт сам', () => {
  it('экраны сменяются без единого нажатия и останавливаются на шаге про аккаунт', async () => {
    const onClose = vi.fn();
    wrap(<WelcomeScreen onClose={onClose} />);
    await settle();
    expect(screenEl().getAttribute('data-wl-auto')).toBe('on');
    expect(heading()).toBe(title(ru, 'hello'));
    await advance(5300);
    expect(heading()).toBe(title(ru, 'find'));
    await advance(7900);
    expect(heading()).toBe(title(ru, 'fresh'));
    await advance(7700);
    expect(heading()).toBe(title(ru, 'telegram'));
    await advance(8100);
    expect(heading()).toBe(title(ru, 'account'));
    // Последний шаг ждёт человека: сам не закрывается и не уезжает.
    await advance(60000);
    expect(heading()).toBe(title(ru, 'account'));
    expect(onClose).not.toHaveBeenCalled();
    expect(screenEl().getAttribute('data-wl-auto')).toBe('off');
    expect(screen.queryByTestId('welcome-pause')).toBeNull();
    expect(track.mock.calls.filter(([n]) => n === 'welcome_step').map(([, v]) => v.via)).toEqual(['auto', 'auto', 'auto', 'auto']);
  });

  it('кнопка паузы останавливает показ и пускает его снова', async () => {
    wrap(<WelcomeScreen onClose={() => {}} />);
    await settle();
    const pause = screen.getByTestId('welcome-pause');
    expect(pause.getAttribute('aria-label')).toBe(ru('welcome.pause'));
    fireEvent.click(pause);
    expect(pause.getAttribute('aria-pressed')).toBe('true');
    expect(pause.getAttribute('aria-label')).toBe(ru('welcome.play'));
    expect(screenEl().getAttribute('data-wl-paused')).toBe('true');
    await advance(30000);
    expect(heading()).toBe(title(ru, 'hello'));
    fireEvent.click(pause);
    await advance(5300);
    expect(heading()).toBe(title(ru, 'find'));
  });

  it('пока палец или кнопка мыши на сцене, показ ждёт и продолжает с того же места', async () => {
    wrap(<WelcomeScreen onClose={() => {}} />);
    await settle();
    await advance(3000);
    const stage = document.querySelector('.fe-wl__stage');
    fireEvent.pointerDown(stage, { pointerType: 'mouse', clientX: 10, clientY: 10 });
    await advance(20000);
    expect(heading()).toBe(title(ru, 'hello'));
    fireEvent.pointerUp(stage, { pointerType: 'mouse', clientX: 10, clientY: 10 });
    await advance(1500);
    expect(heading()).toBe(title(ru, 'hello')); // оставалось больше двух секунд
    await advance(1000);
    expect(heading()).toBe(title(ru, 'find'));
  });

  it('с клавиатуры человек ведёт сам: после Tab или стрелки показ больше не листает', async () => {
    wrap(<WelcomeScreen onClose={() => {}} />);
    await settle();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(screenEl().getAttribute('data-wl-auto')).toBe('off');
    await advance(30000);
    expect(heading()).toBe(title(ru, 'hello'));
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    expect(heading()).toBe(title(ru, 'find'));
    await advance(30000);
    expect(heading()).toBe(title(ru, 'find'));
  });

  it('«Назад» останавливает показ: человек вернулся перечитать', async () => {
    wrap(<WelcomeScreen onClose={() => {}} />);
    await settle();
    start();
    fireEvent.click(screen.getByTestId('welcome-next'));
    fireEvent.click(screen.getByRole('button', { name: ru('welcome.back') }));
    expect(heading()).toBe(title(ru, 'find'));
    await advance(30000);
    expect(heading()).toBe(title(ru, 'find'));
  });

  it('«меньше движения»: показ сам не идёт, кнопки паузы нет, листает человек', async () => {
    const original = window.matchMedia;
    window.matchMedia = (q) => ({ matches: /reduced-motion/.test(q), media: q, addEventListener() {}, removeEventListener() {} });
    wrap(<WelcomeScreen onClose={() => {}} />);
    await settle();
    expect(screenEl().getAttribute('data-wl-auto')).toBe('off');
    expect(screen.queryByTestId('welcome-pause')).toBeNull();
    await advance(60000);
    expect(heading()).toBe(title(ru, 'hello'));
    start();
    expect(heading()).toBe(title(ru, 'find'));
    window.matchMedia = original;
  });

  it('открытие сразу на шаге (проверка на устройствах) стоит на месте', async () => {
    wrap(<WelcomeScreen initialStep={2} onClose={() => {}} />);
    await settle();
    await advance(60000);
    expect(heading()).toBe(title(ru, 'fresh'));
  });
});

describe('сцены показывают настоящее', () => {
  it('в сценах — название показателя, страна, последнее значение, месяц и источник из ряда сайта', async () => {
    wrap(<WelcomeScreen initialStep={1} onClose={() => {}} />);
    await settle();
    expect(fetchWorldCompareSeries.mock.calls.map((c) => c[0]).sort()).toEqual(['russia', 'united-states']);
    expect(screenEl().getAttribute('data-wl-data')).toBe('ready');
    const find = sceneText();
    expect(find).toContain(ru('welcome.scene.indicator'));
    expect(find).toContain('2,2\u00a0%');
    expect(find).toContain('4,1\u00a0%');
    expect(find).toContain('октябрь 2026, Росстат');
    fireEvent.click(screen.getByTestId('welcome-next'));
    expect(sceneText()).toContain('Россия, октябрь 2026, Росстат');
    fireEvent.click(screen.getByTestId('welcome-next'));
    expect(sceneText()).toContain(ru('welcome.scene.answer', { value: '2,2\u00a0%' }));
  });

  it('знак сайта в сцене — стеклянная F значка сайта; плоской «F.» нет нигде', async () => {
    wrap(<WelcomeScreen initialStep={3} onClose={() => {}} />);
    await settle();
    const mark = document.querySelector('.fe-wl__art-in image');
    expect(mark.getAttribute('href')).toBe('/favicon-512.png');
    expect(document.querySelector('.fe-wl__mark img').getAttribute('src')).toBe('/favicon-512.png');
    expect(document.querySelector('.fe-wl .fe-brand')).toBeNull();
    // Прежний плоский знак рисовался контуром «M51.5 53V40.5…»: его больше нет.
    expect(document.querySelector('.fe-wl').innerHTML).not.toContain('M51.5 53');
  });

  it('данные не пришли — в сценах остаются названия, но нет ни одного числа', async () => {
    fetchWorldCompareSeries.mockRejectedValue(new Error('down'));
    wrap(<WelcomeScreen initialStep={1} onClose={() => {}} />);
    await settle();
    expect(screenEl().getAttribute('data-wl-data')).toBe('empty');
    for (let i = 0; i < 4; i += 1) {
      const text = sceneText().join(' ');
      expect(text).not.toMatch(/\d/);
      if (i < 3) fireEvent.click(screen.getByTestId('welcome-next'));
    }
  });

  it('иностранный посетитель видит ряд своей страны и соседней', async () => {
    const RealFormat = Intl.DateTimeFormat;
    vi.spyOn(Intl, 'DateTimeFormat').mockImplementation((...args) => (args.length ? new RealFormat(...args) : { resolvedOptions: () => ({ timeZone: 'Europe/London' }) }));
    wrap(<WelcomeScreen initialStep={3} onClose={() => {}} />, { t: en, locale: 'en' });
    await settle();
    expect(fetchWorldCompareSeries.mock.calls.map((c) => c[0]).sort()).toEqual(['germany', 'united-kingdom']);
    expect(sceneText()).toEqual(expect.arrayContaining(['United Kingdom 4.6%', 'Germany 3.9%']));
    vi.restoreAllMocks();
  });
});

describe('WelcomeGate', () => {
  it('флаг выключен: ни экрана, ни пункта в подвале, ни ручного показа', async () => {
    wrap(<><WelcomeGate /><ul><WelcomeEntry /></ul></>, { path: '/?welcome=1' });
    setFlag(false);
    await advance(WELCOME_OPEN_DELAY_MS + 100);
    expect(screenEl()).toBeNull();
    expect(screen.queryByTestId('welcome-entry')).toBeNull();
  });

  it('новый гость на главной: экран открывается сам после паузы и только один раз', async () => {
    wrap(<WelcomeGate />);
    setFlag(true);
    expect(screenEl()).toBeNull();
    await advance(WELCOME_OPEN_DELAY_MS + 50);
    await vi.dynamicImportSettled();
    await advance(0);
    expect(screenEl()).not.toBeNull();
    expect(track).toHaveBeenCalledWith('welcome_view', { trigger: 'auto', audience: 'ru' });
    fireEvent.click(screen.getByRole('button', { name: ru('welcome.skipAria') }));
    await advance(700);
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
    await advance(0);
    expect(screenEl()).not.toBeNull();
    expect(track).toHaveBeenCalledWith('welcome_view', { trigger: 'manual', audience: 'ru' });
    fireEvent.click(screen.getByRole('button', { name: ru('welcome.skipAria') }));
    await advance(700);
    expect(screenEl()).toBeNull();
    expect(screen.getByTestId('where').textContent).toBe('/russia?x=2');
    fireEvent.click(screen.getByTestId('welcome-entry'));
    await advance(0);
    expect(screenEl()).not.toBeNull();
  });
});
