import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../context/authContext';
import { fetchDownloadQuota } from './api';

/**
 * Состояние гейта выгрузок для UI кнопок Excel/CSV (ADR-0007 Phase 2).
 * Авторизованный — unlimited (кнопки активны). Гость — remaining из счётчика;
 * когда remaining<=0, blocked=true: кнопка тускнеет, подсказка зовёт войти.
 * Жёсткий лимит всё равно на сервере — это только подсветка состояния.
 */
export function useDownloadAccess() {
  const { isAuthed, isLoading } = useAuth();
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ['download-quota', isAuthed],
    queryFn: () => fetchDownloadQuota(),
    enabled: !isLoading,
    staleTime: 30_000,
    retry: false,
  });

  // После успешной выгрузки бэкенд отдаёт остаток в X-Download-Remaining →
  // excel.js шлёт событие; обновляем кэш квоты без повторного запроса.
  useEffect(() => {
    const onDone = (e) => {
      const r = e?.detail?.remaining;
      if (typeof r === 'number') {
        qc.setQueryData(['download-quota', isAuthed], (old) => ({
          unlimited: old?.unlimited ?? false,
          limit: old?.limit,
          remaining: r,
        }));
      } else {
        qc.invalidateQueries({ queryKey: ['download-quota'] });
      }
    };
    window.addEventListener('fe:download-done', onDone);
    return () => window.removeEventListener('fe:download-done', onDone);
  }, [qc, isAuthed]);

  const unlimited = !!data?.unlimited;
  const remaining = unlimited ? null : (data?.remaining ?? null);
  const historyYears = data?.history_years ?? 0;
  const blocked = !isAuthed && !unlimited && remaining != null && remaining <= 0;
  return { isAuthed, unlimited, remaining, historyYears, blocked };
}
