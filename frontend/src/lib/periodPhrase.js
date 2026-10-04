import { formatDate } from './format';

/**
 * Человеческая подпись даты значения: «на 15 октября 2026» для дневных и недельных рядов,
 * «за август 2026» / «за I кв. 2026» для месячных и квартальных, «за 2025 год» для годовых.
 * `t` — функция перевода (нужны ключи w3.tele.asOf / forPeriod / forYear).
 */
export function periodPhrase(t, dateStr, dateFmt, locale) {
  if (!dateStr) return undefined;
  const date = formatDate(dateStr, dateFmt, locale);
  if (date === '—') return undefined;
  if (dateFmt === 'day' || dateFmt === 'weekly') return t('w3.tele.asOf', { date });
  if (dateFmt === 'annual') return t('w3.tele.forYear', { date });
  return t('w3.tele.forPeriod', { date });
}
