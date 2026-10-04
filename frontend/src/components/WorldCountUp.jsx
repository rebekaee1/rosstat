import { useEffect, useRef, useState } from 'react';

const DURATION_MS = 650;

function calm() {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Число, которое «докручивается» от нуля до значения при появлении и от старого значения к новому при смене.
 * При prefers-reduced-motion сразу показывает итог. Скринридеру отдаётся только итоговый текст
 * (его `aria-label` — `label`), видимая анимируемая копия скрыта: иначе каждый кадр озвучивался бы.
 */
export default function WorldCountUp({ value, format, label, className }) {
  const target = value == null || value === '' ? NaN : Number(value);
  const finalText = Number.isFinite(target) ? format(target) : '';
  // Кадр анимации помнит, к какому значению он относится: устаревший кадр после смены значения не показывается.
  // Первый кадр сразу «с нуля», иначе мелькнёт итоговое значение до старта счётчика.
  const [frameState, setFrameState] = useState(() => ({
    target, format, text: Number.isFinite(target) && !calm() ? format(0) : '',
  }));
  const previous = useRef(null);
  useEffect(() => {
    if (!Number.isFinite(target)) { previous.current = null; return undefined; }
    const from = previous.current;
    previous.current = target;
    if (calm() || typeof requestAnimationFrame !== 'function' || from === target) return undefined;
    const start = from == null ? 0 : from;
    const began = performance.now();
    let frame = 0;
    const tick = (now) => {
      const progress = Math.min(1, (now - began) / DURATION_MS);
      const eased = 1 - (1 - progress) ** 3;
      setFrameState({ target, format, text: format(progress === 1 ? target : start + (target - start) * eased) });
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, format]);
  const shown = frameState.target === target && frameState.format === format && frameState.text ? frameState.text : finalText;
  return (
    <>
      <span className={className} aria-hidden="true">{shown}</span>
      <span className="sr-only" aria-label={label || undefined}>{finalText}</span>
    </>
  );
}
