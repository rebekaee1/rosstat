/**
 * Когда показывать приглашение зарегистрироваться (волна 6, 15.3 и 14.8).
 *
 * Принципы: не просить регистрацию раньше, чем человек получил пользу; не показывать там, где
 * скачивать нечего (информационные страницы, главная, календарь); не вешать плашку на каждую страницу.
 *  - «Действие» = переход на другую страницу внутри сайта за эту сессию (первый вход не считается).
 *    Приглашение появляется после второго действия.
 *  - Первая попытка скачать (сервер ответил «скачивание после регистрации») показывает приглашение сразу.
 *  - Только на страницах, где есть что скачать (показатель, рейтинг, сравнение, региональный показатель).
 */

export const NUDGE_ACTIONS_KEY = 'fe_nudge_actions';
export const NUDGE_DOWNLOAD_KEY = 'fe_nudge_download';
export const NUDGE_MIN_ACTIONS = 2;

// Страницы, где пользователь может что-то скачать: показатель (любой раздел), рейтинг стран и регионов,
// сравнение, региональный показатель, «Россия сегодня» по показателю.
const DOWNLOADABLE = [
  /\/indicator\/[^/]+/,
  /^\/world\/rating(\/|$)/,
  /^\/russia\/region-rating\/[^/]+/,
  /^\/russia\/region\/[^/]+\/[^/]+/,
  /^\/[^/]+\/region\/[^/]+\/[^/]+/,
  /^\/russia\/today\/[^/]+/,
  /^\/compare(\/|$)/,
];

export function isDownloadablePath(pathname) {
  const path = String(pathname || '');
  return DOWNLOADABLE.some((re) => re.test(path));
}

function read(storage, key) {
  try { return storage.getItem(key); } catch { return null; }
}

function write(storage, key, value) {
  try { storage.setItem(key, value); } catch { /* приватный режим: счётчик живёт только в памяти вкладки */ }
}

/** Сколько переходов между страницами сделано в этой сессии. */
export function readActions() {
  if (typeof sessionStorage === 'undefined') return 0;
  const n = Number(read(sessionStorage, NUDGE_ACTIONS_KEY));
  return Number.isFinite(n) && n > 0 ? n : 0;
}

export function writeActions(count) {
  if (typeof sessionStorage === 'undefined') return;
  write(sessionStorage, NUDGE_ACTIONS_KEY, String(Math.max(0, Number(count) || 0)));
}

export function markDownloadAttempt() {
  if (typeof sessionStorage !== 'undefined') write(sessionStorage, NUDGE_DOWNLOAD_KEY, '1');
}

export function hasDownloadAttempt() {
  return typeof sessionStorage !== 'undefined' && read(sessionStorage, NUDGE_DOWNLOAD_KEY) === '1';
}

/** Решение «показывать ли приглашение»: чистая функция, чтобы проверять тестом. */
export function shouldOfferNudge({ actions = 0, downloadAttempted = false, pathname = '/', requireDownloadable = true }) {
  if (requireDownloadable && !isDownloadablePath(pathname)) return false;
  return downloadAttempted || actions >= NUDGE_MIN_ACTIONS;
}
