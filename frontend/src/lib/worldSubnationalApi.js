// API субнациональных регионов (штаты / земли / провинции).
import { useQuery } from '@tanstack/react-query';
import api from './api';
import { currentUiLocale } from '../i18n/locale';
import { formatValue } from './format';

const STALE = 10 * 60 * 1000;

function localeKey() {
  return currentUiLocale();
}

export function formatSubnationalValue(value, locale) {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  return formatValue(Number(value), undefined, locale);
}

export function useWorldRegionsHub(countrySlug) {
  return useQuery({
    queryKey: ['world-subnational-hub', countrySlug, localeKey()],
    queryFn: async () => (await api.get(`/world/${countrySlug}/regions`)).data,
    enabled: Boolean(countrySlug),
    staleTime: STALE,
    retry: (count, err) => {
      const status = err?.response?.status;
      if (status && status >= 400 && status < 500 && status !== 429) return false;
      return count < 1;
    },
  });
}

export function useWorldRegionsMap(countrySlug, code, period) {
  return useQuery({
    queryKey: ['world-subnational-map', countrySlug, code, period || 'last', localeKey()],
    queryFn: async () => {
      const params = period ? { period } : {};
      return (await api.get(`/world/${countrySlug}/regions/map/${code}`, { params })).data;
    },
    enabled: Boolean(countrySlug && code),
    staleTime: STALE,
  });
}

export function useWorldRegionProfile(countrySlug, slug) {
  return useQuery({
    queryKey: ['world-subnational-profile', countrySlug, slug, localeKey()],
    queryFn: async () => (await api.get(`/world/${countrySlug}/regions/region/${slug}`)).data,
    enabled: Boolean(countrySlug && slug),
    staleTime: STALE,
  });
}

export function useWorldRegionIndicator(countrySlug, slug, code) {
  return useQuery({
    queryKey: ['world-subnational-series', countrySlug, slug, code, localeKey()],
    queryFn: async () => (
      await api.get(`/world/${countrySlug}/regions/region/${slug}/${code}`)
    ).data,
    enabled: Boolean(countrySlug && slug && code),
    staleTime: STALE,
  });
}
