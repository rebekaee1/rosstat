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
  if (isNaN(d.getTime())) return '—';
  const year = d.getUTCFullYear();
  if (format === 'annual') return year.toString();
  if (format === 'quarterly') {
    const q = Math.ceil((d.getUTCMonth() + 1) / 3);
    return `${q} кв. ${year}`;
  }
  const month = d.getUTCMonth();
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
  'тыс. чел.': { digits: 1, suffix: ' тыс.',   space: false },
  'млрд $':    { digits: 1, suffix: ' млрд $',  space: false },
  'млн $':     { digits: 0, suffix: ' млн $',   space: false },
  'индекс':    { digits: 1, suffix: '',          space: false },
  '‰':         { digits: 2, suffix: '‰',         space: false },
  'чел.':      { digits: 0, suffix: ' чел.',     space: false },
  'ед.':       { digits: 0, suffix: ' ед.',      space: false },
  'млн кв.м':  { digits: 1, suffix: ' млн кв.м', space: false },
};

function groupThousands(str) {
  return str.replace(/\B(?=(\d{3})+(?!\d))/g, '\u00A0');
}

function formatFixed(num, digits) {
  const fixed = num.toFixed(digits);
  const [intPart, decPart] = fixed.split('.');
  const sign = intPart.startsWith('-') ? '-' : '';
  const abs = intPart.replace('-', '');
  const grouped = groupThousands(abs);
  return decPart !== undefined ? `${sign}${grouped}.${decPart}` : `${sign}${grouped}`;
}

export function formatValue(val, digits = 2) {
  if (val == null) return '—';
  const num = Number(val);
  if (!Number.isFinite(num)) return '—';
  return formatFixed(num, digits);
}

export function formatValueWithUnit(val, unit = '%') {
  if (val == null) return '—';
  const num = Number(val);
  if (!Number.isFinite(num)) return '—';
  const cfg = UNIT_CONFIG[unit] || { digits: 2, suffix: ` ${unit}`, space: false };
  return `${formatFixed(num, cfg.digits)}${cfg.suffix}`;
}

export function unitSuffix(unit = '%') {
  const cfg = UNIT_CONFIG[unit];
  return cfg ? cfg.suffix.trim() : unit;
}

export function unitDigits(unit = '%') {
  return (UNIT_CONFIG[unit] || { digits: 2 }).digits;
}

export function formatAxisTick(val, digits = 2) {
  if (val == null) return '';
  const num = Number(val);
  if (!Number.isFinite(num)) return '';
  const fixed = num.toFixed(digits);
  const cleaned = fixed.replace(/\.?0+$/, '');
  const [intPart, decPart] = cleaned.split('.');
  const sign = intPart.startsWith('-') ? '-' : '';
  const abs = intPart.replace('-', '');
  const grouped = groupThousands(abs);
  return decPart ? `${sign}${grouped}.${decPart}` : `${sign}${grouped}`;
}

export function formatChange(val) {
  if (val == null) return null;
  const num = Number(val);
  if (!Number.isFinite(num)) return null;
  const sign = num >= 0 ? '+' : '';
  return `${sign}${formatFixed(num, 2)}`;
}

export function cn(...classes) {
  return classes.filter(Boolean).join(' ');
}

/**
 * Codes that need CPI-100 display adjustment.
 * MAINTENANCE: Update when adding new CPI-based indicators.
 */
const CPI_INDEX_CODES = new Set([
  'cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services', 'inflation-quarterly',
]);

export function isCpiIndex(code) {
  return CPI_INDEX_CODES.has(code);
}

export function adjustCpiDisplay(value, code) {
  if (value == null || !isFinite(value)) return value;
  if (code !== undefined && !isCpiIndex(code)) return value;
  return +(Number(value) - 100).toFixed(2);
}

export function relativeTime(dateStr) {
  if (!dateStr) return null;
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return null;
  const now = new Date();
  const diffMs = now - d;
  const diffMin = Math.floor(diffMs / 60000);
  const diffH = Math.floor(diffMs / 3600000);
  const diffD = Math.floor(diffMs / 86400000);
  if (diffD > 365) return `${Math.floor(diffD / 365)} г. назад`;
  if (diffD > 30) return `${Math.floor(diffD / 30)} мес. назад`;
  if (diffD > 0) return `${diffD} дн. назад`;
  if (diffH > 0) return `${diffH} ч. назад`;
  if (diffMin > 0) return `${diffMin} мин. назад`;
  return 'только что';
}
