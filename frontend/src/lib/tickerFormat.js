// RU-витрина живёт по Москве, EN — международная, часы в UTC.
export const tzFor = (locale) => (locale === 'en' ? 'UTC' : 'Europe/Moscow');

/** Календарный день «ГГГГ-ММ-ДД» для даты ряда (как есть) или метки времени (в часовом поясе витрины). */
function calendarDay(isoDate, locale = 'ru') {
  if (!isoDate) return null;
  if (!isoDate.includes('T')) return /^\d{4}-\d{2}-\d{2}$/.test(isoDate) ? isoDate : null;
  const d = new Date(isoDate);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString('en-CA', { timeZone: tzFor(locale) });
}

/**
 * Дата значения человеческим языком: «3 окт.». Пустая строка, если значение сегодняшнее —
 * тогда подпись только шумит. Нужна, чтобы устаревший дневной ряд не выглядел как свежая котировка.
 */
export function formatAsOfHuman(isoDate, locale = 'ru', now = new Date()) {
  const day = calendarDay(isoDate, locale);
  if (!day) return '';
  const today = now.toLocaleDateString('en-CA', { timeZone: tzFor(locale) });
  if (day === today) return '';
  const d = new Date(`${day}T12:00:00Z`);
  return d.toLocaleDateString(locale === 'en' ? 'en-US' : 'ru-RU', {
    day: 'numeric', month: 'short', timeZone: 'UTC',
  });
}

/** Откуда число: биржевая котировка или официальный курс ЦБ. Для прочих источников подписи нет. */
export function tickerSourceKind(source) {
  const text = String(source || '');
  if (/moex|мосбирж/i.test(text)) return 'market';
  if (/cbr|банк россии|\bцб\b/i.test(text)) return 'cb';
  return null;
}

