import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LocaleContext } from '../../i18n/localeContext';
import { translate } from '../../i18n/messages';
import WelcomeGate, { WelcomeEntry } from './WelcomeGate';
import WelcomeScreen from './WelcomeScreen';
import * as pwa from '../../lib/pwa';
import { track } from '../../lib/track';
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

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date', 'setTimeout', 'clearTimeout'] });
  pwa.resetPwaForTests();
  track.mockClear();
  auth.isAuthed = false;
  auth.isLoading = false;
  cabinet.enabled = true;
  automation.on = false;
  window.scrollY = 0;
});
afterEach(() => { vi.useRealTimers(); });

describe('WelcomeScreen', () => {
  it('четыре шага по порядку, на каждом заголовок шага; «Дальше» листает, последний шаг предлагает аккаунт', () => {
    wrap(<WelcomeScreen onClose={() => {}} />);
    const dialog = screenEl();
    expect(dialog.getAttribute('role')).toBe('dialog');
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(ru('welcome.find.title'));
    for (const step of ['fresh', 'telegram', 'account']) {
      fireEvent.click(screen.getByTestId('welcome-next'));
      expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(ru(`welcome.${step}.title`));
    }
    expect(screen.queryByTestId('welcome-next')).toBeNull();
    const register = screen.getByTestId('welcome-register');
    expect(register.getAttribute('href')).toBe('/register?next=%2F');
    expect(register.className).toContain('fe-cta-gold');
    expect(track.mock.calls.filter(([name]) => name === 'welcome_step').map(([, p]) => p.step)).toEqual(['fresh', 'telegram', 'account']);
    expect(track.mock.calls.filter(([name]) => name === 'welcome_view')).toHaveLength(1);
  });

  it('«Пропустить» есть на каждом шаге, закрывает экран и запоминает исход', async () => {
    const onClose = vi.fn();
    wrap(<WelcomeScreen onClose={onClose} />);
    for (let i = 0; i < 3; i += 1) {
      expect(screen.getByRole('button', { name: ru('welcome.skipAria') })).toBeTruthy();
      fireEvent.click(screen.getByTestId('welcome-next'));
    }
    fireEvent.click(screen.getByRole('button', { name: ru('welcome.skipAria') }));
    await advance(400);
    expect(onClose).toHaveBeenCalledWith('skip');
    expect(readWelcomeSeen().outcome).toBe('skip');
    expect(track).toHaveBeenCalledWith('welcome_skip', { step: 'account', via: 'button' });
  });

  it('клавиатура: Esc пропускает, стрелки листают', async () => {
    const onClose = vi.fn();
    wrap(<WelcomeScreen onClose={onClose} />);
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(ru('welcome.fresh.title'));
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(ru('welcome.find.title'));
    fireEvent.keyDown(document, { key: 'Escape' });
    await advance(400);
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
    wrap(<WelcomeScreen onClose={onClose} />);
    fireEvent.click(screen.getByTestId('welcome-next'));
    fireEvent.click(screen.getByTestId('welcome-next'));
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
    wrap(<WelcomeScreen onClose={() => {}} />);
    for (let i = 0; i < 3; i += 1) fireEvent.click(screen.getByTestId('welcome-next'));
    const points = [...document.querySelectorAll('.fe-wl__points li')].map((li) => li.textContent);
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

  it('английская версия: те же шаги на английском', () => {
    wrap(<WelcomeScreen onClose={() => {}} />, { t: en, locale: 'en' });
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(en('welcome.find.title'));
    expect(screen.getByRole('button', { name: en('welcome.skipAria') })).toBeTruthy();
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
    expect(track).toHaveBeenCalledWith('welcome_view', { trigger: 'auto' });
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
    await advance(0);
    expect(screenEl()).not.toBeNull();
    expect(track).toHaveBeenCalledWith('welcome_view', { trigger: 'manual' });
    fireEvent.click(screen.getByRole('button', { name: ru('welcome.skipAria') }));
    await advance(400);
    expect(screenEl()).toBeNull();
    expect(screen.getByTestId('where').textContent).toBe('/russia?x=2');
    fireEvent.click(screen.getByTestId('welcome-entry'));
    await advance(0);
    expect(screenEl()).not.toBeNull();
  });
});
