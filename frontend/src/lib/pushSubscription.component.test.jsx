import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import api from './api';
import {
  PushNotConfirmedError, PushUnavailableError, getPushState, isPushSupported,
  subscribeToPush, unsubscribeFromPush,
} from './pushSubscription';

vi.mock('./api', () => ({ default: { post: vi.fn(async () => ({ data: { ok: true } })) } }));

const KEY = 'BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U';
let requestPermission;
let subscribeSpy;
let sub;

function setupBrowser({ permission = 'default', outcome = 'granted' } = {}) {
  requestPermission = vi.fn(async () => outcome);
  window.Notification = Object.assign(function Notification() {}, { permission, requestPermission });
  window.PushManager = function PushManager() {};
  sub = { toJSON: () => ({ endpoint: 'https://push.example.com/abc', keys: { p256dh: 'p', auth: 'a' } }), unsubscribe: vi.fn(async () => true) };
  subscribeSpy = vi.fn(async () => sub);
  const registration = { pushManager: { subscribe: subscribeSpy, getSubscription: vi.fn(async () => sub) } };
  Object.defineProperty(navigator, 'serviceWorker', {
    value: { ready: Promise.resolve(registration), getRegistration: vi.fn(async () => registration) },
    configurable: true,
  });
}

function mockConfig(config) {
  globalThis.fetch = vi.fn(async () => ({ ok: true, json: async () => config }));
}

beforeEach(() => { api.post.mockClear(); setupBrowser(); });
afterEach(() => { delete globalThis.fetch; });

describe('никаких автоматических вызовов', () => {
  it('импорт модуля ничего не вызывает: ни разрешение, ни сеть, ни подписку', () => {
    expect(requestPermission).not.toHaveBeenCalled();
    expect(subscribeSpy).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('subscribeToPush() без подтверждения бросает ошибку до любых обращений к браузеру и сети', async () => {
    globalThis.fetch = vi.fn();
    await expect(subscribeToPush()).rejects.toBeInstanceOf(PushNotConfirmedError);
    await expect(subscribeToPush({})).rejects.toBeInstanceOf(PushNotConfirmedError);
    await expect(subscribeToPush({ confirmedByUser: 'yes' })).rejects.toBeInstanceOf(PushNotConfirmedError);
    await expect(subscribeToPush({ confirmedByUser: 1 })).rejects.toBeInstanceOf(PushNotConfirmedError);
    expect(globalThis.fetch).not.toHaveBeenCalled();
    expect(requestPermission).not.toHaveBeenCalled();
    expect(subscribeSpy).not.toHaveBeenCalled();
  });

  it('getPushState только читает: запрос разрешения не показывается', async () => {
    const state = await getPushState();
    expect(state).toEqual({ supported: true, permission: 'default', subscribed: true });
    expect(requestPermission).not.toHaveBeenCalled();
  });

  it('ни один файл приложения не импортирует pushSubscription (вызвать автоматически нечем)', () => {
    const root = resolve(import.meta.dirname, '..');
    const offenders = [];
    const walk = (dir) => {
      for (const name of readdirSync(dir)) {
        const path = join(dir, name);
        if (statSync(path).isDirectory()) { walk(path); continue; }
        if (!/\.(jsx?|mjs)$/.test(name) || /\.test\./.test(name) || name === 'pushSubscription.js') continue;
        if (/pushSubscription/.test(readFileSync(path, 'utf8'))) offenders.push(path.replace(root, 'src'));
      }
    };
    walk(root);
    expect(offenders).toEqual([]);
  });
});

describe('подписка по явному действию', () => {
  it('сервер выключил push: разрешение не запрашивается', async () => {
    mockConfig({ push_enabled: false, vapid_public_key: null });
    await expect(subscribeToPush({ confirmedByUser: true })).rejects.toMatchObject({ name: 'PushUnavailableError', reason: 'disabled' });
    expect(requestPermission).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('запрещено в браузере: ошибка без повторного запроса', async () => {
    setupBrowser({ permission: 'denied' });
    mockConfig({ push_enabled: true, vapid_public_key: KEY });
    await expect(subscribeToPush({ confirmedByUser: true })).rejects.toBeInstanceOf(PushUnavailableError);
    expect(requestPermission).not.toHaveBeenCalled();
  });

  it('пользователь отказал в системном окне: подписки и POST нет', async () => {
    setupBrowser({ outcome: 'denied' });
    mockConfig({ push_enabled: true, vapid_public_key: KEY });
    await expect(subscribeToPush({ confirmedByUser: true })).rejects.toMatchObject({ reason: 'denied' });
    expect(requestPermission).toHaveBeenCalledTimes(1);
    expect(subscribeSpy).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('полный путь: разрешение → подписка с ключом VAPID → один POST', async () => {
    mockConfig({ push_enabled: true, vapid_public_key: KEY });
    await expect(subscribeToPush({ confirmedByUser: true })).resolves.toBe(true);
    expect(requestPermission).toHaveBeenCalledTimes(1);
    const options = subscribeSpy.mock.calls[0][0];
    expect(options.userVisibleOnly).toBe(true);
    expect(options.applicationServerKey).toBeInstanceOf(Uint8Array);
    expect(options.applicationServerKey.length).toBe(65);
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(api.post).toHaveBeenCalledWith('/push/subscribe', sub.toJSON());
  });

  it('уже выданное разрешение повторно не запрашивается', async () => {
    setupBrowser({ permission: 'granted' });
    mockConfig({ push_enabled: true, vapid_public_key: KEY });
    await subscribeToPush({ confirmedByUser: true });
    expect(requestPermission).not.toHaveBeenCalled();
  });

  it('отписка: снимает подписку в браузере и просит сервер удалить строку', async () => {
    await expect(unsubscribeFromPush()).resolves.toBe(true);
    expect(sub.unsubscribe).toHaveBeenCalled();
    expect(api.post).toHaveBeenCalledWith('/push/unsubscribe', { endpoint: 'https://push.example.com/abc' });
  });

  it('браузер без поддержки push', async () => {
    delete window.PushManager;
    expect(isPushSupported()).toBe(false);
    expect(await getPushState()).toMatchObject({ supported: false });
    expect(await unsubscribeFromPush()).toBe(false);
  });
});
