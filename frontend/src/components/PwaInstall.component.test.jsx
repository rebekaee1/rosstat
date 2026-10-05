import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LocaleContext } from '../i18n/localeContext';
import { translate } from '../i18n/messages';
import { MESSAGES } from '../i18n/messages';
import PwaInstallPrompt from './PwaInstallPrompt';
import PwaInstallEntry from './PwaInstallEntry';
import * as pwa from '../lib/pwa';
import { track } from '../lib/track';
import { DAY_MS, MIN_PAGE_DWELL_MS, SECOND_VISIT_MIN_GAP_MS } from '../lib/pwaPolicy';

vi.mock('../lib/track', () => ({
  track: vi.fn(),
  events: {
    PWA_INSTALL_PROMPT_VIEW: 'pwa_install_prompt_view',
    PWA_INSTALL_PROMPT_ACCEPT: 'pwa_install_prompt_accept',
    PWA_INSTALL_PROMPT_DISMISS: 'pwa_install_prompt_dismiss',
    PWA_INSTALL_NATIVE_ACCEPTED: 'pwa_install_native_accepted',
    PWA_INSTALL_NATIVE_DISMISSED: 'pwa_install_native_dismissed',
    PWA_INSTALLED: 'pwa_installed',
    PWA_APP_LAUNCH: 'pwa_app_launch',
    PWA_IOS_HINT_VIEW: 'pwa_ios_hint_view',
    PWA_INSTALL_ENTRY_CLICK: 'pwa_install_entry_click',
  },
}));
vi.mock('../context/authContext', () => ({ useAuth: () => ({ isAuthed: false, isLoading: false }) }));

const UA = {
  android: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36',
  iphone: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
  desktop: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
};
const ru = (key, vars) => translate(key, vars, 'ru');
const en = (key, vars) => translate(key, vars, 'en');
const { _store, writeState, emit } = pwa.__testing;
const T0 = 1_800_000_000_000;

function setUa(ua, touch = 0) {
  Object.defineProperty(navigator, 'userAgent', { value: ua, configurable: true });
  Object.defineProperty(navigator, 'maxTouchPoints', { value: touch, configurable: true });
}

function prompt(outcome = 'accepted') {
  const event = new Event('beforeinstallprompt', { cancelable: true });
  event.prompt = vi.fn(async () => {});
  event.userChoice = Promise.resolve({ outcome });
  return event;
}

function renderCard(path = '/russia/indicator/cpi', t = ru, locale = 'ru') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LocaleContext.Provider value={{ locale, t, isPreview: false, setPreviewLocale() {} }}>
        <PwaInstallPrompt />
        <PwaInstallEntry className="foot" />
      </LocaleContext.Provider>
    </MemoryRouter>,
  );
}

/** Состояние «второй заход прошёл давно»: окно имеет право появиться после паузы на странице. */
function secondVisit(extra = {}) {
  writeState({ ..._store.state, visits: 2, firstSeen: T0 - 2 * SECOND_VISIT_MIN_GAP_MS, ...extra });
}
const CONFIG_ON = { sw_enabled: true, install_prompt_enabled: true };
/** Как в приложении: initPwa ставит слушатели и грузит публичный конфиг (подменён). */
const enable = async (config = CONFIG_ON) => {
  globalThis.fetch = vi.fn(async () => ({ ok: true, json: async () => config }));
  pwa.initPwa();
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
};
const advance = async (ms) => { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); };

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval', 'setTimeout', 'clearTimeout'] });
  vi.setSystemTime(T0);
  pwa.resetPwaForTests();
  track.mockClear();
  document.body.innerHTML = '';
  window.matchMedia = vi.fn((q) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} }));
  setUa(UA.android);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('Android: окно «Установить приложение»', () => {
  it('не показывается на первом визите без полезного действия, сколько бы ни прошло', async () => {
    await enable();
    writeState({ ..._store.state, visits: 1, firstSeen: T0 });
    window.dispatchEvent(prompt());
    renderCard();
    await advance(10 * 60_000);
    expect(screen.queryByTestId('pwa-install-card')).toBeNull();
    expect(track).not.toHaveBeenCalledWith('pwa_install_prompt_view', expect.anything());
  });

  it('второй заход: не сразу, а после паузы на странице; показ фиксируется один раз', async () => {
    secondVisit(); await enable(); window.dispatchEvent(prompt());
    renderCard();
    await advance(MIN_PAGE_DWELL_MS - 3000);
    expect(screen.queryByTestId('pwa-install-card')).toBeNull();
    await advance(5000);
    expect(screen.getByTestId('pwa-install-card')).toBeTruthy();
    expect(screen.getByText(ru('pwa.card.title'))).toBeTruthy();
    expect(screen.queryByTestId('pwa-ios-steps')).toBeNull();
    await advance(30_000);
    expect(track.mock.calls.filter(([e]) => e === 'pwa_install_prompt_view')).toEqual([
      ['pwa_install_prompt_view', { platform: 'android' }],
    ]);
  });

  it('полезное действие на первом визите открывает окно, но с задержкой', async () => {
    await enable();
    writeState({ ..._store.state, visits: 1, firstSeen: T0 });
    window.dispatchEvent(prompt());
    renderCard();
    await advance(20_000); // пауза на странице уже прошла
    expect(screen.queryByTestId('pwa-install-card')).toBeNull();
    act(() => { window.dispatchEvent(new CustomEvent('fe:track', { detail: { event: 'download_csv' } })); });
    await advance(3000);
    expect(screen.queryByTestId('pwa-install-card')).toBeNull(); // человек ещё читает результат
    await advance(7000);
    expect(screen.getByTestId('pwa-install-card')).toBeTruthy();
  });

  it('«Установить» вызывает системное окно; отказ в нём откладывает на 3 дня и скрывает карточку', async () => {
    await enable(); secondVisit();
    const event = prompt('dismissed'); window.dispatchEvent(event);
    renderCard();
    await advance(20_000);
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: ru('pwa.card.install') })); });
    await advance(0);
    expect(event.prompt).toHaveBeenCalledTimes(1);
    expect(track).toHaveBeenCalledWith('pwa_install_prompt_accept', { platform: 'android' });
    expect(track).toHaveBeenCalledWith('pwa_install_native_dismissed', { platform: 'android' });
    expect(screen.queryByTestId('pwa-install-card')).toBeNull();
    expect(_store.state.nextAt - Date.now()).toBe(3 * DAY_MS);
  });

  it('«Не сейчас» откладывает с растущими интервалами и шлёт dismiss с номером отказа', async () => {
    secondVisit(); await enable(); window.dispatchEvent(prompt());
    renderCard();
    await advance(20_000);
    fireEvent.click(screen.getByRole('button', { name: ru('pwa.card.later') }));
    expect(track).toHaveBeenCalledWith('pwa_install_prompt_dismiss', { platform: 'android', dismiss_count: 1 });
    expect(_store.state.nextAt - Date.now()).toBe(3 * DAY_MS);
    expect(screen.queryByTestId('pwa-install-card')).toBeNull();
    vi.setSystemTime(T0 + 20_000 + 2 * DAY_MS); // ещё рано
    await advance(3000);
    expect(screen.queryByTestId('pwa-install-card')).toBeNull();
  });

  it('крестик равен «Не сейчас»', async () => {
    secondVisit(); await enable(); window.dispatchEvent(prompt());
    renderCard();
    await advance(20_000);
    fireEvent.click(screen.getByRole('button', { name: ru('common.close') }));
    expect(_store.state.dismissCount).toBe(1);
  });

  it('установившим не показывается, даже если все условия выполнены', async () => {
    secondVisit({ installed: true }); await enable(); window.dispatchEvent(prompt());
    renderCard();
    await advance(60_000);
    expect(screen.queryByTestId('pwa-install-card')).toBeNull();
    expect(screen.queryByTestId('pwa-install-entry')).toBeNull();
  });

  it('запуск в режиме приложения: не показывается', async () => {
    secondVisit(); await enable(); window.dispatchEvent(prompt());
    _store.standalone = true; emit();
    renderCard();
    await advance(60_000);
    expect(screen.queryByTestId('pwa-install-card')).toBeNull();
  });

  it('аварийное выключение флагом install_prompt_enabled=false прячет всё', async () => {
    await enable({ sw_enabled: true, install_prompt_enabled: false });
    secondVisit(); window.dispatchEvent(prompt());
    renderCard();
    await advance(60_000);
    expect(screen.queryByTestId('pwa-install-card')).toBeNull();
    expect(screen.queryByTestId('pwa-install-entry')).toBeNull();
  });

  it('не показывается, пока не загружен конфиг', async () => {
    pwa.initPwa(); // конфиг не отвечает (fetch не подменён → ошибка → null)
    secondVisit(); window.dispatchEvent(prompt());
    renderCard();
    await advance(60_000);
    expect(screen.queryByTestId('pwa-install-card')).toBeNull();
  });

  it('без beforeinstallprompt на Android карточки нет (нечего вызывать)', async () => {
    await enable(); secondVisit();
    renderCard();
    await advance(60_000);
    expect(screen.queryByTestId('pwa-install-card')).toBeNull();
  });

  it('десктоп и скрытые маршруты', async () => {
    secondVisit(); await enable(); window.dispatchEvent(prompt());
    setUa(UA.desktop);
    renderCard();
    await advance(60_000);
    expect(screen.queryByTestId('pwa-install-card')).toBeNull();
    cleanup();
    setUa(UA.android);
    for (const path of ['/admin/bi', '/embed/chart/cpi', '/login']) {
      renderCard(path);
      await advance(60_000);
      expect(screen.queryByTestId('pwa-install-card')).toBeNull();
      cleanup();
    }
  });
});

describe('не наезжает на другие окна', () => {
  const blockers = {
    'баннер согласия': '<div data-analytics-overlay="cookie-consent"></div>',
    'модальное окно': '<div role="dialog" aria-modal="true"></div>',
    'нудж регистрации / обратной связи': '<aside class="fe-nudge-root"></aside>',
  };
  it.each(Object.entries(blockers))('ждёт, пока висит: %s', async (_name, html) => {
    secondVisit(); await enable(); window.dispatchEvent(prompt());
    const holder = document.createElement('div');
    holder.innerHTML = html;
    document.body.appendChild(holder);
    renderCard();
    await advance(60_000);
    expect(screen.queryByTestId('pwa-install-card')).toBeNull();
    holder.remove();
    await advance(3000);
    expect(screen.getByTestId('pwa-install-card')).toBeTruthy();
  });

  it('RegisterNudge узнаёт, что окно установки на экране (флаг cardVisible)', async () => {
    secondVisit(); await enable(); window.dispatchEvent(prompt());
    renderCard();
    await advance(20_000);
    expect(screen.getByTestId('pwa-install-card')).toBeTruthy();
    expect(pwa.__testing._store.cardVisible).toBe(true);
    cleanup();
    expect(pwa.__testing._store.cardVisible).toBe(false);
  });
});

describe('iPhone (Safari): подсказка «Поделиться → На экран Домой»', () => {
  beforeEach(() => setUa(UA.iphone));

  it('показывает подсказку с иконками, без кнопки «Установить», шлёт события показа', async () => {
    await enable(); secondVisit();
    renderCard();
    await advance(20_000);
    expect(screen.getByTestId('pwa-install-card')).toBeTruthy();
    expect(screen.getByTestId('pwa-ios-steps').querySelectorAll('svg').length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText(ru('pwa.ios.step.share'))).toBeTruthy();
    expect(screen.getByText(ru('pwa.ios.step.add'))).toBeTruthy();
    expect(screen.queryByRole('button', { name: ru('pwa.card.install') })).toBeNull();
    expect(track).toHaveBeenCalledWith('pwa_install_prompt_view', { platform: 'ios' });
    expect(track).toHaveBeenCalledWith('pwa_ios_hint_view', { platform: 'ios' });
  });

  it('«Понятно» — пауза 30 дней; «Не сейчас» — обычная лестница', async () => {
    await enable(); secondVisit();
    renderCard();
    await advance(20_000);
    fireEvent.click(screen.getByRole('button', { name: ru('pwa.ios.ok') }));
    expect(track).toHaveBeenCalledWith('pwa_install_prompt_accept', { platform: 'ios' });
    expect(_store.state.nextAt - Date.now()).toBe(30 * DAY_MS);
    expect(_store.state.dismissCount).toBe(0);
    expect(screen.queryByTestId('pwa-install-card')).toBeNull();
  });

  it('английский текст на английском хосте', async () => {
    await enable(); secondVisit();
    renderCard('/', en, 'en');
    await advance(20_000);
    expect(screen.getByText(en('pwa.ios.title'))).toBeTruthy();
    expect(screen.getByText('Share')).toBeTruthy();
    expect(screen.getByText('Add to Home Screen')).toBeTruthy();
  });
});

describe('постоянная точка входа в подвале', () => {
  it('Android: есть при наличии системного окна, клик вызывает его и шлёт событие', async () => {
    await enable();
    const event = prompt('accepted'); window.dispatchEvent(event);
    renderCard();
    const entry = screen.getByTestId('pwa-install-entry');
    expect(entry.textContent).toBe(ru('pwa.entry'));
    await act(async () => { fireEvent.click(entry); });
    expect(track).toHaveBeenCalledWith('pwa_install_entry_click', { platform: 'android' });
    expect(event.prompt).toHaveBeenCalledTimes(1);
    expect(_store.state.dismissCount).toBe(0);
  });

  it('iPhone: открывает окно с подсказкой', async () => {
    setUa(UA.iphone); await enable();
    renderCard();
    fireEvent.click(screen.getByTestId('pwa-install-entry'));
    expect(screen.getByRole('dialog', { name: ru('pwa.ios.title') })).toBeTruthy();
    expect(track).toHaveBeenCalledWith('pwa_install_entry_click', { platform: 'ios' });
    expect(track).toHaveBeenCalledWith('pwa_ios_hint_view', { platform: 'ios' });
    fireEvent.click(screen.getByRole('button', { name: ru('pwa.ios.ok') }));
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('скрыта у установивших и на десктопе', async () => {
    await enable(); window.dispatchEvent(prompt());
    writeState({ ..._store.state, installed: true });
    renderCard();
    expect(screen.queryByTestId('pwa-install-entry')).toBeNull();
    cleanup();
    writeState({ ..._store.state, installed: false });
    setUa(UA.desktop);
    renderCard();
    expect(screen.queryByTestId('pwa-install-entry')).toBeNull();
  });
});

describe('RU/EN паритет', () => {
  it('все ключи pwa.* есть в обоих словарях', () => {
    const keys = (l) => Object.keys(MESSAGES[l]).filter((k) => k.startsWith('pwa.')).sort();
    expect(keys('ru').length).toBeGreaterThanOrEqual(12);
    expect(keys('en')).toEqual(keys('ru'));
    for (const k of keys('ru')) expect(MESSAGES.en[k].trim()).not.toBe('');
  });
});
