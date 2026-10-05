// «Фальшивая дверь» платного API (замер спроса, 2026-10-05).
//
// Точки входа («API и выгрузка с прогнозом» на странице показателя и в окне
// лимита скачиваний) показываются только когда бэкенд сообщил api_interest_enabled
// (GET /api/v1/api-interest/config — тот же канал, что у /analytics/replay/config).
// Флаг переключается переменной окружения backend без пересборки фронта; по
// умолчанию он выключен, поэтому выкладка кода опрос не включает.
//
// Клик открывает глобальное окно ApiInterestModal через window-событие (как
// 'fe:download-limit'). Аналитика (lib/track.js) несёт только use_case/source/
// indicator_code — почта в события не попадает никогда.
import { useEffect, useState } from 'react';
import { track, events } from './track';

export const API_INTEREST_EVENT = 'fe:api-interest';
export const API_INTEREST_SOURCES = ['indicator', 'limit_modal'];
// Ключи — контракт с backend (app.services.alerting.API_INTEREST_USE_CASES).
export const API_INTEREST_USE_CASES = [
  'analytics_treasury',
  'planning_contracts',
  'consulting',
  'research',
  'study',
  'journalism',
  'other',
];

const CONFIG_URL = '/api/v1/api-interest/config';

let _enabled = null; // null — ещё не знаем
let _inflight = null;
const _viewSeen = new Set(); // запасной вариант, если sessionStorage недоступен

/** Однократная (на загрузку страницы) загрузка флага; ошибка = выключено. */
export function loadApiInterestEnabled() {
  if (_enabled !== null) return Promise.resolve(_enabled);
  if (!_inflight) {
    _inflight = (async () => {
      try {
        const response = await fetch(CONFIG_URL, { headers: { Accept: 'application/json' } });
        _enabled = response.ok ? (await response.json()).enabled === true : false;
      } catch {
        _enabled = false;
      }
      return _enabled;
    })();
  }
  return _inflight;
}

/** Только для тестов. */
export function resetApiInterestForTests() {
  _enabled = null;
  _inflight = null;
  _viewSeen.clear();
  try {
    Object.keys(window.sessionStorage)
      .filter((k) => k.startsWith('fe:api-interest:'))
      .forEach((k) => window.sessionStorage.removeItem(k));
  } catch { /* нет sessionStorage */ }
}

export function useApiInterestEnabled() {
  const [enabled, setEnabled] = useState(_enabled === true);
  useEffect(() => {
    let alive = true;
    loadApiInterestEnabled().then((value) => { if (alive) setEnabled(value); });
    return () => { alive = false; };
  }, []);
  return enabled;
}

/** Показ точки входа — не чаще 1 раза за сессию на точку входа. */
export function trackApiInterestView(source) {
  const key = `fe:api-interest:view:${source}`;
  if (_viewSeen.has(key)) return false;
  _viewSeen.add(key);
  try {
    if (window.sessionStorage.getItem(key)) return false;
    window.sessionStorage.setItem(key, '1');
  } catch { /* приватный режим: хватит памяти страницы */ }
  track(events.API_INTEREST_VIEW, { source });
  return true;
}

/** Клик по точке входа: фиксируем намерение и открываем окно заявки. */
export function openApiInterest({ source = 'indicator', indicatorCode = null } = {}) {
  const safeSource = API_INTEREST_SOURCES.includes(source) ? source : 'indicator';
  track(events.API_INTEREST_CLICK, { source: safeSource, indicator_code: indicatorCode || null });
  window.dispatchEvent(new CustomEvent(API_INTEREST_EVENT, {
    detail: { source: safeSource, indicatorCode: indicatorCode || null },
  }));
}
