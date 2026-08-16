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

export function fmtPct(v, sign = false) {
  if (v == null || !Number.isFinite(v)) return '—';
  const s = sign && v > 0 ? '+' : '';
  return `${s}${v.toFixed(1).replace('.', ',')}%`;
}
