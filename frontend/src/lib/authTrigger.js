/**
 * Контекст регистрации и входа для аналитики (круг 11, зона H).
 *
 * Помнит, ЧТО подтолкнуло человека к регистрации (упор в лимит, нудж, кнопка в шапке),
 * откуда он начал визит и сколько дней назад впервые пришёл, и собирает из этого
 * параметры событий `signup` / `login_success`. Только технические значения:
 * публичные коды, пути без query, числа. Ни почты, ни имени, ни текста форм.
 *
 * Модуль не импортирует `track`, чтобы `track.js` мог подключать его без цикла.
 * Всё в try/catch: аналитика не влияет на работу страницы.
 */

export const VISITOR_SINCE_KEY = 'fe:analytics:visitor_since';
const TRIGGER_KEY = 'fe:auth:trigger';
const LANDING_KEY = 'fe:analytics:landing';
const PENDING_KEY = 'fe:auth:pending';
// Подталкивающее событие считается актуальным 45 минут (как на сервере).
const TRIGGER_TTL_MS = 45 * 60 * 1000;
// Флаг «вернулись с провайдера» живёт короче: редирект туда и обратно занимает минуты.
const PENDING_TTL_MS = 30 * 60 * 1000;

export const TRIGGER_BY_EVENT = {
  download_limit: 'gate_download',
  chart_image_blocked: 'gate_chart_image',
  compare_image_blocked: 'gate_compare',
  compare_limit_hit: 'gate_compare',
  regions_map_gif_blocked: 'gate_gif',
  register_nudge_cta: 'nudge',
  header_register_click: 'header',
};

function readJson(storage, key) {
  try {
    const raw = storage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/** Запоминает «что подтолкнуло», если событие из списка упоров и кнопок регистрации. */
export function rememberAuthTrigger(eventName) {
  const value = TRIGGER_BY_EVENT[eventName];
  if (!value || typeof window === 'undefined') return;
  try {
    window.sessionStorage.setItem(TRIGGER_KEY, JSON.stringify({ value, ts: Date.now() }));
  } catch { /* не критично */ }
}

/** Что подтолкнуло к регистрации; 'direct', если ничего не запомнено или прошло больше 45 минут. */
export function peekAuthTrigger() {
  if (typeof window === 'undefined') return 'direct';
  const record = readJson(window.sessionStorage, TRIGGER_KEY);
  if (!record || !record.value || Date.now() - Number(record.ts || 0) > TRIGGER_TTL_MS) return 'direct';
  return record.value;
}

export function clearAuthTrigger() {
  try { window.sessionStorage.removeItem(TRIGGER_KEY); } catch { /* не критично */ }
}

/** Первая страница визита (путь без query): запоминается один раз за вкладку. */
export function rememberLanding() {
  if (typeof window === 'undefined') return;
  try {
    if (!window.sessionStorage.getItem(LANDING_KEY)) {
      window.sessionStorage.setItem(LANDING_KEY, String(window.location.pathname || '/').slice(0, 200));
    }
  } catch { /* не критично */ }
}

export function landingPath() {
  try {
    return window.sessionStorage.getItem(LANDING_KEY) || null;
  } catch {
    return null;
  }
}

/** Язык сайта, на котором сейчас человек (атрибут lang страницы). */
export function siteLocale() {
  try {
    const lang = String(document.documentElement.lang || '').slice(0, 2).toLowerCase();
    return lang === 'en' || lang === 'ru' ? lang : null;
  } catch {
    return null;
  }
}

/** Сколько полных дней назад посетитель пришёл впервые; null, если метки нет (старый посетитель). */
export function firstVisitDays(now = Date.now()) {
  try {
    const since = Number(window.localStorage.getItem(VISITOR_SINCE_KEY));
    if (!Number.isFinite(since) || since <= 0) return null;
    return Math.max(0, Math.floor((now - since) / 86400000));
  } catch {
    return null;
  }
}

function compact(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== null && v !== undefined));
}

/** Параметры события `signup`. */
export function signupParams(method, { newsletter } = {}) {
  return compact({
    method,
    newsletter: newsletter === undefined ? undefined : (newsletter ? 1 : 0),
    site_locale: siteLocale(),
    trigger: peekAuthTrigger(),
    landing: landingPath(),
    first_visit_days: firstVisitDays(),
  });
}

/** Параметры события `login_success`. */
export function loginParams(method) {
  return compact({ method, site_locale: siteLocale() });
}

/** Код ошибки формы по HTTP-статусу (без текста сообщения). */
export function authErrorCode(err) {
  const status = err?.response?.status;
  if (!err?.response) return 'network';
  if (status === 401) return 'credentials';
  if (status === 409) return 'exists';
  if (status === 422) return 'invalid';
  if (status === 423) return 'locked';
  if (status === 403) return 'unavailable';
  return status ? `http_${status}` : 'unknown';
}

/** Поле формы, на которое указывает ошибка (по структуре ответа, не по тексту): email / password / consent / null. */
export function authErrorField(err) {
  const detail = err?.response?.data?.detail;
  if (Array.isArray(detail)) {
    const loc = detail[0]?.loc;
    const last = Array.isArray(loc) ? loc[loc.length - 1] : null;
    if (last === 'email' || last === 'password') return last;
  }
  const status = err?.response?.status;
  if (status === 409) return 'email';
  if (status === 401) return 'password';
  if (status === 422) return 'consent';
  return null;
}

/** Перед полным редиректом на провайдера: после возврата AuthProvider отправит signup/login_success. */
export function markOAuthPending(provider, intent, { newsletter } = {}) {
  try {
    window.sessionStorage.setItem(PENDING_KEY, JSON.stringify({
      provider, intent, newsletter: Boolean(newsletter), ts: Date.now(),
    }));
  } catch { /* не критично */ }
}

/** Забирает флаг возврата один раз. Возвращает { provider, intent, newsletter } или null. */
export function consumeOAuthPending() {
  if (typeof window === 'undefined') return null;
  const record = readJson(window.sessionStorage, PENDING_KEY);
  try { window.sessionStorage.removeItem(PENDING_KEY); } catch { /* не критично */ }
  if (!record || !record.provider || Date.now() - Number(record.ts || 0) > PENDING_TTL_MS) return null;
  return { provider: record.provider, intent: record.intent || 'login', newsletter: Boolean(record.newsletter) };
}

/** Разбор ?error= при возврате с провайдера: возвращает код ошибки или null. */
export function oauthReturnError(search) {
  try {
    const code = new URLSearchParams(search || '').get('error');
    return code && /^[a-z0-9_]{1,40}$/.test(code) ? code : null;
  } catch {
    return null;
  }
}
