/**
 * Подпись последней точки графика: «28,08 млн» вместо «28 076 986,00».
 * От миллиона число укрупняется (млн, млрд, трлн / M, B, T) до двух знаков после запятой; меньшие числа
 * показываются как есть с заданной точностью. Единица измерения рядом не пишется: она уже в заголовке графика.
 */
import { formatValue } from './format';

const RU = [[1e12, 'трлн'], [1e9, 'млрд'], [1e6, 'млн']];
const EN = [[1e12, 'T'], [1e9, 'B'], [1e6, 'M']];
const NBSP = '\u00A0';

export function formatPointLabel(value, digits = 2, locale = 'ru') {
  const n = Number(value);
  if (value == null || !Number.isFinite(n)) return '';
  const abs = Math.abs(n);
  for (const [div, suffix] of (locale === 'en' ? EN : RU)) {
    if (abs >= div) {
      const scaled = n / div;
      const d = Math.abs(scaled) >= 100 ? 0 : 2;
      // «3,40» читается хуже, чем «3,4»: хвостовые нули после запятой убираем.
      const text = formatValue(scaled, d, locale)
        .replace(/([.,]\d*[1-9])0+$/, '$1')
        .replace(/[.,]0+$/, '');
      return `${text}${NBSP}${suffix}`;
    }
  }
  return formatValue(n, digits, locale);
}

/** Ширина плашки с подписью в пикселях (цифра ≈ 7 px при 12 px шрифта) плюс поля. */
export function pointLabelWidth(text) {
  return Math.max(36, Math.round(String(text || '').length * 7.2) + 16);
}
