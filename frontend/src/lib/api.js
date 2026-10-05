import axios from 'axios';
import { LOCALE_HEADER, currentUiLocale } from '../i18n/locale';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
  // Сессионная кука fe_sess летит на same-origin запросы (личный кабинет).
  withCredentials: true,
});

/*
 * Политика повторов (F11, 2026-10-04).
 *
 * Автоматически повторяется только то, что безопасно выполнить дважды:
 *   - GET/HEAD (чтение) — при обрыве сети/таймауте и при 429/503;
 *   - изменяющий запрос (POST/PUT/PATCH/DELETE) — только если вызывающий явно
 *     объявил его идемпотентным: `{ idempotent: true }` в конфиге или заголовок
 *     `Idempotency-Key` (сервер должен дедуплицировать по ключу).
 * Регистрация, обратная связь, выгрузка, подписка и прочие изменяющие операции
 * по умолчанию НЕ повторяются: после 429/503/обрыва неизвестно, выполнил ли их
 * сервер, и повтор может задвоить действие. Ошибка уходит вызывающему коду.
 * Эндпоинты `/auth*` не повторяются никогда (креды, лимиты входа).
 *
 * Параметры: не более RETRY_LIMIT повторов; заголовок Retry-After (секунды или
 * HTTP-date) соблюдается как минимальная пауза, а если сервер просит ждать
 * дольше RETRY_AFTER_MAX_MS — повтор не делается (UI не блокируем минутами);
 * без заголовка — экспоненциальная пауза с небольшим jitter.
 * Отмена запроса (AbortController) в повторы не попадает.
 */
const RETRY_LIMIT = 3;
const RETRY_AFTER_MAX_MS = 10000;
const RETRY_BASE_MS = 500;
const RETRYABLE_STATUS = new Set([429, 503]);
const SAFE_METHODS = new Set(['get', 'head']);
const MUTATING = new Set(['post', 'put', 'patch', 'delete']);

function hasIdempotencyKey(headers) {
  if (!headers) return false;
  if (typeof headers.has === 'function') return Boolean(headers.has('Idempotency-Key'));
  return Object.keys(headers).some((k) => k.toLowerCase() === 'idempotency-key' && headers[k]);
}

/** Можно ли выполнить этот запрос повторно без риска задвоить эффект. */
export function isRetrySafe(config) {
  if (!config) return false;
  const method = (config.method || 'get').toLowerCase();
  if (SAFE_METHODS.has(method)) return true;
  return config.idempotent === true || hasIdempotencyKey(config.headers);
}

/** Retry-After → миллисекунды (секунды или HTTP-date); null — заголовка нет/не разобран. */
export function parseRetryAfter(headers, now = Date.now()) {
  let raw;
  try {
    raw = typeof headers?.get === 'function' ? headers.get('retry-after') : headers?.['retry-after'] ?? headers?.['Retry-After'];
  } catch { return null; }
  if (raw == null || raw === '') return null;
  const value = String(raw).trim();
  if (/^\d+(?:\.\d+)?$/.test(value)) return Number(value) * 1000;
  const when = Date.parse(value);
  return Number.isFinite(when) ? Math.max(0, when - now) : null;
}

function backoffMs(attempt) {
  return RETRY_BASE_MS * 2 ** (attempt - 1) + Math.floor(Math.random() * 250);
}

function readCookie(name) {
  const m = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)'));
  return m ? decodeURIComponent(m[1]) : null;
}

// Locale for public_indicator_fields (EN overlay) + CSRF on mutations.
api.interceptors.request.use((config) => {
  config.headers = config.headers || {};
  if (!config.headers[LOCALE_HEADER]) {
    config.headers[LOCALE_HEADER] = currentUiLocale();
  }
  if (MUTATING.has((config.method || '').toLowerCase())) {
    const token = readCookie('XSRF-TOKEN');
    if (token) {
      config.headers['X-XSRF-TOKEN'] = token;
    }
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const { config, response } = error;
    // A replaced query is finished: cancellation must not enter transient retries.
    if (axios.isCancel(error) || error.code === 'ERR_CANCELED' || config?.signal?.aborted) {
      return Promise.reject(error);
    }
    if (!config) return Promise.reject(error);
    // Политика — в комментарии выше: auth и небезопасные для повтора запросы не ретраим.
    const isAuth = (config.url || '').startsWith('/auth');
    config.__retryCount = config.__retryCount || 0;
    if (isAuth || !isRetrySafe(config) || config.__retryCount >= RETRY_LIMIT) {
      return Promise.reject(error);
    }

    // Сеть / Empty reply / рестарт backend / таймаут.
    if (!response) {
      config.__retryCount += 1;
      await new Promise((r) => setTimeout(r, backoffMs(config.__retryCount)));
      return api(config);
    }

    if (RETRYABLE_STATUS.has(response.status)) {
      const retryAfter = parseRetryAfter(response.headers);
      if (retryAfter != null && retryAfter > RETRY_AFTER_MAX_MS) return Promise.reject(error);
      config.__retryCount += 1;
      const delay = Math.max(backoffMs(config.__retryCount), retryAfter ?? 0);
      await new Promise((r) => setTimeout(r, delay));
      return api(config);
    }
    return Promise.reject(error);
  },
);

export const fetchIndicators = (params = {}, { signal } = {}) => {
  const { category, includeInactive, includeUnlisted } = params;
  const search = new URLSearchParams();
  if (category) search.set('category', category);
  if (includeInactive) search.set('include_inactive', 'true');
  if (includeUnlisted) search.set('include_unlisted', 'true');
  const q = search.toString();
  return api.get(`/indicators${q ? `?${q}` : ''}`, { signal }).then((r) => r.data);
};

/**
 * Глобальный поиск по мировым индикаторам (все страны).
 * Backend: GET /api/v1/world/search — listed + ненулевой сигнал.
 */
export const fetchWorldSearch = (q, { country, limit = 50 } = {}, { signal } = {}) => {
  const params = { q, limit };
  if (country) params.country = country;
  return api.get('/world/search', { signal, params }).then((r) => r.data);
};

/** Алиас для списка индикаторов по категории (план Фазы 1). */
export const fetchIndicatorsByCategory = (category, opts = {}) =>
  fetchIndicators({ category, ...opts });

export const fetchIndicator = (code, { signal } = {}) =>
  api.get(`/indicators/${code}`, { signal }).then((r) => r.data);

export const fetchIndicatorData = (code, params = {}, { signal } = {}) =>
  api.get(`/indicators/${code}/data`, { params, signal }).then((r) => r.data);

export const fetchIndicatorStats = (code, { signal } = {}) =>
  api.get(`/indicators/${code}/stats`, { signal }).then((r) => r.data);

export const fetchForecast = (code, { signal } = {}) =>
  api.get(`/indicators/${code}/forecast`, { signal }).then((r) => r.data);

export const fetchInflation = (code, { signal } = {}) =>
  api.get(`/indicators/${code}/inflation`, { signal }).then((r) => r.data);

export const fetchSystemStatus = ({ signal } = {}) =>
  api.get('/system/status', { signal }).then((r) => r.data);

export const fetchCalendarEvents = (params = {}, { signal } = {}) => {
  const search = new URLSearchParams();
  if (params.from) search.set('from', params.from);
  if (params.to) search.set('to', params.to);
  if (params.source) search.set('source', params.source);
  if (params.importance) search.set('importance', params.importance);
  if (params.event_type) search.set('event_type', params.event_type);
  if (params.limit) search.set('limit', String(params.limit));
  if (params.offset) search.set('offset', String(params.offset));
  const q = search.toString();
  return api.get(`/calendar${q ? `?${q}` : ''}`, { signal }).then((r) => r.data);
};

export const fetchCalendarUpcoming = (params = {}, { signal } = {}) => {
  const search = new URLSearchParams();
  if (params.limit) search.set('limit', String(params.limit));
  if (params.importance_min) search.set('importance_min', String(params.importance_min));
  const q = search.toString();
  return api.get(`/calendar/upcoming${q ? `?${q}` : ''}`, { signal }).then((r) => r.data);
};

export const fetchCoverage = ({ signal } = {}) =>
  api.get('/dashboard/coverage', { signal }).then((r) => r.data);

export const fetchDashboardSparklines = ({ signal } = {}) =>
  api.get('/dashboard/sparklines', { signal }).then((r) => r.data);

export const fetchDemographicsStructure = ({ signal } = {}) =>
  api.get('/demographics/structure', { signal }).then((r) => r.data);

// --- Личный кабинет (ADR-0007) ---
export const fetchMe = ({ signal } = {}) =>
  api.get('/auth/me', { signal }).then((r) => r.data.user);

export const registerUser = (payload) =>
  api.post('/auth/register', payload).then((r) => r.data.user);

export const loginUser = (payload) =>
  api.post('/auth/login', payload).then((r) => r.data.user);

export const logoutUser = () => api.post('/auth/logout').then((r) => r.data);

export const logoutAll = () => api.post('/auth/logout-all').then((r) => r.data);

export const setPassword = (payload) =>
  api.post('/auth/set-password', payload).then((r) => r.data);

export const unlinkIdentity = (id) =>
  api.delete(`/auth/identities/${id}`).then((r) => r.data);

export const deleteAccount = () => api.delete('/auth/account').then((r) => r.data);

export const submitFeedback = (payload) =>
  api.post('/auth/feedback', payload).then((r) => r.data);

/**
 * Заявка «API и выгрузка с прогнозом» (замер спроса). Открыта и гостям; почта
 * уходит только на этот эндпоинт — в аналитические события не попадает.
 */
export const submitApiInterest = (payload) =>
  api.post('/api-interest', payload).then((r) => r.data);

/** Подписка/отписка на информационную рассылку из кабинета. */
export const updateNewsletter = (subscribe) =>
  api.post('/auth/account/newsletter', { subscribe }).then((r) => r.data.user);

export const updateProfile = (displayName) =>
  api.patch('/auth/account/profile', { display_name: displayName }).then((r) => r.data.user);

/** Остаток гостевых выгрузок для состояния кнопок (без инкремента). */
export const fetchDownloadQuota = ({ signal } = {}) =>
  api.get('/export/quota', { signal }).then((r) => r.data);

/**
 * Post-OAuth return URL. Callback живёт на apex, поэтому относительный
 * `/account` оставлял бы пользователя на EN-хосте после входа с ``ru.``.
 * Передаём абсолютный same-origin next с хоста старта.
 */
export function absoluteAuthNext(next = '/account') {
  let path = typeof next === 'string' ? next.trim() : '/account';
  if (!path || path.startsWith('//') || (path.startsWith('/') === false && !/^https?:\/\//i.test(path))) {
    path = '/account';
  }
  if (/^https?:\/\//i.test(path)) return path;
  if (!path.startsWith('/') || path.startsWith('//')) path = '/account';
  if (typeof window !== 'undefined' && window.location?.origin) {
    return `${String(window.location.origin).replace(/\/$/, '')}${path}`;
  }
  return path;
}

// OAuth — полностраничный редирект на backend start-эндпоинт.
// newsletter=1 фиксирует согласие на рассылку (из всплывающего окна перед входом).
export const oauthStartUrl = (provider, { intent = 'login', next = '/account', newsletter = false, consent = false } = {}) => {
  const qs = new URLSearchParams({ intent, next: absoluteAuthNext(next) });
  if (newsletter) qs.set('newsletter', '1');
  if (consent) qs.set('consent', '1');
  return `/api/v1/auth/oauth/${provider}/start?${qs.toString()}`;
};

/** Включённые OAuth-провайдеры (фронт скрывает несконфигурированные кнопки). */
export const fetchOAuthProviders = ({ signal } = {}) =>
  api.get('/auth/oauth/providers', { signal }).then((r) => r.data.providers || []);

/**
 * Серверная выгрузка таблицы (Excel/CSV) с гейтом лимита.
 * Возвращает Blob; при 403 download_limit бросает ошибку с code='download_limit'.
 */
export const exportTable = async ({ format, filename, valueLabel, points, meta }) => {
  try {
    const res = await api.post(
      '/export/table',
      { format, filename, value_label: valueLabel, points, meta },
      { responseType: 'blob' },
    );
    const raw = res.headers?.['x-download-remaining'];
    const remaining = raw == null || raw === '' ? null : Number(raw);
    return { blob: res.data, remaining };
  } catch (err) {
    // Тело ошибки приходит как Blob (responseType=blob) — распарсим JSON.
    const blob = err?.response?.data;
    if (err?.response?.status === 403 && blob) {
      try {
        const text = await blob.text();
        const parsed = JSON.parse(text);
        const detail = parsed?.detail || parsed;
        const e = new Error(detail?.message || 'download_limit');
        e.code = detail?.code || 'download_limit';
        throw e;
      } catch (parseErr) {
        if (parseErr.code) throw parseErr;
      }
    }
    throw err;
  }
};

export default api;
