import { useEffect, useRef } from 'react';
import { track, events } from './track';

/**
 * Отслеживает глубину прокрутки текущей страницы и шлёт `scroll_depth` в
 * Метрику ровно один раз для каждой пройденной отметки 25/50/75/100%.
 *
 * Контракт:
 * - Бакеты пороговые, монотонно возрастающие. Дойдя до 75%, мы уже считаем
 *   25/50/75 пройденными (Метрика тогда видит три goal-reach подряд — это
 *   ожидаемо для funnel-аналитики).
 * - Слушатель пассивный, считает по `documentElement.scrollHeight` — это
 *   корректно работает в SPA, где маршруты меняются без перезагрузки. Сброс
 *   происходит при изменении `key` (обычно — pathname или indicator code).
 * - Ничего не делает для `prefers-reduced-motion: reduce`-агентов? Нет —
 *   reduce-motion не означает «не считать аналитику», поэтому хук работает
 *   всегда.
 *
 * Использование:
 *   useScrollDepth({ key: location.pathname, page: 'indicator', indicator: code });
 */
export default function useScrollDepth({ key = '', ...payload } = {}) {
  const reachedRef = useRef(new Set());
  const payloadRef = useRef(payload);

  useEffect(() => {
    payloadRef.current = payload;
  });

  useEffect(() => {
    reachedRef.current = new Set();

    if (typeof window === 'undefined') return undefined;

    const thresholds = [25, 50, 75, 100];
    let raf = null;

    const compute = () => {
      raf = null;
      const docEl = document.documentElement;
      const total = docEl.scrollHeight - docEl.clientHeight;
      if (total <= 0) {
        if (!reachedRef.current.has(100)) {
          reachedRef.current.add(100);
          track(events.SCROLL_DEPTH, { ...payloadRef.current, percent: 100, fitsViewport: true });
        }
        return;
      }
      const scrolled = window.scrollY || docEl.scrollTop || 0;
      const pct = Math.min(100, Math.round((scrolled / total) * 100));
      for (const t of thresholds) {
        if (pct >= t && !reachedRef.current.has(t)) {
          reachedRef.current.add(t);
          track(events.SCROLL_DEPTH, { ...payloadRef.current, percent: t });
        }
      }
    };

    const onScroll = () => {
      if (raf != null) return;
      raf = window.requestAnimationFrame(compute);
    };

    compute();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });

    return () => {
      if (raf != null) window.cancelAnimationFrame(raf);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
    };
  }, [key]);
}
