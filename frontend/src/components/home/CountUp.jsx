import { useLayoutEffect, useRef } from 'react';

// Счёт от нуля до значения проигрывается один раз за открытие сайта для каждой группы чисел («Мир сейчас», числа платформы)
// и только если число уже видно в экране. Число ниже экрана остаётся итоговым сразу: иначе снимок страницы целиком,
// поиск по странице и печать показали бы «0».
const played = new Set();
const COUNT_MS = 900;

/**
 * Число, которое «набегает» один раз при открытии страницы. Итоговый текст всегда лежит в разметке
 * (поиск, скринридер и печать видят его сразу); без requestAnimationFrame, при «уменьшить движение»
 * и для чисел вне экрана счёта нет.
 *
 * @param {number} value итоговое число
 * @param {(n: number) => string} format как показать число; функция должна быть стабильной (useMemo или модульная)
 * @param {string} [group] общий «один раз» для группы: пока одно число группы не доиграло, остальные тоже могут стартовать
 * @param {string} [text] итоговый текст, если он должен совпасть с готовой строкой символ в символ
 */
export default function CountUp({
  value, format, group = 'default', text: finalText,
}) {
  const ref = useRef(null);
  const text = finalText ?? format(value);
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node || played.has(group) || !Number.isFinite(value) || value <= 0) return undefined;
    if (typeof window.requestAnimationFrame !== 'function') return undefined;
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return undefined;
    if (document.documentElement.getAttribute('data-fe-motion') === 'off') return undefined;
    const box = node.getBoundingClientRect();
    if (!(box.width > 0 && box.height > 0 && box.top < window.innerHeight && box.bottom > 0)) return undefined;
    let frame = 0;
    let started = 0;
    node.textContent = format(0);
    const step = (now) => {
      if (!started) started = now;
      const progress = Math.min(1, (now - started) / COUNT_MS);
      const eased = 1 - (1 - progress) ** 3;
      node.textContent = format(value * eased);
      if (progress < 1) frame = window.requestAnimationFrame(step);
      else {
        node.textContent = text;
        played.add(group);
      }
    };
    frame = window.requestAnimationFrame(step);
    return () => {
      window.cancelAnimationFrame(frame);
      node.textContent = text;
    };
  }, [value, text, format, group]);
  return <span ref={ref}>{text}</span>;
}
