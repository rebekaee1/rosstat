import { useQuery } from '@tanstack/react-query';
import {
  fetchIndicators,
  fetchIndicator,
  fetchIndicatorData,
  fetchIndicatorStats,
  fetchForecast,
  fetchInflation,
  fetchSystemStatus,
} from './api';

export function useIndicators(options = {}) {
  const { category, includeInactive, enabled = true } = options;
  return useQuery({
    queryKey: ['indicators', category ?? 'all', includeInactive ? 'with_inactive' : 'active_only'],
    queryFn: () => fetchIndicators({ category, includeInactive }),
    staleTime: 5 * 60 * 1000,
    enabled,
  });
}

export function useIndicator(code) {
  return useQuery({
    queryKey: ['indicator', code],
    queryFn: () => fetchIndicator(code),
    enabled: !!code,
    staleTime: 5 * 60 * 1000,
  });
}

export function useIndicatorData(code, params) {
  return useQuery({
    queryKey: ['indicator-data', code, params],
    queryFn: () => fetchIndicatorData(code, params),
    enabled: !!code,
    staleTime: 60 * 60 * 1000,
  });
}

export function useIndicatorStats(code) {
  return useQuery({
    queryKey: ['indicator-stats', code],
    queryFn: () => fetchIndicatorStats(code),
    enabled: !!code,
    staleTime: 60 * 60 * 1000,
  });
}

export function useForecast(code) {
  return useQuery({
    queryKey: ['forecast', code],
    queryFn: () => fetchForecast(code),
    enabled: !!code,
    staleTime: 60 * 60 * 1000,
  });
}

export function useInflation(code, options = {}) {
  const { enabled = true } = options;
  return useQuery({
    queryKey: ['inflation', code],
    queryFn: () => fetchInflation(code),
    enabled: !!code && enabled,
    staleTime: 60 * 60 * 1000,
  });
}

export function useSystemStatus() {
  return useQuery({
    queryKey: ['system-status'],
    queryFn: fetchSystemStatus,
    staleTime: 30 * 1000,
  });
}
