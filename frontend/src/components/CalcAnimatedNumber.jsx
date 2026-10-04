// Число результата калькулятора: плавно «докатывается» до нового значения (gsap — единственное место
// калькуляторов, где он нужен), без прыжка ширины (tabular-nums). Экранным дикторам отдаётся
// только итоговое значение: анимируемая копия скрыта от них, иначе каждый кадр счётчика озвучивался бы.
import { useEffect, useRef } from 'react';
import gsap from 'gsap';

export default function CalcAnimatedNumber({ value, format, className }) {
  const ref = useRef(null);
  const prevRef = useRef(value);
  const finalText = format(value);

  useEffect(() => {
    const node = ref.current;
    if (!node || value == null) return undefined;
    const reduced = typeof window !== 'undefined'
      && typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const from = prevRef.current ?? 0;
    prevRef.current = value;
    if (reduced || from === value) {
      node.textContent = format(value);
      return undefined;
    }
    const counter = { v: from };
    const tween = gsap.to(counter, {
      v: value,
      duration: from === 0 ? 0.9 : 0.4,
      ease: 'power2.out',
      onUpdate() {
        if (ref.current) ref.current.textContent = format(Math.round(counter.v));
      },
      onComplete() {
        if (ref.current) ref.current.textContent = format(value);
      },
    });
    return () => tween.kill();
  }, [value, format]);

  return (
    <>
      <span className={`calc-result-number ${className || ''}`} aria-hidden="true">
        <span ref={ref}>{finalText}</span>
      </span>
      <span className="sr-only">{finalText}</span>
    </>
  );
}
