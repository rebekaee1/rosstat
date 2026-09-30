import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from './api';
import { useLocale } from '../i18n';

/** One server search across public catalogues; never display another query's hits. */
export default function useGlobalSearch(query, { enabled = true, limit = 100 } = {}) {
  const { locale } = useLocale();
  const needle = String(query || '').trim();
  const [settled, setSettled] = useState(needle);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(needle), 200);
    return () => clearTimeout(timer);
  }, [needle]);
  const isDebouncing = needle !== settled;
  const request = useQuery({
    queryKey: ['catalog-search', 'v2', locale, settled, limit],
    queryFn: ({ signal }) => api.get('/search', { params: { q: settled, limit }, signal }).then(r => r.data),
    enabled: enabled && Boolean(settled) && !isDebouncing,
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    retry: 1,
  });
  return { ...request, isDebouncing };
}
