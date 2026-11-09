import { useQuery } from '@tanstack/react-query';
import api from './api';
import { resolveBrowserLocale } from '../i18n/locale';

/** Лёгкая сводка цен России (тот же эндпоинт, что у блока на странице цен); без неё блок просто не показывается. */
export function useHomePriceSummary() {
  return useQuery({
    queryKey: ['r9a-home-prices', resolveBrowserLocale()],
    queryFn: async ({ signal }) => (await api.get('/regions/russia/prices-summary', { signal })).data,
    staleTime: 10 * 60 * 1000,
    retry: 1,
  });
}

