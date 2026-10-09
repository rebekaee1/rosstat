// Общие форматтеры денежных калькуляторов (/calculator*): одна точка истины
// для инфляционного, ипотечного и калькулятора сложных процентов.
// Числа следуют языку страницы: RU «1 000,5», EN «1,000.5».
import { currentUiLocale } from '../i18n/locale';

const isEn = () => currentUiLocale() === 'en';
const group = (str, sep) => str.replace(/\B(?=(\d{3})+(?!\d))/g, sep);

/** Десятичное число в языке страницы: «3,1» / «3.1». */
export function decimalText(n, digits = 1) {
  if (n == null || !Number.isFinite(n)) return '—';
  const fixed = Number(n).toFixed(digits);
  // Круг 11 (E): тысячи отделяются пробелом и у процентов («+17 147 219,6%», а не «+17147219,6%»).
  const [intPart, frac] = fixed.split('.');
  const negative = intPart.startsWith('-');
  const grouped = group(negative ? intPart.slice(1) : intPart, isEn() ? ',' : '\u00A0');
  const body = `${negative ? '-' : ''}${grouped}`;
  if (frac == null) return body;
  return `${body}${isEn() ? '.' : ','}${frac}`;
}

export function formatRubles(n) {
  if (n == null || !Number.isFinite(n)) return '—';
  const abs = Math.abs(Math.round(n));
  const sign = n < 0 ? '-' : '';
  return sign + group(abs.toString(), isEn() ? ',' : '\u00A0') + '\u00A0₽';
}

const COMPACT_RU = [[1e12, 'трлн'], [1e9, 'млрд'], [1e6, 'млн']];
const COMPACT_EN = [[1e12, 'T'], [1e9, 'B'], [1e6, 'M']];

/**
 * Сумма в сокращённой записи: «17,1 млрд ₽», «160 млн ₽» (EN: «17.1B ₽»). Меньше миллиона остаётся целым числом.
 * `symbol` дописывается через неразрывный пробел; пустой — без знака.
 */
export function formatCompactAmount(n, symbol = '₽', { prefix = false } = {}) {
  if (n == null || !Number.isFinite(n)) return '—';
  const abs = Math.abs(n);
  const sign = n < 0 ? '-' : '';
  const tail = symbol && !prefix ? `\u00A0${symbol}` : '';
  const head = symbol && prefix ? symbol : '';
  const table = isEn() ? COMPACT_EN : COMPACT_RU;
  for (const [limit, word] of table) {
    if (abs >= limit) {
      const scaled = abs / limit;
      const digits = scaled >= 100 ? 0 : 1;
      const text = decimalText(Math.round(scaled * 10 ** digits) / 10 ** digits, digits).replace(/[,.]0$/, '');
      return isEn() ? `${sign}${head}${text}${word}${tail}` : `${sign}${head}${text}\u00A0${word}${tail}`;
    }
  }
  return sign + head + group(Math.round(abs).toString(), isEn() ? ',' : '\u00A0') + tail;
}

/**
 * Готовая строка, которая помещается в `maxChars` знаков: полная запись, а если длиннее, сокращённая.
 * Нужна плашке «Результат» и плиткам итогов на телефоне, где длинное число обрезалось многоточием.
 */
export function fitAmountText(fullText, n, { symbol = '₽', maxChars = 13, prefix = false } = {}) {
  const text = String(fullText ?? '');
  if (text.length <= maxChars || n == null || !Number.isFinite(n) || Math.abs(n) < 1e6) return text;
  return formatCompactAmount(n, symbol, { prefix });
}

/** Целое с разделителями тысяч без знака валюты (для ячеек таблиц, где валюта указана в шапке). */
export function formatAmountPlain(n) {
  if (n == null || !Number.isFinite(n)) return '—';
  const abs = Math.abs(Math.round(n));
  return (n < 0 ? '-' : '') + group(abs.toString(), isEn() ? ',' : '\u00A0');
}

export function parseAmount(str) {
  const cleaned = str.replace(/[^\d]/g, '');
  return cleaned ? parseInt(cleaned, 10) : 0;
}

export function formatInput(n) {
  if (!n || n <= 0) return '';
  return group(n.toString(), isEn() ? ',' : ' ');
}

/** Склонение существительного при числе: 21 год, 22 года, 25 лет. */
export function plural(n, one, few, many) {
  const abs = Math.abs(Math.round(n));
  const mod10 = abs % 10;
  const mod100 = abs % 100;
  if (mod100 >= 11 && mod100 <= 14) return many;
  if (mod10 === 1) return one;
  if (mod10 >= 2 && mod10 <= 4) return few;
  return many;
}

export function years(n) {
  return `${n} ${plural(n, 'год', 'года', 'лет')}`;
}

/** Порядковый номер года кредита для слайдера: «3-й» / «3rd». */
export function loanYearOrdinal(n, locale = 'ru') {
  const num = Math.round(Number(n));
  if (!Number.isFinite(num) || num < 1) return String(n);
  if (locale === 'en') {
    const v = num % 100;
    if (v >= 11 && v <= 13) return `${num}th`;
    switch (num % 10) {
      case 1: return `${num}st`;
      case 2: return `${num}nd`;
      case 3: return `${num}rd`;
      default: return `${num}th`;
    }
  }
  return `${num}-й`;
}

export function fmtPct(v, sign = false) {
  if (v == null || !Number.isFinite(v)) return '—';
  const s = sign && v > 0 ? '+' : '';
  return `${s}${decimalText(v, 1)}%`;
}

/**
 * Подписи оси «годы» через равные промежутки: 0, 5, 10, 15, 20 (а не 1, 3, 5, 7, 9, 11, 14, 17, 20).
 * Значения совпадают с годами в данных графика.
 */
export function evenYearTicks(maxYear) {
  const max = Math.floor(Number(maxYear));
  if (!Number.isFinite(max) || max <= 0) return [0];
  const step = max <= 6 ? 1 : max <= 12 ? 2 : max <= 30 ? 5 : 10;
  const ticks = [];
  for (let y = 0; y <= max; y += step) ticks.push(y);
  return ticks;
}
