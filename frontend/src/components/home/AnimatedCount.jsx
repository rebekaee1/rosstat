// Живой счётчик: один раз, когда блок впервые попал в экран, число «докручивается» от `from` до `value`.
// Текст всегда отдаёт React (итоговое значение), поэтому без IntersectionObserver, в тестах, при печати
// и при prefers-reduced-motion человек сразу видит итог; анимация лишь временно подменяет текст узла.
import { useLayoutEffect, useRef } from 'react';

const defaultFormat = (n) => String(Math.round(n));

function canAnimate() {
  if (typeof window === 'undefined') return false;
  if (typeof window.IntersectionObserver !== 'function' || typeof window.requestAnimationFrame !== 'function') return false;
  const reduce = typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  return !reduce;
}

export default function AnimatedCount({
  value, from = 0, format = defaultFormat, duration = 900, className,
}) {
  const ref = useRef(null);
  const playedRef = useRef(false);
  // Родитель может передавать новую функцию на каждый рендер: держим её в ref, чтобы не перезапускать анимацию.
  const formatRef = useRef(format);
  useLayoutEffect(() => { formatRef.current = format; });
  const target = Number(value);
  const hasValue = value != null && Number.isFinite(target);

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node || !hasValue || playedRef.current || !canAnimate()) return undefined;
    let frame = 0;
    const observer = new window.IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      observer.disconnect();
      playedRef.current = true;
      // Первое уведомление наблюдателя приходит до первой отрисовки кадра, поэтому итог не мелькнёт.
      node.textContent = formatRef.current(from);
      const started = performance.now();
      const tick = (now) => {
        const progress = Math.min(1, (now - started) / duration);
        const eased = 1 - (1 - progress) ** 3;
        node.textContent = formatRef.current(from + (target - from) * eased);
        if (progress < 1) frame = window.requestAnimationFrame(tick);
        else node.textContent = formatRef.current(target);
      };
      frame = window.requestAnimationFrame(tick);
    }, { threshold: 0.2 });
    observer.observe(node);
    return () => {
      observer.disconnect();
      window.cancelAnimationFrame(frame);
      // Прервали на середине (смена значения, уход со страницы): оставляем итог, а не промежуток.
      if (node.isConnected) node.textContent = formatRef.current(target);
    };
  }, [hasValue, target, from, duration]);

  return <span ref={ref} className={className}>{hasValue ? format(target) : ''}</span>;
}
