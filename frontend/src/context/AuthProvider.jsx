import { useCallback, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchMe } from '../lib/api';
import { setTrackedIdentity } from '../lib/track';
import { AuthContext } from './authContext';

const AUTH_KEY = ['auth', 'me'];

export function AuthProvider({ children }) {
  const qc = useQueryClient();

  const { data: user, isLoading, isFetched } = useQuery({
    queryKey: AUTH_KEY,
    queryFn: async ({ signal }) => {
      try {
        return await fetchMe({ signal });
      } catch (e) {
        const status = e?.response?.status;
        // 401 — гость. 403 на /me — scrape-guard без fe_bind (SPA /login
        // и /register куку не ставят), не «аккаунт недоступен».
        if (status === 401 || status === 403) return null;
        throw e;
      }
    },
    // 401/403 = гость, не ретраим; транзиентные сбои (deploy, сеть) — до 2 ретраев,
    // иначе живая сессия на секунду недоступного бэка выглядела бы как разлогин.
    retry: (failureCount, error) => {
      const status = error?.response?.status;
      return status !== 401 && status !== 403 && failureCount < 2;
    },
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

  // Пробрасываем идентичность в аналитику: authed + userId уходят в Метрику
  // (userParams/setUserID) и в каждое first-party событие. Ждём отрезолвленный
  // /me (isFetched), чтобы не пометить гостем ещё не проверенную сессию.
  useEffect(() => {
    if (!isFetched) return;
    setTrackedIdentity({ authed: Boolean(user), userId: user?.id ?? null });
  }, [user, isFetched]);

  const setUser = useCallback((u) => qc.setQueryData(AUTH_KEY, u ?? null), [qc]);
  const refetch = useCallback(() => qc.invalidateQueries({ queryKey: AUTH_KEY }), [qc]);

  const value = {
    user: user ?? null,
    isAuthed: Boolean(user),
    // Пока первый /me не отрезолвился — навбар показывает нейтральный плейсхолдер
    // (анти-фликер «Войти→Кабинет», ADR-0007).
    isLoading: isLoading && !isFetched,
    setUser,
    refetch,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
