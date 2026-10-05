import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from './api';
import { useLocale } from '../i18n';

const searchKey = (locale, q, limit) => ['catalog-search', 'v3', locale, q, limit];
const fetchSearch = (q, limit, signal) => api.get('/search', { params: { q, limit }, signal }).then((r) => r.data);

/** One server search across public catalogues; never display another query's hits. */
export default function useGlobalSearch(query, { enabled = true, limit = 100 } = {}) {
  const { locale } = useLocale();
  const needle = String(query || '').trim();
  const [settled, setSettled] = useState(needle);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(needle), 300);
    return () => clearTimeout(timer);
  }, [needle]);
  const isDebouncing = needle !== settled;
  const queryClient = useQueryClient();
  const request = useQuery({
    queryKey: searchKey(locale, settled, limit),
    queryFn: ({ signal }) => fetchSearch(settled, limit, signal),
    enabled: enabled && Boolean(settled) && !isDebouncing,
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    retry: 1,
  });
  // Подгрузка заранее: подсказка уже «горячая», когда человек её нажимает (паузу набора обходим).
  const prefetch = (text) => {
    const q = String(text || '').trim();
    if (!q) return;
    queryClient.prefetchQuery({
      queryKey: searchKey(locale, q, limit),
      queryFn: ({ signal }) => fetchSearch(q, limit, signal),
      staleTime: 60_000,
    }).catch(() => {});
  };
  // Подсказка нажата: пауза набора не нужна, ищем сразу.
  const flush = (text) => setSettled(String(text || '').trim());
  return { ...request, isDebouncing, prefetch, flush };
}
