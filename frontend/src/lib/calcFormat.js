// Общие форматтеры денежных калькуляторов (/calculator*): одна точка истины
// для инфляционного, ипотечного и калькулятора сложных процентов.

export function formatRubles(n) {
  if (n == null || !Number.isFinite(n)) return '—';
  const abs = Math.abs(Math.round(n));
  const sign = n < 0 ? '-' : '';
  return sign + abs.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '\u00A0') + '\u00A0₽';
}

export function parseAmount(str) {
  const cleaned = str.replace(/[^\d]/g, '');
  return cleaned ? parseInt(cleaned, 10) : 0;
}

export function formatInput(n) {
  if (!n || n <= 0) return '';
  return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
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
  return `${s}${v.toFixed(1).replace('.', ',')}%`;
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
