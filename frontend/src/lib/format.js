const monthsShort = [
  'янв', 'фев', 'мар', 'апр', 'май', 'июн',
  'июл', 'авг', 'сен', 'окт', 'ноя', 'дек',
];

const monthsFull = [
  'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
  'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь',
];

const monthsGenitive = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
];

export function formatDate(dateStr, format = 'short') {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  const month = d.getUTCMonth();
  const year = d.getUTCFullYear();
  const day = d.getUTCDate();
  if (format === 'day') return `${day} ${monthsGenitive[month]} ${year}`;
  if (format === 'full') return `${monthsFull[month]} ${year}`;
  return `${monthsShort[month]} ${year}`;
}

const UNIT_CONFIG = {
  '%':         { digits: 2, suffix: '%',       space: false },
  'руб.':      { digits: 2, suffix: ' руб.',   space: false },
  'млн руб.':  { digits: 0, suffix: ' млн ₽',  space: false },
  'млрд руб.': { digits: 1, suffix: ' млрд ₽', space: false },
  'трлн руб.': { digits: 2, suffix: ' трлн ₽', space: false },
  'млн чел.':  { digits: 1, suffix: ' млн',    space: false },
};

export function formatValue(val, digits = 2) {
  if (val == null) return '—';
  return Number(val).toFixed(digits);
}

export function formatValueWithUnit(val, unit = '%') {
  if (val == null) return '—';
  const cfg = UNIT_CONFIG[unit] || { digits: 2, suffix: ` ${unit}`, space: false };
  const n = Number(val);
  return `${n.toFixed(cfg.digits)}${cfg.suffix}`;
}

export function unitSuffix(unit = '%') {
  const cfg = UNIT_CONFIG[unit];
  return cfg ? cfg.suffix.trim() : unit;
}

export function unitDigits(unit = '%') {
  return (UNIT_CONFIG[unit] || { digits: 2 }).digits;
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

const CPI_INDEX_CODES = new Set([
  'cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services', 'inflation-quarterly',
]);

export function isCpiIndex(code) {
  return CPI_INDEX_CODES.has(code);
}

export function adjustCpiDisplay(value) {
  if (value == null) return value;
  return Number(value) - 100;
}
