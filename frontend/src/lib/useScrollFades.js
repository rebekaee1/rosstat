import { useEffect } from 'react';

/**
 * Затухание у края прокручиваемой полосы (круг 11, F): человек видит, что таблица или ряд продолжается за краем.
 * Ставит на элемент `data-fade-start` и `data-fade-end` («true» / «false»); сами градиенты рисуют стили
 * (`[data-fade-end='true']` в z4-indicator.css и z6-rating.css). Без рамок и теней: затухает сам контент.
 */
export function attachScrollFades(el, onChange = null) {
  if (!el || typeof el.addEventListener !== 'function') return () => {};
  const update = () => {
    const max = el.scrollWidth - el.clientWidth;
    el.dataset.fadeStart = el.scrollLeft > 2 ? 'true' : 'false';
    el.dataset.fadeEnd = max > 2 && max - el.scrollLeft > 2 ? 'true' : 'false';
    if (onChange) onChange({ start: el.dataset.fadeStart === 'true', end: el.dataset.fadeEnd === 'true' });
  };
  update();
  el.addEventListener('scroll', update, { passive: true });
  let observer = null;
  if (typeof ResizeObserver === 'function') {
    observer = new ResizeObserver(update);
    observer.observe(el);
    if (el.firstElementChild) observer.observe(el.firstElementChild);
  } else if (typeof window !== 'undefined') {
    window.addEventListener('resize', update);
  }
  return () => {
    el.removeEventListener('scroll', update);
    if (observer) observer.disconnect();
    else if (typeof window !== 'undefined') window.removeEventListener('resize', update);
    delete el.dataset.fadeStart;
    delete el.dataset.fadeEnd;
  };
}

/** Элемент по ссылке: `useScrollFades(ref, [число колонок], onChange?)`; повторно считается при смене зависимостей. */
export function useScrollFades(ref, deps = [], onChange = null) {
  useEffect(() => attachScrollFades(ref.current, onChange),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    deps);
}

/** Элементы внутри корня по селектору (таблица истории рисуется компонентом, которому ссылку не передать). */
export function useScrollFadesWithin(rootRef, selector, deps = []) {
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return undefined;
    const cleanups = Array.from(root.querySelectorAll(selector)).map((el) => attachScrollFades(el));
    return () => cleanups.forEach((fn) => fn());
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
