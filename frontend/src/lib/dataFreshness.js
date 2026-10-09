/**
 * Свежесть данных у числа (круг 11, F): одна пометка «данные до августа 2026» или «устарело» вместо надписи внизу страницы.
 *
 * Возраст считается от конца периода последней точки: точка «2026-08-01» месячного ряда описывает весь август, значит возраст
 * идёт с 31 августа. Порог зависит от частоты: у дневного ряда неделя без нового значения уже много, у годового нормально
 * опоздание на полтора года (годовые данные выходят через год после периода). Сервер ничего не считает: только дата последней точки.
 */

const DAY = 86400000;

/** Сколько дней после конца периода ряд считается свежим (`fresh`) и сколько ещё допустимо (`aging`), дальше `stale`. */
const LIMITS = {
  daily: { fresh: 5, aging: 14 },
  weekly: { fresh: 14, aging: 35 },
  monthly: { fresh: 60, aging: 120 },
  quarterly: { fresh: 120, aging: 220 },
  annual: { fresh: 480, aging: 700 },
};

function parseDate(text) {
  const match = String(text || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;
  const time = Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isFinite(time) ? time : null;
}

/** Конец периода, к которому относится дата точки (мс, UTC). */
export function periodEnd(dateText, frequency) {
  const start = parseDate(dateText);
  if (start == null) return null;
  const d = new Date(start);
  const y = d.getUTCFullYear();
  const m = d.getUTCMonth();
  if (frequency === 'annual') return Date.UTC(y, 11, 31);
  if (frequency === 'quarterly') return Date.UTC(y, (Math.floor(m / 3) + 1) * 3, 0);
  if (frequency === 'weekly') return start + 6 * DAY;
  if (frequency === 'daily') return start;
  // Частота неизвестна: читаем как месячную (самая частая у официальной статистики).
  return Date.UTC(y, m + 1, 0);
}

/**
 * @param {string} lastDate дата последней точки ряда (ISO)
 * @param {string} frequency daily | weekly | monthly | quarterly | annual
 * @param {Date|number} [now]
 * @returns {{ level: 'fresh'|'aging'|'stale', ageDays: number } | null} null — даты нет, говорить нечего
 */
export function dataFreshness(lastDate, frequency, now = Date.now()) {
  const end = periodEnd(lastDate, frequency);
  if (end == null) return null;
  const current = now instanceof Date ? now.getTime() : Number(now);
  const ageDays = Math.max(0, Math.floor((current - end) / DAY));
  const limits = LIMITS[frequency] || LIMITS.monthly;
  let level = 'stale';
  if (ageDays <= limits.fresh) level = 'fresh';
  else if (ageDays <= limits.aging) level = 'aging';
  return { level, ageDays };
}

/** Формат даты для подписи «данные до …»: месяц словом в родительном падеже, у годового ряда только год. */
export function freshnessDateFormat(frequency) {
  if (frequency === 'annual') return 'annual';
  if (frequency === 'quarterly') return 'quarterly';
  if (frequency === 'daily' || frequency === 'weekly') return 'day';
  return 'fullGen';
}
