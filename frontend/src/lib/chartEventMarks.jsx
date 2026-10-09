// Отметки событий для графиков Recharts: переключатель с памятью и вертикали с годом.
import { useCallback, useState } from 'react';
import { ReferenceLine } from 'recharts';
import { CHART_THEME } from './chartTheme';
import { labelledMarks } from './chartEvents';

const STORAGE_KEY = 'fe:chart-events';

function readFlag() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

/** Включены ли отметки. По умолчанию выключены (график спокойный); выбор помнится в браузере, если он доступен. */
export function useEventsToggle() {
  const [on, setOn] = useState(readFlag);
  const toggle = useCallback(() => {
    setOn((value) => {
      const next = !value;
      try {
        window.localStorage.setItem(STORAGE_KEY, next ? '1' : '0');
      } catch { /* хранилище недоступно: выбор живёт до перезагрузки */ }
      return next;
    });
  }, []);
  return [on, toggle];
}

/**
 * Вертикали событий для `<ComposedChart>`. Возвращает массив элементов Recharts: их нужно ставить прямо в график,
 * обёртку-компонент Recharts не увидит. Год стоит сверху, если рядом нет другой подписи.
 */
export function eventReferenceLines(marks, dates, plotPx, yAxisId) {
  if (!marks?.length) return [];
  const labelled = labelledMarks(marks, dates, plotPx);
  return marks.map((mark) => (
    <ReferenceLine
      key={`event-${mark.id}`}
      x={mark.at}
      {...(yAxisId ? { yAxisId } : {})}
      stroke={CHART_THEME.refLine}
      strokeOpacity={0.55}
      strokeWidth={1}
      strokeDasharray="2 4"
      ifOverflow="hidden"
      label={labelled.has(mark.id)
        ? {
          value: String(mark.year), position: 'insideTopRight', fill: CHART_THEME.axis, fontSize: 10.5, fontFamily: CHART_THEME.font,
        }
        : undefined}
    />
  ));
}
