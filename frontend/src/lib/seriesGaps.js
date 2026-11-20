// Пропуски в рядах с известной частотой (год, квартал, месяц): линия рвётся, проценты и «максимум» через пропуск не считаются.
// Частота берётся из самих дат (медианный шаг), а не из подписи ряда: так не нужно поле от бэкенда.
// Дневные и недельные ряды не трогаем: выходные и праздники — не пропуск данных.

const DAY = 86400000;

function ms(date) {
  const t = Date.parse(`${String(date ?? '').slice(0, 10)}T00:00:00Z`);
  return Number.isFinite(t) ? t : NaN;
}

/** Шаг ряда в днях: 365 (год), 91 (квартал), 30 (месяц) или 0, если ряд чаще месяца или нерегулярный. */
export function seriesCadenceDays(dates) {
  const times = (dates || []).map(ms).filter(Number.isFinite).sort((a, b) => a - b);
  if (times.length < 3) return 0;
  const gaps = [];
  for (let i = 1; i < times.length; i += 1) gaps.push((times[i] - times[i - 1]) / DAY);
  gaps.sort((a, b) => a - b);
  const median = gaps[Math.floor(gaps.length / 2)];
  if (median >= 350 && median <= 380) return 365;
  if (median >= 85 && median <= 95) return 91;
  if (median >= 27 && median <= 32) return 30;
  return 0;
}

/** Между двумя соседними датами пропущен хотя бы один период (шаг больше полутора обычных). */
export function isGapBetween(prevDate, nextDate, cadenceDays) {
  if (!cadenceDays) return false;
  const a = ms(prevDate);
  const b = ms(nextDate);
  if (!Number.isFinite(a) || !Number.isFinite(b)) return false;
  return (b - a) / DAY > cadenceDays * 1.5;
}

/**
 * Индексы строк, перед которыми пропущен период (по возрастанию дат).
 * @param {Array<{date:string}>} rows
 * @returns {Set<number>} i — между rows[i-1] и rows[i] пропуск
 */
export function gapIndexes(rows) {
  const list = rows || [];
  const cadence = seriesCadenceDays(list.map((r) => r?.date));
  const out = new Set();
  if (!cadence) return out;
  for (let i = 1; i < list.length; i += 1) {
    if (isGapBetween(list[i - 1].date, list[i].date, cadence)) out.add(i);
  }
  return out;
}

export function hasGaps(rows) {
  return gapIndexes(rows).size > 0;
}

function isoMid(a, b) {
  return new Date((ms(a) + ms(b)) / 2).toISOString().slice(0, 10);
}

/**
 * Для графика: между точками факта, где пропущен период, вставляется пустая строка `{ date, actual: null, _gap: true }`.
 * Линия без соединения (connectNulls выключен) на ней рвётся. Прогноз и строки без факта пропуск не создают.
 * Ряд без пропусков возвращается тем же массивом.
 */
export function insertGapRows(rows) {
  const list = Array.isArray(rows) ? rows : [];
  const actualRows = list.filter((r) => r && r.actual != null);
  const cadence = seriesCadenceDays(actualRows.map((r) => r.date));
  if (!cadence) return list;
  const out = [];
  let prevActual = null;
  let changed = false;
  for (const row of list) {
    if (row && row.actual != null) {
      if (prevActual && isGapBetween(prevActual.date, row.date, cadence)) {
        // Пустая строка должна идти сразу перед этой точкой; строки без факта между ними (сравнения) остаются слева.
        out.push({ date: isoMid(prevActual.date, row.date), actual: null, forecast: null, _gap: true });
        changed = true;
      }
      prevActual = row;
    }
    out.push(row);
  }
  return changed ? out : list;
}

/** Без служебных пустых строк: для выгрузки и подписей. */
export function withoutGapRows(rows) {
  const list = Array.isArray(rows) ? rows : [];
  return list.some((r) => r && r._gap) ? list.filter((r) => !r?._gap) : list;
}
