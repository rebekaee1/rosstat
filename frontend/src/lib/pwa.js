// Веб-приложение (PWA, 2026-10-05): регистрация service worker, захват события
// установки, определение «уже установлено», флаги из публичного конфига.
//
// initPwa() вызывается один раз из main.jsx ДО монтирования React: событие
// beforeinstallprompt может прийти раньше, чем появится первый компонент.
// Состояние (когда звать, сколько раз отказывали) хранится в localStorage, а не в
// аналитике; почту/идентификаторы сюда не кладём.
//
// Аварийный выход без пересборки: GET /api/v1/pwa/config → sw_enabled=false снимает
// все регистрации service worker и чистит кэши `fe-` (то же самое делает сам sw.js).
import { useSyncExternalStore } from 'react';
import { track, events } from './track';
import {
  USEFUL_EVENTS, afterDismiss, afterIosAck, detectPlatform, emptyState,
} from './pwaPolicy';

const STATE_KEY = 'fe:pwa:v1';
const SESSION_KEY = 'fe:pwa:session';
const LAUNCH_KEY = 'fe:pwa:launch';
const CONFIG_URL = '/api/v1/pwa/config';

let _initialized = false;
const _teardown = []; // снятие слушателей (нужно тестам; в приложении initPwa вызывается один раз)
let _version = 0;
const _listeners = new Set();
const _store = {
  config: null, // { sw_enabled, install_prompt_enabled } | null — пока не загружен
  deferredPrompt: null, // BeforeInstallPromptEvent (Android Chrome/Яндекс Браузер/Samsung)
  standalone: false,
  sessionUsefulAt: 0,
  cardVisible: false,
  state: emptyState(),
};

function emit() {
  _version += 1;
  _listeners.forEach((fn) => fn());
}

function readState() {
  try {
    const raw = JSON.parse(localStorage.getItem(STATE_KEY) || 'null');
    return raw && raw.v === 1 ? { ...emptyState(), ...raw } : emptyState();
  } catch { return emptyState(); }
}

function writeState(next) {
  _store.state = next;
  try { localStorage.setItem(STATE_KEY, JSON.stringify(next)); } catch { /* приватный режим */ }
  emit();
}

export function isStandalone() {
  if (typeof window === 'undefined') return false;
  try {
    return Boolean(
      window.matchMedia?.('(display-mode: standalone)').matches
      || window.matchMedia?.('(display-mode: fullscreen)').matches
      || window.navigator.standalone === true
      || (document.referrer || '').startsWith('android-app://'),
    );
  } catch { return false; }
}

export function currentPlatform() {
  if (typeof navigator === 'undefined') return 'desktop';
  return detectPlatform({ userAgent: navigator.userAgent, maxTouchPoints: navigator.maxTouchPoints || 0 });
}

export function inIframe() {
  try { return window.self !== window.top; } catch { return true; }
}

function markInstalled() {
  if (_store.state.installed) return;
  writeState({ ..._store.state, installed: true });
}

function sessionFlag(key) {
  try {
    if (window.sessionStorage.getItem(key)) return true;
    window.sessionStorage.setItem(key, '1');
    return false;
  } catch { return true; }
}

async function unregisterAll() {
  try {
    const regs = await navigator.serviceWorker.getRegistrations();
    await Promise.all(regs.map((r) => r.unregister()));
    if (window.caches) {
      const names = await window.caches.keys();
      await Promise.all(names.filter((n) => n.startsWith('fe-')).map((n) => window.caches.delete(n)));
    }
  } catch { /* нечего чистить */ }
}

function registerWorker() {
  if (!('serviceWorker' in navigator)) return;
  // В dev service worker не регистрируем (HMR + токен версии); включить: localStorage fe:pwa:dev=1.
  let dev = false;
  try { dev = import.meta.env.DEV && localStorage.getItem('fe:pwa:dev') !== '1'; } catch { /* noop */ }
  if (dev) return;
  const go = () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .then((reg) => reg.update().catch(() => {}))
      .catch(() => { /* CSP/сеть: приложение работает и без SW */ });
  };
  if (document.readyState === 'complete') go();
  else window.addEventListener('load', go, { once: true });
}

async function loadConfig() {
  try {
    const response = await fetch(CONFIG_URL, { cache: 'no-store', headers: { Accept: 'application/json' } });
    if (!response.ok) return null;
    const data = await response.json();
    return {
      sw_enabled: data.sw_enabled !== false,
      install_prompt_enabled: data.install_prompt_enabled === true,
    };
  } catch { return null; }
}

export function initPwa() {
  if (_initialized || typeof window === 'undefined') return;
  _initialized = true;
  // Витрины внутри чужих страниц и виджеты приложению не нужны.
  if (inIframe() || location.pathname.startsWith('/embed/')) return;

  _store.state = readState();
  _store.standalone = isStandalone();

  // Счёт заходов: одна новая сессия браузера = один заход.
  if (!sessionFlag(SESSION_KEY)) {
    writeState({
      ..._store.state,
      visits: (_store.state.visits || 0) + 1,
      firstSeen: _store.state.firstSeen || Date.now(),
    });
  }

  if (_store.standalone) {
    markInstalled();
    if (!sessionFlag(LAUNCH_KEY)) track(events.PWA_APP_LAUNCH, { platform: currentPlatform() });
  }

  const listen = (type, handler) => {
    window.addEventListener(type, handler);
    _teardown.push(() => window.removeEventListener(type, handler));
  };
  listen('beforeinstallprompt', (event) => {
    event.preventDefault(); // своё окно вместо мини-инфобара
    _store.deferredPrompt = event;
    emit();
  });
  listen('appinstalled', () => {
    _store.deferredPrompt = null;
    markInstalled();
    track(events.PWA_INSTALLED, { platform: currentPlatform() });
    emit();
  });
  // Chrome Android: приложение уже стоит (в т.ч. установлено в другой вкладке/ранее).
  try {
    window.navigator.getInstalledRelatedApps?.().then((apps) => {
      if (Array.isArray(apps) && apps.length > 0) markInstalled();
    }).catch(() => {});
  } catch { /* не поддерживается */ }

  // Режим «приложение» мог включиться без перезагрузки (установка из меню).
  try {
    window.matchMedia?.('(display-mode: standalone)').addEventListener?.('change', (e) => {
      if (e.matches) { _store.standalone = true; markInstalled(); }
    });
  } catch { /* старые браузеры */ }

  // Полезное действие считаем по существующим событиям трекинга, без правок мест вызова.
  listen('fe:track', (e) => {
    const name = e?.detail?.event;
    if (!name || !USEFUL_EVENTS.has(name)) return;
    const now = Date.now();
    _store.sessionUsefulAt = now;
    if (!_store.state.usefulAt) writeState({ ..._store.state, usefulAt: now });
    else emit();
  });

  loadConfig().then(async (config) => {
    _store.config = config;
    if (config && config.sw_enabled === false) await unregisterAll();
    else if (config) registerWorker(); // нет конфига (сеть/старый backend) — SW не трогаем, не ставим
    emit();
  });
}

// ── Подписка React на хранилище ──
function subscribe(fn) {
  _listeners.add(fn);
  return () => _listeners.delete(fn);
}
const getVersion = () => _version;

/** Снимок состояния; обновляется при любом изменении. */
export function usePwaStore() {
  useSyncExternalStore(subscribe, getVersion, getVersion);
  return _store;
}

export function setCardVisible(visible) {
  if (_store.cardVisible === visible) return;
  _store.cardVisible = visible;
  emit();
}

/** Для других плавающих подсказок: «не наезжай, пока висит окно установки». */
export function usePwaCardVisible() {
  return usePwaStore().cardVisible;
}

// ── Действия ──
export function dismissInstall(platform) {
  writeState(afterDismiss(_store.state, Date.now()));
  track(events.PWA_INSTALL_PROMPT_DISMISS, { platform, dismiss_count: _store.state.dismissCount });
}

export function acknowledgeIos() {
  writeState(afterIosAck(_store.state, Date.now()));
  track(events.PWA_INSTALL_PROMPT_ACCEPT, { platform: 'ios' });
}

/**
 * Показывает системное окно установки (Android). Событие одноразовое: после prompt()
 * оно больше не годится. outcome: 'accepted' | 'dismissed' | 'unavailable'.
 */
export async function promptNativeInstall({ fromCard = true } = {}) {
  const deferred = _store.deferredPrompt;
  if (!deferred) return 'unavailable';
  _store.deferredPrompt = null;
  emit();
  try {
    await deferred.prompt();
    const choice = await deferred.userChoice;
    if (choice?.outcome === 'accepted') {
      track(events.PWA_INSTALL_NATIVE_ACCEPTED, { platform: 'android' });
      return 'accepted'; // appinstalled придёт отдельно и запомнит установку
    }
    track(events.PWA_INSTALL_NATIVE_DISMISSED, { platform: 'android' });
    if (fromCard) writeState(afterDismiss(_store.state, Date.now()));
    return 'dismissed';
  } catch {
    return 'unavailable';
  }
}

/** Только для тестов. */
export function resetPwaForTests() {
  _initialized = false;
  while (_teardown.length) _teardown.pop()();
  _version = 0;
  _store.config = null;
  _store.deferredPrompt = null;
  _store.standalone = false;
  _store.sessionUsefulAt = 0;
  _store.cardVisible = false;
  _store.state = emptyState();
  try {
    localStorage.removeItem(STATE_KEY);
    sessionStorage.removeItem(SESSION_KEY);
    sessionStorage.removeItem(LAUNCH_KEY);
  } catch { /* noop */ }
}

export const __testing = { _store, writeState, readState, emit };
