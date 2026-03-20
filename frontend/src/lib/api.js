import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

export const fetchIndicators = (params = {}) => {
  const { category, includeInactive } = params;
  const search = new URLSearchParams();
  if (category) search.set('category', category);
  if (includeInactive) search.set('include_inactive', 'true');
  const q = search.toString();
  return api.get(`/indicators${q ? `?${q}` : ''}`).then((r) => r.data);
};

export const fetchIndicator = (code) =>
  api.get(`/indicators/${code}`).then(r => r.data);

export const fetchIndicatorData = (code, params = {}) =>
  api.get(`/indicators/${code}/data`, { params }).then(r => r.data);

export const fetchIndicatorStats = (code) =>
  api.get(`/indicators/${code}/stats`).then(r => r.data);

export const fetchForecast = (code) =>
  api.get(`/indicators/${code}/forecast`).then(r => r.data);

export const fetchInflation = (code) =>
  api.get(`/indicators/${code}/inflation`).then(r => r.data);

export const fetchSystemStatus = () =>
  api.get('/system/status').then(r => r.data);

export default api;
