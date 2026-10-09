/**
 * Максимум и среднее за период, который человек выбрал на графике (круг 11, F, U16). Раньше карточки считали по последним десяти годам
 * независимо от переключателя «1 год / 5 лет / …» над графиком.
 *
 * `rows` — видимые строки графика ({ date, actual }), `fullPoints` — весь ряд ({ date, value }).
 * Возвращает null, пока человек не сузил окно (на экране весь ряд): тогда действует прежняя логика карточки.
 */
const DAY_MS = 86400000;

function dayOf(date) {
  const time = Date.parse(String(date || '').slice(0, 10));
  return Number.isFinite(time) ? time : null;
}

/** @returns {{ highest: {value: number, date: string}, average: number, years: number, count: number } | null} */
export function visibleRangeStats(rows, fullPoints) {
  const values = (Array.isArray(rows) ? rows : [])
    .map((row) => ({ date: row?.date, value: Number(row?.actual ?? row?.value) }))
    .filter((row) => row.date && Number.isFinite(row.value) && row.actual !== null);
  if (values.length < 3) return null;
  const full = Array.isArray(fullPoints) ? fullPoints.filter((point) => point?.date && Number.isFinite(Number(point.value))) : [];
  if (full.length < 3) return null;
  const firstVisible = dayOf(values[0].date);
  const lastVisible = dayOf(values[values.length - 1].date);
  const firstFull = dayOf(full[0].date);
  const lastFull = dayOf(full[full.length - 1].date);
  if (firstVisible == null || lastVisible == null || firstFull == null || lastFull == null) return null;
  // Окно сужено, если начало заметно позже начала ряда или конец раньше конца (больше месяца).
  const narrowed = firstVisible - firstFull > 31 * DAY_MS || lastFull - lastVisible > 31 * DAY_MS;
  if (!narrowed) return null;
  let highest = values[0];
  let sum = 0;
  for (const row of values) {
    sum += row.value;
    if (row.value > highest.value) highest = row;
  }
  return {
    highest: { value: highest.value, date: highest.date },
    average: sum / values.length,
    years: Math.round((lastVisible - firstVisible) / (365 * DAY_MS)),
    count: values.length,
  };
}
