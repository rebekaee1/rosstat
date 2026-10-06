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
 * Дата значения человеческим языком: «3 окт.». Пустая строка, если значение сегодняшнее (или моложе `minAgeDays`) —
 * тогда подпись только шумит. Нужна, чтобы устаревший дневной ряд не выглядел как свежая котировка.
 */
export function formatAsOfHuman(isoDate, locale = 'ru', now = new Date(), { minAgeDays = 0 } = {}) {
  const day = calendarDay(isoDate, locale);
  if (!day) return '';
  const today = now.toLocaleDateString('en-CA', { timeZone: tzFor(locale) });
  if (day === today) return '';
  // Свежий дневной курс (вчера, выходные) не подписываем: подпись нужна, только когда значение действительно давнее.
  const ageDays = (Date.parse(`${today}T12:00:00Z`) - Date.parse(`${day}T12:00:00Z`)) / 86400000;
  if (minAgeDays > 0 && ageDays < minAgeDays) return '';
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


/** Имя источника для подсказки курса: на английской версии «ЕЦБ» и «Банк России» не остаются кириллицей. */
export function tickerSourceName(source, locale) {
  if (locale !== 'en' || !source) return source;
  const text = String(source);
  if (/^ЕЦБ$/i.test(text)) return 'ECB';
  if (/Банк России|^ЦБ$/i.test(text)) return 'Bank of Russia';
  return text;
}
