/**
 * Закрепление точки графика нажатием (18.11.2026; общий код вынесен из IndicatorChart 19.11.2026).
 *
 * Recharts передаёт в onClick графика подпись ближайшей точки (`activeLabel`). Нажатие закрепляет её,
 * повторное нажатие на ту же точку снимает выбор. Отпускание после сдвига графика мышью — не нажатие:
 * хозяин перетаскивания вызывает `suppressNextPick()` до того, как браузер пришлёт click.
 * Что делать при новом выборе (событие аналитики, переход таблицы) — решает график в `onPick(label)`.
 *
 * Плот с закреплением помечают `data-interactive`: поток поведения (behavior.js) считает нажатие
 * по нему управлением, а не мёртвым кликом.
 */
import { useCallback, useRef, useState } from 'react';

/**
 * @param {(label: string|number) => void} [onPick] вызывается при новом выборе (не при снятии)
 * @returns {{ picked: any, setPicked: Function, handlePlotClick: Function, suppressNextPick: Function }}
 */
export function useChartPick(onPick) {
  const [picked, setPicked] = useState(null);
  const suppressRef = useRef(false);

  const handlePlotClick = (state) => {
    if (suppressRef.current) {
      suppressRef.current = false;
      return;
    }
    const label = state?.activeLabel;
    if (label == null || label === '') return;
    if (picked === label) {
      setPicked(null);
      return;
    }
    setPicked(label);
    if (onPick) onPick(label);
  };

  // Стабильная ссылка: её вызывают из обработчиков указателя, завёрнутых в useCallback.
  const suppressNextPick = useCallback(() => {
    suppressRef.current = true;
  }, []);

  return { picked, setPicked, handlePlotClick, suppressNextPick };
}
