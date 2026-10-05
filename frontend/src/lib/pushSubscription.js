// Подписка на web-push — ПОДГОТОВКА (2026-10-05). НИГДЕ НЕ ПОДКЛЮЧЕНА И НЕ ВЫЗЫВАЕТСЯ.
//
// Правила, которые держит этот модуль (и тест pushSubscription.test.js):
//   - Ничего не происходит при импорте и ничего не вызывается автоматически: ни запрос
//     разрешения, ни подписка, ни сетевой вызов. Функции — только для будущей кнопки,
//     которую человек нажмёт сам.
//   - subscribeToPush() без { confirmedByUser: true } бросает ошибку ДО любого обращения к
//     Notification/pushManager; браузерный запрос разрешения показывается только после такого
//     явного подтверждения и только если сервер включил подписку (push_enabled в
//     /api/v1/pwa/config — по умолчанию выключено).
//   - Адрес подписки — персональные данные: уходит одним POST на /api/v1/push/subscribe,
//     не логируется и не попадает в аналитические события.
import api from './api';

export class PushNotConfirmedError extends Error {
  constructor() { super('Push subscription requires an explicit user action (confirmedByUser: true)'); this.name = 'PushNotConfirmedError'; }
}
export class PushUnavailableError extends Error {
  constructor(reason) { super(`Push is unavailable: ${reason}`); this.name = 'PushUnavailableError'; this.reason = reason; }
}

export function isPushSupported() {
  return typeof window !== 'undefined'
    && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
}

/** Только чтение состояния: никогда не показывает запрос разрешения. */
export async function getPushState() {
  if (!isPushSupported()) return { supported: false, permission: 'unsupported', subscribed: false };
  let subscribed = false;
  try {
    const registration = await navigator.serviceWorker.getRegistration();
    subscribed = Boolean(registration && await registration.pushManager.getSubscription());
  } catch { /* нет регистрации */ }
  return { supported: true, permission: Notification.permission, subscribed };
}

function urlBase64ToUint8Array(value) {
  const padding = '='.repeat((4 - (value.length % 4)) % 4);
  const raw = atob((value + padding).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(raw, (ch) => ch.charCodeAt(0));
}

async function readServerConfig() {
  const response = await fetch('/api/v1/pwa/config', { cache: 'no-store', headers: { Accept: 'application/json' } });
  if (!response.ok) throw new PushUnavailableError('config');
  return response.json();
}

/**
 * Подписаться. ТОЛЬКО по явному действию пользователя: { confirmedByUser: true }.
 * Порядок строго такой: подтверждение → флаг сервера → поддержка браузера → разрешение → подписка.
 */
export async function subscribeToPush({ confirmedByUser } = {}) {
  if (confirmedByUser !== true) throw new PushNotConfirmedError();
  const config = await readServerConfig();
  if (!config.push_enabled || !config.vapid_public_key) throw new PushUnavailableError('disabled');
  if (!isPushSupported()) throw new PushUnavailableError('unsupported');
  if (Notification.permission === 'denied') throw new PushUnavailableError('denied');
  const permission = Notification.permission === 'granted' ? 'granted' : await Notification.requestPermission();
  if (permission !== 'granted') throw new PushUnavailableError('denied');
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(config.vapid_public_key),
  });
  await api.post('/push/subscribe', subscription.toJSON());
  return true;
}

/** Отписаться: снимает подписку в браузере и удаляет строку на сервере. */
export async function unsubscribeFromPush() {
  if (!isPushSupported()) return false;
  const registration = await navigator.serviceWorker.getRegistration();
  const subscription = registration ? await registration.pushManager.getSubscription() : null;
  if (!subscription) return false;
  const { endpoint } = subscription.toJSON();
  await subscription.unsubscribe();
  try { await api.post('/push/unsubscribe', { endpoint }); } catch { /* строка могла уже исчезнуть */ }
  return true;
}
