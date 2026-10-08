// Число результата калькулятора. Круг 9 (K4): итог показывается сразу и всегда верный; раньше цифры «докручивались» от нуля,
// и на медленной машине неверное промежуточное число висело секунды (рядом столбик уже показывал итог). Теперь при смене значения
// число только коротко проявляется (прозрачность, gsap) и по нему проходит блик камня результата (K1 .fe-glint).
// При prefers-reduced-motion, в фоновой вкладке и при том же значении движения нет. Экранным дикторам отдаётся только итог:
// видимая копия скрыта от них (aria-hidden), чтобы пересчёт не озвучивался по кадрам.
import { useLayoutEffect, useRef } from 'react';
import gsap from 'gsap';
import { replayGlint } from '../lib/calcGlint';
import '../styles/z8-tools.css';

export default function CalcAnimatedNumber({ value, format, className }) {
  const ref = useRef(null);
  const shownRef = useRef(null);
  const finalText = format(value);

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node || value == null) return undefined;
    const previous = shownRef.current;
    shownRef.current = value;
    node.textContent = format(value);
    const reduced = typeof window !== 'undefined'
      && typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const hidden = typeof document !== 'undefined' && document.hidden;
    if (reduced || hidden || previous === value) return undefined;
    if (previous != null) replayGlint(node.closest('.fe-glint'));
    const tween = gsap.fromTo(
      node,
      { opacity: previous == null ? 0.2 : 0.55 },
      { opacity: 1, duration: previous == null ? 0.35 : 0.22, ease: 'power2.out', clearProps: 'opacity' },
    );
    return () => {
      tween.kill();
      node.style.opacity = '';
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
