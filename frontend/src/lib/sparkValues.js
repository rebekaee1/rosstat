/**
 * Значения для мини-графика в шапке показателя: последние ~10 лет, не больше 120 точек (равномерно прореженных).
 * Чистая функция без React: ряд из {date, value} превращается в массив чисел для `Sparkline`.
 */
const SPARK_YEARS = 10;
const SPARK_MAX_POINTS = 120;

function dayMs(date) {
  return Date.parse(`${String(date).slice(0, 10)}T00:00:00Z`);
}

/** Начало окна: ровно десять лет назад от последней даты (календарно, без дрейфа високосных суток). */
function windowStart(lastMs) {
  if (!Number.isFinite(lastMs)) return -Infinity;
  const d = new Date(lastMs);
  d.setUTCFullYear(d.getUTCFullYear() - SPARK_YEARS);
  return d.getTime();
}

export function sparkValues(points) {
  const valid = (Array.isArray(points) ? points : [])
    .filter((p) => p && p.date && p.value != null && Number.isFinite(Number(p.value)));
  if (valid.length < 3) return [];
  const cutoff = windowStart(dayMs(valid[valid.length - 1].date));
  const recent = valid.filter((p) => dayMs(p.date) >= cutoff);
  const rows = recent.length >= 3 ? recent : valid;
  if (rows.length <= SPARK_MAX_POINTS) return rows.map((p) => Number(p.value));
  const step = (rows.length - 1) / (SPARK_MAX_POINTS - 1);
  return Array.from({ length: SPARK_MAX_POINTS }, (_, i) => Number(rows[Math.round(i * step)].value));
}
