import { useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchMe } from '../lib/api';
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
        if (e?.response?.status === 401) return null; // аноним — это не ошибка
        throw e;
      }
    },
    retry: false,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

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
