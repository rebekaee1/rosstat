// Хуки графиков: ширина контейнера, подсказка по касанию, предпочтение «меньше движения».
import {
  useCallback, useEffect, useId, useMemo, useRef, useState,
} from 'react';

/**
 * Ширина элемента через ResizeObserver. Возвращает [refCallback, width].
 * Колбэк-реф (а не useRef + эффект с []), потому что график часто монтируется позже
 * первого рендера страницы — после загрузки данных; обычный эффект такой узел не увидит.
 */
export function useElementWidth() {
  const [node, setNode] = useState(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    if (!node) return undefined;
    // ResizeObserver сообщает размер сразу после observe(), отдельное измерение не нужно.
    if (typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect?.width;
      if (w) setWidth(w);
    });
    ro.observe(node);
    return () => ro.disconnect();
  }, [node]);

  return [setNode, width];
}

function readMedia(query) {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  try {
    return window.matchMedia(query).matches;
  } catch {
    return false;
  }
}

function useMediaQuery(query) {
  const [matches, setMatches] = useState(() => readMedia(query));
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined;
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    if (mql.addEventListener) mql.addEventListener('change', onChange);
    else if (mql.addListener) mql.addListener(onChange);
    return () => {
      if (mql.removeEventListener) mql.removeEventListener('change', onChange);
      else if (mql.removeListener) mql.removeListener(onChange);
    };
  }, [query]);
  return matches;
}

/** true, если пользователь просит меньше движения (анимации графиков отключаем). */
export function usePrefersReducedMotion() {
  return useMediaQuery('(prefers-reduced-motion: reduce)');
}

/** true на устройствах с грубым указателем (палец). */
export function useCoarsePointer() {
  return useMediaQuery('(pointer: coarse)');
}

/**
 * Подсказка графика по касанию. На сенсорных экранах Recharts показывает подсказку по
 * эмулированным мышиным событиям и не прячет её, пока не придёт «уход мыши» — часто никогда.
 * Здесь подсказка открыта, пока палец внутри графика (касание = показать), и закрывается
 * касанием вне графика или клавишей Escape. На компьютере ничего не меняется (active не задан).
 *
 * Использование: `const touch = useTouchTooltip(containerRef);`
 *   <div ref={containerRef} onPointerDownCapture={touch.onPointerDownCapture}> ... <Tooltip {...touch.tooltipProps} />
 */
export function useTouchTooltip(containerRef) {
  const coarse = useCoarsePointer();
  const [open, setOpen] = useState(false);
  const openRef = useRef(false);

  const setOpenState = useCallback((value) => {
    openRef.current = value;
    setOpen(value);
  }, []);

  useEffect(() => {
    if (!coarse || !open) return undefined;
    const onOutside = (event) => {
      const el = containerRef?.current;
      if (el && event.target instanceof Node && el.contains(event.target)) return;
      setOpenState(false);
    };
    const onKey = (event) => { if (event.key === 'Escape') setOpenState(false); };
    document.addEventListener('pointerdown', onOutside, true);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onOutside, true);
      document.removeEventListener('keydown', onKey);
    };
  }, [coarse, open, containerRef, setOpenState]);

  const onPointerDownCapture = useCallback(() => {
    if (!openRef.current) setOpenState(true);
  }, [setOpenState]);

  return {
    coarse,
    open,
    onPointerDownCapture,
    // На компьютере undefined → Recharts сам показывает по наведению; на сенсоре false скрывает.
    tooltipProps: coarse ? { active: open ? undefined : false } : {},
  };
}

/**
 * Набор идентификаторов градиентов одного графика (лента, сапфир, заливка, прогноз, столбцы, шарик).
 * У каждого графика на странице свои id: два графика рядом не берут чужие градиенты.
 */
export function useChartGlassIds(prefix = 'fe-glass') {
  const raw = useId().replace(/[^A-Za-z0-9_-]/g, '');
  const base = `${prefix}-${raw}`;
  return useMemo(() => ({
    ribbon: `${base}-ribbon`,
    sapphire: `${base}-sapphire`,
    area: `${base}-area`,
    areaSapphire: `${base}-area-sapphire`,
    forecast: `${base}-forecast`,
    bar: `${base}-bar`,
    barForecast: `${base}-bar-forecast`,
    beam: `${base}-beam`,
    bead: `${base}-bead`,
  }), [base]);
}
