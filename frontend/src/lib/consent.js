/**
 * React-сторона consent-механизма (152-ФЗ, подразумеваемое согласие).
 *
 * Загрузкой трекеров управляет vanilla-bootstrap `public/consent.js`
 * (window.__feApplyConsent): по умолчанию трекеры грузятся сразу, явный отказ
 * текущей редакции уважается. Здесь — чтение/запись выбора пользователя и
 * событие повторного открытия баннера («Настройки cookie» в футере и на
 * странице политики). Ключ localStorage и CONSENT_VERSION обязаны совпадать
 * с public/consent.js (KEY / CURRENT_V).
 */

export const CONSENT_KEY = 'fe:consent:v1';
// Версия = дата действующей редакции политики конфиденциальности.
// При существенном изменении политики поднять дату — баннер покажется заново
// (см. isConsentCurrent). ОБЯЗАНА совпадать с CURRENT_V в public/consent.js.
export const CONSENT_VERSION = '2026-06-16';
export const CONSENT_OPEN_EVENT = 'fe:consent:open';

export function getConsent() {
  try {
    const raw = window.localStorage.getItem(CONSENT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function isConsentCurrent(record) {
  return Boolean(record && record.v === CONSENT_VERSION);
}

export function saveConsent({ analytics, ads }) {
  const record = {
    v: CONSENT_VERSION,
    ts: new Date().toISOString(),
    analytics: Boolean(analytics),
    ads: Boolean(ads),
  };
  try {
    window.localStorage.setItem(CONSENT_KEY, JSON.stringify(record));
  } catch {
    // Приватный режим: выбор применится на текущую сессию, но не сохранится.
  }
  if (typeof window.__feApplyConsent === 'function') {
    // explicit: выбор сделан кликом по баннеру — доверенный ввод человека,
    // рекламный гейт в public/consent.js открывается сразу.
    window.__feApplyConsent(record, { explicit: true });
  }
  return record;
}

export function openConsentSettings() {
  window.dispatchEvent(new Event(CONSENT_OPEN_EVENT));
}
