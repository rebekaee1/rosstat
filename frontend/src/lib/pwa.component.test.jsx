import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { track } from './track';
import { USEFUL_EVENTS } from './pwaPolicy';

vi.mock('./track', () => ({
  track: vi.fn(),
  events: {
    PWA_APP_LAUNCH: 'pwa_app_launch',
    PWA_INSTALLED: 'pwa_installed',
    PWA_INSTALL_PROMPT_DISMISS: 'pwa_install_prompt_dismiss',
    PWA_INSTALL_PROMPT_ACCEPT: 'pwa_install_prompt_accept',
    PWA_INSTALL_NATIVE_ACCEPTED: 'pwa_install_native_accepted',
    PWA_INSTALL_NATIVE_DISMISSED: 'pwa_install_native_dismissed',
  },
}));

let pwa;
const flush = () => new Promise((r) => setTimeout(r, 0));

function setStandalone(on) {
  window.matchMedia = vi.fn((q) => ({
    matches: on && /standalone/.test(q), media: q, addEventListener() {}, removeEventListener() {},
  }));
}

function mockServiceWorker() {
  const registration = { update: vi.fn(async () => {}), unregister: vi.fn(async () => true) };
  const sw = {
    register: vi.fn(async () => registration),
    getRegistrations: vi.fn(async () => [registration]),
  };
  Object.defineProperty(navigator, 'serviceWorker', { value: sw, configurable: true });
  return { sw, registration };
}

function mockConfig(config, ok = true) {
  globalThis.fetch = vi.fn(async () => (ok
    ? { ok: true, json: async () => config }
    : { ok: false, json: async () => ({}) }));
}

beforeEach(async () => {
  vi.resetModules();
  pwa = await import('./pwa');
  pwa.resetPwaForTests();
  track.mockClear();
  localStorage.clear();
  sessionStorage.clear();
  localStorage.setItem('fe:pwa:dev', '1'); // в dev SW по умолчанию не регистрируется
  setStandalone(false);
  Object.defineProperty(navigator, 'getInstalledRelatedApps', { value: undefined, configurable: true });
  Object.defineProperty(window.navigator, 'standalone', { value: undefined, configurable: true });
});
afterEach(() => {
  delete globalThis.fetch;
  Object.defineProperty(navigator, 'serviceWorker', { value: undefined, configurable: true });
});

describe('service worker и аварийный выход', () => {
  it('регистрирует /sw.js, когда конфиг разрешает', async () => {
    const { sw, registration } = mockServiceWorker();
    mockConfig({ sw_enabled: true, install_prompt_enabled: true });
    pwa.initPwa();
    await flush(); await flush();
    expect(sw.register).toHaveBeenCalledWith('/sw.js', { scope: '/' });
    expect(registration.update).toHaveBeenCalled();
    expect(pwa.__testing._store.config).toEqual({ sw_enabled: true, install_prompt_enabled: true });
  });

  it('kill-switch: sw_enabled=false снимает регистрации, чистит кэши fe- и не регистрирует', async () => {
    const { sw, registration } = mockServiceWorker();
    const deleted = [];
    window.caches = {
      keys: async () => ['fe-offline-1', 'other-app-cache'],
      delete: async (n) => { deleted.push(n); return true; },
    };
    mockConfig({ sw_enabled: false, install_prompt_enabled: false });
    pwa.initPwa();
    await flush(); await flush();
    expect(sw.register).not.toHaveBeenCalled();
    expect(registration.unregister).toHaveBeenCalled();
    expect(deleted).toEqual(['fe-offline-1']); // чужие кэши не трогаем
    delete window.caches;
  });

  it('нет конфига (сеть/старый backend): SW не регистрируем и не трогаем', async () => {
    const { sw, registration } = mockServiceWorker();
    mockConfig(null, false);
    pwa.initPwa();
    await flush(); await flush();
    expect(sw.register).not.toHaveBeenCalled();
    expect(registration.unregister).not.toHaveBeenCalled();
    expect(pwa.__testing._store.config).toBeNull();
  });

  it('в dev без явного флага service worker не регистрируется', async () => {
    localStorage.removeItem('fe:pwa:dev');
    const { sw } = mockServiceWorker();
    mockConfig({ sw_enabled: true, install_prompt_enabled: true });
    pwa.initPwa();
    await flush(); await flush();
    expect(sw.register).not.toHaveBeenCalled();
  });

  it('инициализация идемпотентна: конфиг запрашивается один раз', async () => {
    mockServiceWorker();
    mockConfig({ sw_enabled: true, install_prompt_enabled: true });
    pwa.initPwa(); pwa.initPwa();
    await flush();
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
  });
});

describe('надёжное определение «установлено»', () => {
  it('appinstalled: запоминает навсегда и шлёт pwa_installed', async () => {
    mockServiceWorker(); mockConfig({ sw_enabled: true, install_prompt_enabled: true });
    pwa.initPwa();
    window.dispatchEvent(new Event('appinstalled'));
    expect(pwa.__testing._store.state.installed).toBe(true);
    expect(JSON.parse(localStorage.getItem('fe:pwa:v1')).installed).toBe(true);
    expect(track).toHaveBeenCalledWith('pwa_installed', expect.objectContaining({ platform: expect.any(String) }));
  });

  it('запуск в standalone: installed + pwa_app_launch один раз за сессию', async () => {
    setStandalone(true);
    mockServiceWorker(); mockConfig({ sw_enabled: true, install_prompt_enabled: true });
    pwa.initPwa();
    expect(pwa.__testing._store.state.installed).toBe(true);
    expect(track.mock.calls.filter(([e]) => e === 'pwa_app_launch')).toHaveLength(1);
    vi.resetModules();
    const again = await import('./pwa');
    again.initPwa(); // та же сессия браузера — повторного запуска нет
    expect(track.mock.calls.filter(([e]) => e === 'pwa_app_launch')).toHaveLength(1);
  });

  it('iOS navigator.standalone тоже считается установкой', async () => {
    Object.defineProperty(window.navigator, 'standalone', { value: true, configurable: true });
    mockServiceWorker(); mockConfig({ sw_enabled: true, install_prompt_enabled: true });
    pwa.initPwa();
    expect(pwa.__testing._store.state.installed).toBe(true);
  });

  it('getInstalledRelatedApps: приложение стоит, хотя запущено в браузере', async () => {
    Object.defineProperty(navigator, 'getInstalledRelatedApps', {
      value: vi.fn(async () => [{ platform: 'webapp', url: 'https://x/manifest.webmanifest' }]),
      configurable: true,
    });
    mockServiceWorker(); mockConfig({ sw_enabled: true, install_prompt_enabled: true });
    pwa.initPwa();
    await flush();
    expect(pwa.__testing._store.state.installed).toBe(true);
  });

  it('пустой ответ getInstalledRelatedApps не отмечает установку', async () => {
    Object.defineProperty(navigator, 'getInstalledRelatedApps', { value: vi.fn(async () => []), configurable: true });
    mockServiceWorker(); mockConfig({ sw_enabled: true, install_prompt_enabled: true });
    pwa.initPwa();
    await flush();
    expect(pwa.__testing._store.state.installed).toBe(false);
  });
});

describe('заходы и полезные действия', () => {
  it('новая сессия браузера = новый заход; перезагрузка вкладки не считается', async () => {
    mockServiceWorker(); mockConfig({ sw_enabled: true, install_prompt_enabled: true });
    pwa.initPwa();
    expect(pwa.__testing._store.state.visits).toBe(1);
    vi.resetModules();
    const reload = await import('./pwa');
    reload.initPwa(); // sessionStorage сохранён — это та же сессия
    expect(reload.__testing._store.state.visits).toBe(1);
    sessionStorage.clear(); // вкладку закрыли и открыли снова
    vi.resetModules();
    const next = await import('./pwa');
    next.initPwa();
    expect(next.__testing._store.state.visits).toBe(2);
  });

  it('полезное событие трекинга записывается; прочие игнорируются', async () => {
    mockServiceWorker(); mockConfig({ sw_enabled: true, install_prompt_enabled: true });
    pwa.initPwa();
    window.dispatchEvent(new CustomEvent('fe:track', { detail: { event: 'scroll_depth' } }));
    expect(pwa.__testing._store.state.usefulAt).toBe(0);
    window.dispatchEvent(new CustomEvent('fe:track', { detail: { event: 'download_csv' } }));
    expect(pwa.__testing._store.state.usefulAt).toBeGreaterThan(0);
    expect(USEFUL_EVENTS.has('download_csv')).toBe(true);
  });
});

describe('системное окно установки (Android)', () => {
  function stubPrompt(outcome) {
    const event = new Event('beforeinstallprompt', { cancelable: true });
    event.prompt = vi.fn(async () => {});
    event.userChoice = Promise.resolve({ outcome });
    return event;
  }

  it('перехватывает beforeinstallprompt и отменяет мини-инфобар', async () => {
    mockServiceWorker(); mockConfig({ sw_enabled: true, install_prompt_enabled: true });
    pwa.initPwa();
    const event = stubPrompt('accepted');
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
    expect(pwa.__testing._store.deferredPrompt).toBe(event);
  });

  it('согласие: native_accepted, показ не откладывается (appinstalled закрепит установку)', async () => {
    mockServiceWorker(); mockConfig({ sw_enabled: true, install_prompt_enabled: true });
    pwa.initPwa();
    const event = stubPrompt('accepted');
    window.dispatchEvent(event);
    expect(await pwa.promptNativeInstall()).toBe('accepted');
    expect(event.prompt).toHaveBeenCalledTimes(1);
    expect(track).toHaveBeenCalledWith('pwa_install_native_accepted', { platform: 'android' });
    expect(pwa.__testing._store.state.dismissCount).toBe(0);
    expect(pwa.__testing._store.deferredPrompt).toBeNull(); // событие одноразовое
    expect(await pwa.promptNativeInstall()).toBe('unavailable');
  });

  it('отказ в системном окне из карточки считается «Не сейчас» (3 дня)', async () => {
    mockServiceWorker(); mockConfig({ sw_enabled: true, install_prompt_enabled: true });
    pwa.initPwa();
    window.dispatchEvent(stubPrompt('dismissed'));
    const before = Date.now();
    expect(await pwa.promptNativeInstall({ fromCard: true })).toBe('dismissed');
    expect(track).toHaveBeenCalledWith('pwa_install_native_dismissed', { platform: 'android' });
    const { dismissCount, nextAt } = pwa.__testing._store.state;
    expect(dismissCount).toBe(1);
    expect(nextAt - before).toBeGreaterThanOrEqual(3 * 24 * 3600 * 1000 - 5);
  });

  it('отказ из подвала не откладывает карточку', async () => {
    mockServiceWorker(); mockConfig({ sw_enabled: true, install_prompt_enabled: true });
    pwa.initPwa();
    window.dispatchEvent(stubPrompt('dismissed'));
    await pwa.promptNativeInstall({ fromCard: false });
    expect(pwa.__testing._store.state.dismissCount).toBe(0);
  });
});
