import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

const RETRY_LIMIT = 3;

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const { config, response } = error;
    if (!response || !config) return Promise.reject(error);
    config.__retryCount = config.__retryCount || 0;
    if ((response.status === 429 || response.status === 503) && config.__retryCount < RETRY_LIMIT) {
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
  const { category, includeInactive } = params;
  const search = new URLSearchParams();
  if (category) search.set('category', category);
  if (includeInactive) search.set('include_inactive', 'true');
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

export default api;
