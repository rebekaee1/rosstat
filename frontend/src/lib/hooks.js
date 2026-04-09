import { useQuery } from '@tanstack/react-query';
import {
  fetchIndicators,
  fetchIndicator,
  fetchIndicatorData,
  fetchIndicatorStats,
  fetchForecast,
  fetchInflation,
  fetchSystemStatus,
  fetchCalendarEvents,
  fetchCalendarUpcoming,
  fetchDashboardSparklines,
  fetchDemographicsStructure,
} from './api';

export function useIndicators(options = {}) {
  const { category, includeInactive, enabled = true } = options;
  return useQuery({
    queryKey: ['indicators', category ?? 'all', includeInactive ? 'with_inactive' : 'active_only'],
    queryFn: ({ signal }) => fetchIndicators({ category, includeInactive }, { signal }),
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    enabled,
  });
}

export function useIndicator(code) {
  return useQuery({
    queryKey: ['indicator', code],
    queryFn: ({ signal }) => fetchIndicator(code, { signal }),
    enabled: !!code,
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
}

export function useIndicatorData(code, params, options = {}) {
  const { enabled = true } = options;
  return useQuery({
    queryKey: ['indicator-data', code, params],
    queryFn: ({ signal }) => fetchIndicatorData(code, params, { signal }),
    enabled: !!code && enabled,
    staleTime: 60 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
}

export function useIndicatorStats(code) {
  return useQuery({
    queryKey: ['indicator-stats', code],
    queryFn: ({ signal }) => fetchIndicatorStats(code, { signal }),
    enabled: !!code,
    staleTime: 60 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
}

export function useForecast(code) {
  return useQuery({
    queryKey: ['forecast', code],
    queryFn: ({ signal }) => fetchForecast(code, { signal }),
    enabled: !!code,
    staleTime: 60 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
}

export function useInflation(code, options = {}) {
  const { enabled = true } = options;
  return useQuery({
    queryKey: ['inflation', code],
    queryFn: ({ signal }) => fetchInflation(code, { signal }),
    enabled: !!code && enabled,
    staleTime: 60 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
}

export function useSystemStatus() {
  return useQuery({
    queryKey: ['system-status'],
    queryFn: ({ signal }) => fetchSystemStatus({ signal }),
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000,
    retry: 2,
    retryDelay: 3000,
  });
}

export function useCalendarEvents(params = {}, options = {}) {
  const { enabled = true } = options;
  return useQuery({
    queryKey: ['calendar-events', params],
    queryFn: ({ signal }) => fetchCalendarEvents(params, { signal }),
    enabled,
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
}

export function useDashboardSparklines() {
  return useQuery({
    queryKey: ['dashboard-sparklines'],
    queryFn: ({ signal }) => fetchDashboardSparklines({ signal }),
    staleTime: 30 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
  });
}

export function useCalendarUpcoming(params = {}) {
  return useQuery({
    queryKey: ['calendar-upcoming', params],
    queryFn: ({ signal }) => fetchCalendarUpcoming(params, { signal }),
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
}

export function useDemographicsStructure() {
  return useQuery({
    queryKey: ['demographics-structure'],
    queryFn: ({ signal }) => fetchDemographicsStructure({ signal }),
    staleTime: 60 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
}
