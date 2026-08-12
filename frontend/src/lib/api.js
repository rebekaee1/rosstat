import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
  // Сессионная кука fe_sess летит на same-origin запросы (личный кабинет).
  withCredentials: true,
});

const RETRY_LIMIT = 3;
const MUTATING = new Set(['post', 'put', 'patch', 'delete']);

function readCookie(name) {
  const m = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)'));
  return m ? decodeURIComponent(m[1]) : null;
}

// Double-submit CSRF: кладём X-XSRF-TOKEN из cookie на мутирующие запросы.
api.interceptors.request.use((config) => {
  if (MUTATING.has((config.method || '').toLowerCase())) {
    const token = readCookie('XSRF-TOKEN');
    if (token) {
      config.headers = config.headers || {};
      config.headers['X-XSRF-TOKEN'] = token;
    }
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const { config, response } = error;
    if (!config) return Promise.reject(error);
    // Не ретраим auth-эндпоинты: иначе при 429 повторно зашлём креды/мутации.
    const isAuth = (config.url || '').startsWith('/auth');
    const method = (config.method || 'get').toLowerCase();
    config.__retryCount = config.__retryCount || 0;

    // Сеть / Empty reply / рестарт backend — ретрай только безопасных GET.
    const networkMiss = !response && method === 'get' && !isAuth
      && config.__retryCount < RETRY_LIMIT;
    if (networkMiss) {
      config.__retryCount += 1;
      await new Promise((r) => setTimeout(r, 2 ** config.__retryCount * 250));
      return api(config);
    }

    if (!response) return Promise.reject(error);

    if (!isAuth && (response.status === 429 || response.status === 503) && config.__retryCount < RETRY_LIMIT) {
      config.__retryCount += 1;
      const retryAfter = parseInt(response.headers['retry-after'] || '1', 10);
      const delay = Math.min(retryAfter * 1000, 2 ** config.__retryCount * 1000);
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

/** Подписка/отписка на информационную рассылку из кабинета. */
export const updateNewsletter = (subscribe) =>
  api.post('/auth/account/newsletter', { subscribe }).then((r) => r.data.user);

export const updateProfile = (displayName) =>
  api.patch('/auth/account/profile', { display_name: displayName }).then((r) => r.data.user);

/** Остаток гостевых выгрузок для состояния кнопок (без инкремента). */
export const fetchDownloadQuota = ({ signal } = {}) =>
  api.get('/export/quota', { signal }).then((r) => r.data);

// OAuth — полностраничный редирект на backend start-эндпоинт.
// newsletter=1 фиксирует согласие на рассылку (из всплывающего окна перед входом).
export const oauthStartUrl = (provider, { intent = 'login', next = '/account', newsletter = false } = {}) => {
  const qs = new URLSearchParams({ intent, next });
  if (newsletter) qs.set('newsletter', '1');
  return `/api/v1/auth/oauth/${provider}/start?${qs.toString()}`;
};

/** Включённые OAuth-провайдеры (фронт скрывает несконфигурированные кнопки). */
export const fetchOAuthProviders = ({ signal } = {}) =>
  api.get('/auth/oauth/providers', { signal }).then((r) => r.data.providers || []);

/**
 * Серверная выгрузка таблицы (Excel/CSV) с гейтом лимита.
 * Возвращает Blob; при 403 download_limit бросает ошибку с code='download_limit'.
 */
export const exportTable = async ({ format, filename, valueLabel, points }) => {
  try {
    const res = await api.post(
      '/export/table',
      { format, filename, value_label: valueLabel, points },
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
        const e = new Error(detail?.message || 'Лимит выгрузок исчерпан');
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
