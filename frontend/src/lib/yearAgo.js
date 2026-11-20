// Строка того же периода прошлого года для колонки «к году» в таблице истории.
// Годовой ряд — предыдущий год; квартальный и месячный — тот же месяц год назад; дневной и недельный — ближайшая дата в пределах трёх дней.
// Нет строки (пропуск в ряду) — null: изменение через пропуск не считается.

function shiftYear(iso, delta) {
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return null;
  d.setUTCFullYear(d.getUTCFullYear() + delta);
  return d.toISOString().slice(0, 10);
}

function addDays(iso, n) {
  return new Date(Date.parse(`${iso}T00:00:00Z`) + n * 86400000).toISOString().slice(0, 10);
}

/**
 * @param {string} date дата строки
 * @param {Map<string, {value:number}>} byDate строки ряда по дате (ISO, 10 знаков)
 * @param {boolean} annual годовой ряд (шаг от 300 дней)
 */
export function yearAgoRow(date, byDate, annual = false) {
  const iso = String(date ?? '').slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null;
  const target = shiftYear(iso, -1);
  if (!target) return null;
  if (byDate.has(target)) return byDate.get(target);
  if (annual) {
    // Годовые ряды бывают с датой 1 января или 31 декабря: ищем тот же год по номеру.
    const year = String(Number(iso.slice(0, 4)) - 1);
    for (const [key, row] of byDate) if (key.startsWith(year)) return row;
    return null;
  }
  for (let n = 1; n <= 3; n += 1) {
    const before = addDays(target, -n);
    if (byDate.has(before)) return byDate.get(before);
    const after = addDays(target, n);
    if (byDate.has(after)) return byDate.get(after);
  }
  return null;
}
