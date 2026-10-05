/**
 * Текст изменения для плиток, карточек и бейджей: знак, число, единица. Не красит (цвет — lib/deltaTone.js).
 *
 * Принцип: изменение оценивается с той же точностью, с которой показано само значение. Если после округления
 * получился ноль, это «без изменений», а не красное «−0,00».
 */
import { formatValue, unitSuffix } from './format';

const MINUS = '−';
const NBSP = ' ';

/**
 * @returns {{ flat: boolean, text: string }} text — «+0,24» / «−3,10» / «0»; flat — после округления изменения нет.
 */
export function formatDeltaNumber(delta, { digits = 2, locale } = {}) {
  const n = Number(delta);
  if (delta == null || !Number.isFinite(n)) return { flat: true, text: '' };
  if (Number(n.toFixed(digits)) === 0) return { flat: true, text: '0' };
  const body = formatValue(Math.abs(n), digits, locale);
  return { flat: false, text: `${n > 0 ? '+' : MINUS}${body}` };
}

/** Единица изменения: для процента это проценты пунктами, для индекса единицы нет. */
export function deltaUnit(unit, locale, { plain = false } = {}) {
  if (unit == null || unit === '' || unit === 'индекс' || unit === 'index') return '';
  // plain: слова вместо жаргона («п. п.», «руб./л») для людей без экономического образования.
  if (unit === '%') {
    if (plain) return locale === 'en' ? 'percentage points' : 'процентного пункта';
    return locale === 'en' ? 'pp' : 'п. п.';
  }
  if (plain && (unit === 'руб./л' || unit === 'руб/л')) return locale === 'en' ? 'rubles per liter' : '₽ за литр';
  return unitSuffix(unit);
}

/**
 * Полный текст изменения: «+0,24 п. п.» (с `plain` — «+0,24 процентного пункта»). `pct` — изменение уже в процентах
 * (для индексов): «+1,2 %».
 */
export function formatDeltaWithUnit(delta, unit, { pct = false, digits = 2, locale, plain = false } = {}) {
  const { flat, text } = formatDeltaNumber(delta, { digits, locale });
  if (flat) return { flat: true, text: '' };
  if (pct) return { flat: false, text: `${text}${NBSP}%` };
  const suffix = deltaUnit(unit, locale, { plain });
  return { flat: false, text: suffix ? `${text}${NBSP}${suffix}` : text };
}
