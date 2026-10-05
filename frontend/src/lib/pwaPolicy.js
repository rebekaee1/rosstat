// Чистая политика «когда звать установить приложение» (PWA, 2026-10-05).
// Никаких обращений к window/DOM — всё приходит аргументами, поэтому правила
// покрываются юнит-тестами. Хранилище и события — в lib/pwa.js.
//
// Цель владельца: «завлекать как можно дольше», но не навязчиво:
//   - не на первом визите и не сразу: после полезного действия или второго захода;
//   - «Не сейчас» откладывает показ с растущими интервалами 3 → 7 → 14 → 30 дней,
//     дальше раз в 30 дней без верхнего лимита числа показов;
//   - тем, кто установил приложение, не напоминаем никогда.
// Постоянного «Больше не показывать» нет сознательно: оно оборвало бы эту цель.
// Отказ уже сильно разрежает показы (раз в 30 дней), а полный контроль у
// человека остаётся: закрыть окно, пункт «Установить» в подвале никуда не лезет.

export const DAY_MS = 24 * 60 * 60 * 1000;
export const SNOOZE_DAYS = [3, 7, 14, 30];
export const REPEAT_DAYS = 30;
/** Не раньше стольких мс после загрузки страницы (даже на втором визите). */
export const MIN_PAGE_DWELL_MS = 15_000;
/** После полезного действия даём человеку дочитать/дослушать результат. */
export const AFTER_ACTION_DELAY_MS = 8_000;
/** Второй заход = новая сессия браузера не раньше чем через столько после первой. */
export const SECOND_VISIT_MIN_GAP_MS = 30 * 60 * 1000;

/** События трекинга, считающиеся «полезным действием» (человек получил ценность). */
export const USEFUL_EVENTS = new Set([
  'download_csv',
  'download_excel',
  'chart_image_download',
  'compare_image_download',
  'regions_map_gif_download',
  'forecast_toggle',
  'compare_add',
  'embed_code_copy',
  'calc_share',
  'calc_copy_result',
]);

/** Маршруты, где окно не показываем: виджеты, админка, вход/регистрация, кабинет. */
const HIDDEN_PREFIXES = ['/embed', '/admin', '/login', '/register', '/account'];

export function emptyState() {
  return {
    v: 1,
    installed: false,
    dismissCount: 0,
    nextAt: 0,
    visits: 0,
    firstSeen: 0,
    usefulAt: 0,
  };
}

export function snoozeDaysFor(dismissCount) {
  const n = Math.max(1, Math.floor(Number(dismissCount) || 1));
  return n <= SNOOZE_DAYS.length ? SNOOZE_DAYS[n - 1] : REPEAT_DAYS;
}

/** Состояние после «Не сейчас»: счётчик растёт, следующий показ — через интервал. */
export function afterDismiss(state, now) {
  const dismissCount = (state.dismissCount || 0) + 1;
  return { ...state, dismissCount, nextAt: now + snoozeDaysFor(dismissCount) * DAY_MS };
}

/** iOS «Понятно»: инструкцию видели, установку проверить нельзя — вернёмся через 30 дней. */
export function afterIosAck(state, now) {
  return { ...state, nextAt: now + REPEAT_DAYS * DAY_MS };
}

/**
 * Платформа по UA. 'android' | 'ios-safari' | 'ios-other' | 'desktop'.
 * iPadOS 13+ выдаёт себя за Mac: отличаем по тач-точкам.
 */
export function detectPlatform({ userAgent = '', maxTouchPoints = 0 } = {}) {
  const ua = String(userAgent);
  const ios = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && maxTouchPoints > 1);
  if (ios) {
    const inApp = /CriOS|FxiOS|EdgiOS|OPiOS|OPT\/|YaBrowser|GSA\/|FBAN|FBAV|Instagram|Line\/|MicroMessenger|Telegram|VKClient/.test(ua);
    return /Safari/.test(ua) && !inApp ? 'ios-safari' : 'ios-other';
  }
  if (/Android/.test(ua)) return 'android';
  return 'desktop';
}

export function isHiddenPath(pathname = '') {
  const p = String(pathname);
  return HIDDEN_PREFIXES.some((prefix) => p === prefix || p.startsWith(`${prefix}/`));
}

/**
 * Когда окно можно показать, мс (абсолютное время), либо null, если сейчас нельзя.
 * `trigger` — что открыло дверь: 'action' (полезное действие), 'visit' (второй заход) или null.
 */
export function eligibleAt({ state, now, pageLoadedAt, trigger }) {
  if (!trigger) return null;
  if (state.installed) return null;
  if (state.nextAt && now < state.nextAt) return null;
  const dwell = pageLoadedAt + MIN_PAGE_DWELL_MS;
  const afterAction = trigger === 'action' && state.usefulAt ? state.usefulAt + AFTER_ACTION_DELAY_MS : 0;
  return Math.max(dwell, afterAction, state.nextAt || 0);
}

/** Что открыло дверь на этой странице. */
export function triggerFor({ state, now, sessionUsefulAt }) {
  if (sessionUsefulAt || state.usefulAt) return 'action';
  if (state.visits >= 2 && state.firstSeen && now - state.firstSeen >= SECOND_VISIT_MIN_GAP_MS) return 'visit';
  return null;
}

/**
 * Итоговое решение «показать сейчас». Все внешние условия — аргументы.
 * `blocked` — на экране другое окно/баннер (согласие, модалка, нудж регистрации).
 */
export function shouldShowInstallCard({
  state, now, platform, hasNativePrompt, flagEnabled, standalone, inIframe,
  pathname, blocked, trigger, pageLoadedAt,
}) {
  if (!flagEnabled || standalone || inIframe || blocked) return false;
  if (isHiddenPath(pathname)) return false;
  if (platform === 'android' && !hasNativePrompt) return false; // без beforeinstallprompt кнопку не к чему привязать
  if (platform !== 'android' && platform !== 'ios-safari') return false;
  const at = eligibleAt({ state, now, pageLoadedAt, trigger });
  return at !== null && now >= at;
}
