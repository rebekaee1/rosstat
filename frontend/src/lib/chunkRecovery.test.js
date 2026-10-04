// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  RELOAD_GUARD_MS,
  beginBusy,
  createChunkRecovery,
  installChunkRecovery,
  isChunkLoadError,
  isUserBusy,
  resetBusyStateForTests,
  trackBusy,
  watchUserInput,
} from './chunkRecovery';

function storage() {
  const data = new Map();
  return { getItem: (key) => (data.has(key) ? data.get(key) : null), setItem: (key, value) => data.set(key, value) };
}

function make(overrides = {}) {
  let t = 1_000_000;
  const clock = { now: () => t, advance: (ms) => { t += ms; } };
  const saved = storage();
  const reload = vi.fn();
  const options = { release: '/assets/main-A.js', getStorage: () => saved, reload, now: clock.now, isBusy: () => false, ...overrides };
  return { clock, saved, reload, options, recover: createChunkRecovery(options) };
}

afterEach(() => {
  resetBusyStateForTests();
  document.body.innerHTML = '';
});

describe('isChunkLoadError', () => {
  it.each([
    'Failed to fetch dynamically imported module: https://x/assets/LiveTicker-abc.js',
    'error loading dynamically imported module: https://x/a.js',
    'Importing a module script failed.',
    'Loading chunk 42 failed.',
    'Loading CSS chunk 7 failed.',
    'Unable to preload CSS for /assets/a.css',
  ])('распознаёт: %s', (message) => {
    expect(isChunkLoadError(message)).toBe(true);
    expect(isChunkLoadError(new TypeError(message))).toBe(true);
  });

  it('распознаёт ChunkLoadError по имени', () => {
    const err = new Error('boom');
    err.name = 'ChunkLoadError';
    expect(isChunkLoadError(err)).toBe(true);
  });

  it('не принимает обычные ошибки кода', () => {
    expect(isChunkLoadError(new TypeError("Cannot read properties of undefined (reading 'default')"))).toBe(false);
    expect(isChunkLoadError(new Error('Network Error'))).toBe(false);
    expect(isChunkLoadError(null)).toBe(false);
    expect(isChunkLoadError(undefined)).toBe(false);
  });
});

describe('защита от петли перезагрузок', () => {
  it('первая ошибка перезагружает страницу, повторные в тот же момент — нет', () => {
    const { recover, reload } = make();
    expect(recover()).toBe(true);
    expect(recover()).toBe(true); // уже перезагружаемся — показывать ошибку не нужно
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('после перезагрузки (новый запуск) в пределах 5 минут не перезагружает снова', () => {
    const { clock, options, reload } = make();
    expect(createChunkRecovery(options)()).toBe(true);
    clock.advance(RELOAD_GUARD_MS - 1);
    expect(createChunkRecovery(options)()).toBe(false);
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('по истечении 5 минут разрешает новую перезагрузку', () => {
    const { clock, options, reload } = make();
    createChunkRecovery(options)();
    clock.advance(RELOAD_GUARD_MS);
    expect(createChunkRecovery(options)()).toBe(true);
    expect(reload).toHaveBeenCalledTimes(2);
  });

  it('новая версия сборки не обходит защиту по времени', () => {
    const { clock, options, reload, saved } = make();
    createChunkRecovery(options)();
    clock.advance(1000);
    const next = createChunkRecovery({ ...options, release: '/assets/main-B.js', getStorage: () => saved });
    expect(next()).toBe(false);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(JSON.parse(saved.getItem('fe:chunk-reload:at')).release).toBe('/assets/main-A.js');
  });

  it('отметка хранит время и версию', () => {
    const { saved, recover } = make();
    recover();
    expect(JSON.parse(saved.getItem('fe:chunk-reload:at'))).toEqual({ at: 1_000_000, release: '/assets/main-A.js' });
  });

  it('часы ушли назад или отметка повреждена — не перезагружает', () => {
    const { clock, saved, options, reload } = make();
    saved.setItem('fe:chunk-reload:at', JSON.stringify({ at: clock.now() + 60_000, release: 'x' }));
    expect(createChunkRecovery(options)()).toBe(false);
    saved.setItem('fe:chunk-reload:at', '{not json');
    expect(createChunkRecovery(options)()).toBe(false);
    saved.setItem('fe:chunk-reload:at', JSON.stringify({ release: 'x' }));
    expect(createChunkRecovery(options)()).toBe(false);
    expect(reload).not.toHaveBeenCalled();
  });

  it.each(['access', 'read', 'write', 'silent write'])('не перезагружает, если sessionStorage недоступен: %s', (failure) => {
    const broken = () => { throw new Error('SecurityError'); };
    const saved = storage();
    if (failure === 'read') saved.getItem = broken;
    if (failure === 'write') saved.setItem = broken;
    if (failure === 'silent write') saved.setItem = () => {};
    const { options, reload } = make({ getStorage: failure === 'access' ? broken : () => saved });
    const recover = createChunkRecovery(options);
    expect(recover()).toBe(false);
    expect(recover()).toBe(false);
    expect(reload).not.toHaveBeenCalled();
  });
});

describe('не перезагружать, пока пользователь занят', () => {
  it('занят — ни перезагрузки, ни отметки; потом можно', () => {
    let busy = true;
    const { options, reload, saved } = make({ isBusy: () => busy });
    const recover = createChunkRecovery(options);
    expect(recover()).toBe(false);
    expect(reload).not.toHaveBeenCalled();
    expect(saved.getItem('fe:chunk-reload:at')).toBeNull();
    busy = false;
    expect(recover()).toBe(true);
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('фокус в текстовом поле = занят', () => {
    document.body.innerHTML = '<input id="q" type="text"><input id="c" type="checkbox"><textarea id="t"></textarea>';
    expect(isUserBusy()).toBe(false);
    document.getElementById('q').focus();
    expect(isUserBusy()).toBe(true);
    document.getElementById('c').focus();
    expect(isUserBusy()).toBe(false);
    document.getElementById('t').focus();
    expect(isUserBusy()).toBe(true);
  });

  it('поле только для чтения и кнопка — не ввод', () => {
    document.body.innerHTML = '<input id="r" type="text" readonly><button id="b">ok</button>';
    document.getElementById('r').focus();
    expect(isUserBusy()).toBe(false);
    document.getElementById('b').focus();
    expect(isUserBusy()).toBe(false);
  });

  it('недавний ввод считается занятостью, через 30 секунд — нет', () => {
    document.body.innerHTML = '<input id="q" type="text">';
    let t = 5_000;
    const stop = watchUserInput(window, () => t);
    document.getElementById('q').dispatchEvent(new Event('input', { bubbles: true }));
    t += 10_000;
    expect(isUserBusy({ now: () => t })).toBe(true);
    t += 25_000;
    expect(isUserBusy({ now: () => t })).toBe(false);
    stop();
  });

  it('идущая загрузка/скачивание = занят до завершения', async () => {
    expect(isUserBusy()).toBe(false);
    const end = beginBusy();
    expect(isUserBusy()).toBe(true);
    end();
    end(); // повторный вызов не уводит счётчик в минус
    expect(isUserBusy()).toBe(false);

    let resolve;
    const pending = trackBusy(new Promise((r) => { resolve = r; }));
    expect(isUserBusy()).toBe(true);
    resolve('done');
    await expect(pending).resolves.toBe('done');
    expect(isUserBusy()).toBe(false);
  });

  it('упавшая загрузка тоже снимает занятость', async () => {
    await expect(trackBusy(Promise.reject(new Error('x')))).rejects.toThrow('x');
    expect(isUserBusy()).toBe(false);
  });
});

describe('installChunkRecovery', () => {
  function setup() {
    const target = new EventTarget();
    const recover = vi.fn();
    installChunkRecovery(target, recover);
    const fire = (type, props) => target.dispatchEvent(Object.assign(new Event(type), props));
    return { recover, fire };
  }

  it('vite:preloadError запускает восстановление и не гасится (иначе lazy получит undefined)', () => {
    const recover = vi.fn();
    const target = new EventTarget();
    installChunkRecovery(target, recover);
    const event = Object.assign(new Event('vite:preloadError', { cancelable: true }), { payload: new Error('x') });
    target.dispatchEvent(event);
    expect(recover).toHaveBeenCalledTimes(1);
    expect(event.defaultPrevented).toBe(false);
  });

  it('ошибка динамического import() в unhandledrejection', () => {
    const { recover, fire } = setup();
    fire('unhandledrejection', { reason: new TypeError('Failed to fetch dynamically imported module: https://x/assets/LiveTicker-abc.js') });
    expect(recover).toHaveBeenCalledTimes(1);
  });

  it('непойманная ошибка React.lazy приходит как window error', () => {
    const { recover, fire } = setup();
    fire('error', { message: 'Uncaught TypeError: Failed to fetch dynamically imported module: https://x/a.js' });
    fire('error', { error: new Error('Loading chunk 3 failed.'), message: 'x' });
    expect(recover).toHaveBeenCalledTimes(2);
  });

  it('обычные ошибки страницу не трогают', () => {
    const { recover, fire } = setup();
    fire('unhandledrejection', { reason: new Error('Network Error') });
    fire('unhandledrejection', { reason: undefined });
    fire('error', { message: 'Uncaught Error: boom' });
    fire('error', {}); // сбой загрузки ресурса: target есть, message нет
    expect(recover).not.toHaveBeenCalled();
  });
});
