import { formatValue, unitSuffix, unitDigits } from './format';

const NBSP = ' ';

/**
 * Число с единицей через неразрывный пробел: «14,00 %», «1 500,0 млрд ₽».
 * Единый вид для подсказок графика, таблицы и подписей (раньше «14,00%» и «14,00 %» встречались рядом).
 */
export function valueWithUnit(value, digits, unit, locale) {
  const text = formatValue(value, digits ?? unitDigits(unit), locale);
  if (text === '—') return text;
  const suffix = unitSuffix(unit);
  return suffix ? `${text}${NBSP}${suffix}` : text;
}
