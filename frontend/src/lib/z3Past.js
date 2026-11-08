// Круг 2, зона R2-Z3: «выгодно ли сейчас» — сколько давали за ту же сумму месяц и год назад. Чистая логика без React.
const DAY = 86_400_000;

function ms(date) {
  return Date.parse(`${String(date || '').slice(0, 10)}T12:00:00Z`);
}

/** Курс «из → в» за одну единицу на дату: последняя точка не позже (последняя дата − days). Нет данных на такую глубину: null. */
export function rateDaysAgo(rows, days, { invert = false, units = 1 } = {}) {
  const points = (rows || [])
    .map((row) => ({ date: String(row?.date || '').slice(0, 10), value: Number(row?.value) }))
    .filter((p) => p.date && Number.isFinite(p.value) && p.value > 0)
    .sort((a, b) => (a.date < b.date ? -1 : 1));
  if (points.length < 2) return null;
  const target = ms(points[points.length - 1].date) - days * DAY;
  // Ряд должен уходить достаточно далеко: иначе «год назад» по данным за три месяца было бы неправдой.
  if (ms(points[0].date) > target + 4 * DAY) return null;
  let found = null;
  for (const p of points) { if (ms(p.date) <= target) found = p; else break; }
  if (!found) return null;
  const perOne = found.value / (units || 1);
  return { date: found.date, rate: invert ? 1 / perOne : perOne };
}

/** Сравнение сегодняшнего курса с прошлым: { date, value, pct } (pct: на сколько процентов сейчас больше). */
export function comparePast(amount, nowRate, past) {
  if (!past || !(nowRate > 0) || !Number.isFinite(amount)) return null;
  const value = amount * past.rate;
  if (!(value > 0)) return null;
  return { date: past.date, value, pct: ((nowRate / past.rate) - 1) * 100 };
}
