import { useEffect, useState } from 'react';

/**
 * Пока страница загружается, на <html> стоит data-fe-loading: плавающее приглашение зарегистрироваться
 * прячется (CSS в styles/z1-polish.css), чтобы под скелетоном не торчала посторонняя карточка.
 */
export default function usePageLoading(active) {
  useEffect(() => {
    if (!active || typeof document === 'undefined') return undefined;
    const root = document.documentElement;
    root.setAttribute('data-fe-loading', '1');
    return () => root.removeAttribute('data-fe-loading');
  }, [active]);
}

/** true, если загрузка тянется дольше `ms`: тогда стоит сказать человеку, что мы не зависли. */
export function useSlowFlag(active, ms = 5000) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!active) return undefined;
    const timer = setTimeout(() => setSlow(true), ms);
    return () => { clearTimeout(timer); setSlow(false); };
  }, [active, ms]);
  return active && slow;
}
