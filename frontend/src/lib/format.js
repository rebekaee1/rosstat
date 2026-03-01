const monthsShort = [
  'янв', 'фев', 'мар', 'апр', 'май', 'июн',
  'июл', 'авг', 'сен', 'окт', 'ноя', 'дек',
];

const monthsFull = [
  'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
  'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь',
];

export function formatDate(dateStr, format = 'short') {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  const month = d.getUTCMonth();
  const year = d.getUTCFullYear();
  if (format === 'full') return `${monthsFull[month]} ${year}`;
  return `${monthsShort[month]} ${year}`;
}

export function formatValue(val, digits = 2) {
  if (val == null) return '—';
  return Number(val).toFixed(digits);
}

export function formatChange(val) {
  if (val == null) return null;
  const num = Number(val);
  const sign = num >= 0 ? '+' : '';
  return `${sign}${num.toFixed(2)}`;
}

export function cn(...classes) {
  return classes.filter(Boolean).join(' ');
}
