// Подписи периода на карте мира.
//
// Годовой срез карты приходит без частоты ряда: у каждой страны только дата
// последнего опубликованного за год значения. Гранулярность выводим из самого
// среза — годовые ряды датируются 1 января, месячные попадают на разные
// месяцы. Квартал от месяца по одной дате отличить нельзя (Евростат датирует
// квартал его первым месяцем), поэтому такие точки показываем как месяц —
// это фактическая дата наблюдения, а не выдуманная гранулярность.
import { formatDate } from './format';

const ANNUAL_SHARE = 0.7;

function utcParts(value) {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return { month: parsed.getUTCMonth(), day: parsed.getUTCDate() };
}

/**
 * Формат подписи для всего среза: 'annual' — если срез годовой, иначе месяц с
 * годом. Доля, а не строгое совпадение: в срез подмешивается Россия из
 * российского каталога и её дата может быть другой частоты.
 */
export function resolveWorldPeriodFormat(dates) {
  let total = 0;
  let january = 0;
  for (const value of dates || []) {
    const parts = utcParts(value);
    if (!parts) continue;
    total += 1;
    if (parts.month === 0 && parts.day === 1) january += 1;
  }
  if (!total) return 'full';
  return january / total >= ANNUAL_SHARE ? 'annual' : 'full';
}

export function worldPeriodDates(details) {
  if (!details) return [];
  const items = details instanceof Map ? details.values() : Object.values(details);
  const dates = [];
  for (const item of items) {
    if (item?.date) dates.push(item.date);
  }
  return dates;
}

export function formatWorldPeriod(value, seriesFormat = 'full') {
  const parts = utcParts(value);
  if (!parts) return '';
  if (parts.day !== 1) return formatDate(value, 'day');
  // Точка не той частоты, что весь срез (Россия в годовом срезе): год скрыл бы
  // реальный месяц наблюдения.
  if (seriesFormat === 'annual' && parts.month !== 0) return formatDate(value, 'full');
  return formatDate(value, seriesFormat);
}
