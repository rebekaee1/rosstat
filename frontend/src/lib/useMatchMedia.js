import { useCallback, useSyncExternalStore } from 'react';

/**
 * Подписка на media query без вспышки: на сервере и там, где matchMedia нет (тесты), возвращает `fallback`.
 * Нужна там, где на узком экране рисуется ДРУГАЯ разметка (карточки вместо таблицы), а не просто другой CSS.
 */
export default function useMatchMedia(query, fallback = false) {
  const subscribe = useCallback((notify) => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return () => {};
    const list = window.matchMedia(query);
    list.addEventListener?.('change', notify);
    return () => list.removeEventListener?.('change', notify);
  }, [query]);
  const read = useCallback(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return fallback;
    return window.matchMedia(query).matches;
  }, [query, fallback]);
  return useSyncExternalStore(subscribe, read, () => fallback);
}
