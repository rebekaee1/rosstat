import { useCallback, useSyncExternalStore } from 'react';

/** Подписка на CSS media query. Без matchMedia (SSR, часть тестовых сред) возвращает `fallback`. */
export default function useMediaQuery(query, fallback = false) {
  const subscribe = useCallback((notify) => {
    const list = typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia(query) : null;
    if (!list || typeof list.addEventListener !== 'function') return () => {};
    list.addEventListener('change', notify);
    return () => list.removeEventListener('change', notify);
  }, [query]);
  const read = useCallback(() => (
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia(query).matches
      : fallback
  ), [query, fallback]);
  return useSyncExternalStore(subscribe, read, () => fallback);
}
