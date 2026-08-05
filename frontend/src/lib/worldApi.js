// API-слой мирового блока (bounded context «Мировая экономика»).
// Отдельно от макро/регионов: своя ось (страна × индикатор × mode).
// Прогнозов нет — ни в API, ни в UI.
import { useQuery } from '@tanstack/react-query';
import api from './api';
import { formatValue } from './format';
import {
  WORLD_MOCK_COUNTRIES,
  WORLD_MOCK_COUNTRY,
  WORLD_MOCK_INDICATOR,
  getWorldMockData,
  getWorldMockSearch,
} from './worldMocks';

const STALE = 10 * 60 * 1000;
const GC = 30 * 60 * 1000;

/**
 * Фолбэк на фикстуры — ТОЛЬКО в dev, пока backend /world не подключён.
 * В проде выдуманные значения показывать нельзя ни при каких ошибках: это
 * misleading-данные на публичной витрине, а не удобство разработки.
 */
function shouldUseMock(err) {
  if (!import.meta.env.DEV) return false;
  const status = err?.response?.status;
  return status === 404 || status === 502 || status === 503 || status == null;
}

async function withMockFallback(request, mockFactory) {
  try {
    const { data } = await request();
    return { ...data, _fromMock: false };
  } catch (err) {
    if (shouldUseMock(err)) {
      const mock = mockFactory();
      if (mock != null) return { ...mock, _fromMock: true };
    }
    throw err;
  }
}

export function useWorldCountries() {
  return useQuery({
    queryKey: ['world-countries'],
    queryFn: ({ signal }) =>
      withMockFallback(
        () => api.get('/world/countries', { signal }),
        () => WORLD_MOCK_COUNTRIES,
      ),
    staleTime: STALE,
    gcTime: GC,
  });
}

export function useWorldCountry(slug) {
  return useQuery({
    queryKey: ['world-country', slug],
    queryFn: ({ signal }) =>
      withMockFallback(
        () => api.get(`/world/countries/${slug}`, { signal }),
        () => {
          const mock = WORLD_MOCK_COUNTRY[slug];
          if (!mock) {
            const err = new Error('Страна не найдена');
            err.response = { status: 404 };
            throw err;
          }
          return mock;
        },
      ),
    enabled: !!slug,
    staleTime: STALE,
    gcTime: GC,
    retry: (count, err) => {
      if (err?.response?.status === 404) return false;
      return count < 1;
    },
  });
}

export function useWorldIndicator(slug, code) {
  return useQuery({
    queryKey: ['world-indicator', slug, code],
    queryFn: ({ signal }) =>
      withMockFallback(
        () => api.get(`/world/indicators/${slug}/${code}`, { signal }),
        () => {
          const mock = WORLD_MOCK_INDICATOR[`${slug}/${code}`];
          if (!mock) {
            const err = new Error('Индикатор не найден');
            err.response = { status: 404 };
            throw err;
          }
          return mock;
        },
      ),
    enabled: !!slug && !!code,
    staleTime: STALE,
    gcTime: GC,
    retry: (count, err) => {
      if (err?.response?.status === 404) return false;
      return count < 1;
    },
  });
}

/**
 * Данные ряда. `requestCode` — primary или sibling (легаси-фолбэк);
 * `mode` — составной токен или легаси id (бэкенд принимает оба).
 */
export function useWorldIndicatorData(slug, code, mode, { from, to, requestCode } = {}) {
  const dataCode = requestCode || code;
  return useQuery({
    queryKey: ['world-indicator-data', slug, dataCode, mode, from, to],
    queryFn: ({ signal }) => {
      const params = {};
      if (mode) params.mode = mode;
      if (from) params.from = from;
      if (to) params.to = to;
      return withMockFallback(
        () => api.get(`/world/indicators/${slug}/${dataCode}/data`, { signal, params }),
        () => getWorldMockData(slug, dataCode, mode || 'level-monthly'),
      );
    },
    enabled: !!slug && !!dataCode && !!mode,
    staleTime: STALE,
    gcTime: GC,
  });
}

export function useWorldSearch(q, { country, limit = 50, enabled = true } = {}) {
  return useQuery({
    queryKey: ['world-search', q, country, limit],
    queryFn: ({ signal }) => {
      const params = { q, limit };
      if (country) params.country = country;
      return withMockFallback(
        () => api.get('/world/search', { signal, params }),
        () => getWorldMockSearch(q, country, limit),
      );
    },
    enabled: enabled && !!q && q.trim().length >= 1,
    staleTime: 60 * 1000,
    gcTime: GC,
  });
}

/**
 * Формат числа для витрины мира: русская запятая, неразрывный пробел.
 * Переиспользует formatValue из lib/format.js.
 */
export function formatWorldValue(value, digits) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  const abs = Math.abs(Number(value));
  let d = digits;
  if (d == null) {
    if (abs >= 10000) d = 0;
    else if (abs >= 100) d = 1;
    else d = abs < 1 ? 2 : 2;
  }
  return formatValue(value, d);
}

/** Русское склонение (копия логики regionsApi — без кросс-импорта домена). */
export function pluralRu(n, [one, few, many]) {
  const abs = Math.abs(n) % 100;
  const d = abs % 10;
  if (abs > 10 && abs < 20) return many;
  if (d === 1) return one;
  if (d >= 2 && d <= 4) return few;
  return many;
}

export function groupCountriesByRegion(countries) {
  const order = [];
  const map = new Map();
  for (const c of countries || []) {
    const region = c.region || 'Другие';
    if (!map.has(region)) {
      map.set(region, []);
      order.push(region);
    }
    map.get(region).push(c);
  }
  for (const list of map.values()) {
    list.sort((a, b) => a.name.localeCompare(b.name, 'ru'));
  }
  return order.map((region) => ({ region, countries: map.get(region) }));
}
