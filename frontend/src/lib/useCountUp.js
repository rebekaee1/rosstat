import { useEffect, useState } from 'react';

const prefersReducedMotion = () => (
  typeof window !== 'undefined'
  && typeof window.matchMedia === 'function'
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches
);

/** Плавное замедление к концу: быстрый старт, мягкая посадка. */
export function easeOutCubic(t) {
  return 1 - (1 - t) ** 3;
}

/**
 * Счёт цифр один раз за жизнь компонента (DS5): число «набегает» от нуля к цели за `durationMs`
 * и больше не пересчитывается, даже если цель позже обновилась (тогда оно просто встаёт на новое значение).
 * Без анимации, если человек просил меньше движения, нет requestAnimationFrame или значение не число.
 * Возвращает число для показа; форматируйте его так же, как обычное значение.
 */
export default function useCountUp(target, { durationMs = 900, enabled = true } = {}) {
  const goal = Number(target);
  const valid = Number.isFinite(goal);
  const animate = enabled && valid && !prefersReducedMotion() && typeof requestAnimationFrame === 'function';
  // progress 0…1 меняется только из кадров анимации; finished запоминает, что счёт уже был.
  const [progress, setProgress] = useState(0);
  const [finished, setFinished] = useState(false);

  useEffect(() => {
    if (!animate || finished) return undefined;
    let frame = 0;
    let startedAt = null;
    const step = (now) => {
      if (startedAt === null) startedAt = now;
      const p = Math.min(1, (now - startedAt) / durationMs);
      setProgress(p);
      if (p < 1) frame = requestAnimationFrame(step);
      else setFinished(true);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [goal, animate, finished, durationMs]);

  if (!valid || !animate || finished) return goal;
  return goal * easeOutCubic(progress);
}
