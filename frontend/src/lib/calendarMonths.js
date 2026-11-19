import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { fetchCalendarEvents } from './api';

/**
 * Месяцы календаря выпусков: параметры запроса одного месяца и предзагрузка соседних.
 *
 * 18.11.2026 человек листал «Предыдущий месяц» 21 раз подряд: на каждый новый месяц страница
 * показывала заглушку вместо сетки, кнопка пропадала под пальцем, нажатия попадали в заглушку
 * (Пульс, гипотеза 363). Соседние месяцы теперь лежат в кэше заранее, а параметры строятся одной
 * функцией — ключ запроса страницы и ключ предзагрузки совпадают побайтово.
 */

/** Мировые источники календаря (ФРС, BEA, Eurostat); бэкенд без `source` отдаёт только российские. */
export const WORLD_SOURCES = 'fed,bea,eurostat';

/** Первый и последний день месяца (`month` — 0..11) строками YYYY-MM-DD. */
export function monthRange(year, month) {
  const mm = String(month + 1).padStart(2, '0');
  const lastDay = new Date(year, month + 1, 0).getDate();
  return { from: `${year}-${mm}-01`, to: `${year}-${mm}-${String(lastDay).padStart(2, '0')}` };
}

/** Год и месяц со сдвигом на `delta` месяцев. */
export function shiftMonth(year, month, delta) {
  const idx = year * 12 + month + delta;
  return { year: Math.floor(idx / 12), month: ((idx % 12) + 12) % 12 };
}

/** Параметры `/api/v1/calendar` для одного месяца и фильтра источника (`''`, `cbr`, …, `world`). */
export function calendarMonthParams(year, month, source) {
  const { from, to } = monthRange(year, month);
  return {
    from,
    to,
    source: source === 'world' ? WORLD_SOURCES : (source || undefined),
    limit: 500,
  };
}

/** Ключ запроса месяца — общий для `useCalendarEvents` и предзагрузки. */
export const calendarEventsKey = (params) => ['calendar-events', params];

/** Срок свежести месяца в кэше; совпадает с `useCalendarEvents`. */
export const CALENDAR_STALE_MS = 5 * 60 * 1000;

/** Только события, дата которых внутри месяца (прежний месяц, пока грузится новый, не красит чужие клетки). */
export function eventsInRange(events, { from, to }) {
  if (!events) return [];
  return events.filter((e) => e.scheduled_date >= from && e.scheduled_date <= to);
}

/**
 * Предзагружает предыдущий и следующий месяц после того, как открытый месяц пришёл.
 * Свежий кэш не запрашивается повторно (`staleTime`), поэтому листание назад стоит один запрос на месяц.
 */
export function usePrefetchNeighbourMonths(year, month, source, enabled) {
  const queryClient = useQueryClient();
  useEffect(() => {
    if (!enabled) return;
    for (const delta of [-1, 1]) {
      const n = shiftMonth(year, month, delta);
      const params = calendarMonthParams(n.year, n.month, source);
      queryClient.prefetchQuery({
        queryKey: calendarEventsKey(params),
        queryFn: ({ signal }) => fetchCalendarEvents(params, { signal }),
        staleTime: CALENDAR_STALE_MS,
      });
    }
  }, [queryClient, year, month, source, enabled]);
}
