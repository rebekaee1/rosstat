// Число результата калькулятора: при появлении один раз «докручивается» от нуля, дальше плавно
// катится к новому значению (gsap — единственное место калькуляторов, где он нужен), без прыжка
// ширины (tabular-nums). При prefers-reduced-motion значение показывается сразу. Экранным дикторам
// отдаётся только итоговое значение: анимируемая копия скрыта от них, иначе каждый кадр счётчика
// озвучивался бы.
import { useLayoutEffect, useRef } from 'react';
import gsap from 'gsap';

export default function CalcAnimatedNumber({ value, format, className }) {
  const ref = useRef(null);
  // Что сейчас показано на экране: 0 до первого запуска — тогда первое появление считается от нуля.
  const shownRef = useRef(0);
  const firstRef = useRef(true);
  const finalText = format(value);

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node || value == null) return undefined;
    const reduced = typeof window !== 'undefined'
      && typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const from = shownRef.current;
    const first = firstRef.current;
    firstRef.current = false;
    if (reduced || from === value) {
      shownRef.current = value;
      node.textContent = format(value);
      return undefined;
    }
    const counter = { v: from };
    const tween = gsap.to(counter, {
      v: value,
      duration: first ? 0.9 : 0.4,
      ease: 'power2.out',
      onUpdate() {
        shownRef.current = counter.v;
        if (ref.current) ref.current.textContent = format(Math.round(counter.v));
      },
      onComplete() {
        shownRef.current = value;
        if (ref.current) ref.current.textContent = format(value);
      },
    });
    return () => {
      tween.kill();
      // Строгий режим повторяет эффект: следующий запуск снова считается первым, пока ничего не показано.
      if (shownRef.current === 0) firstRef.current = first;
    };
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
