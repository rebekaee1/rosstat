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

/**
 * Короткая подпись даты на оси графика (не tooltip/таблица).
 * multiYear: при окне >1 года добавляем двузначный год, иначе только день+месяц.
 */
export function formatChartAxisDate(dateStr, format = 'short', { multiYear = false } = {}) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return '';
  const day = d.getUTCDate();
  const month = monthsShort[d.getUTCMonth()];
  const year = d.getUTCFullYear();

  if (format === 'day' || format === 'weekly') {
    return multiYear ? `${day} ${month} '${String(year).slice(-2)}` : `${day} ${month}`;
  }
  if (format === 'quarterly' || format === 'annual') {
    return formatDate(dateStr, format);
  }
  return formatDate(dateStr, format === 'full' ? 'short' : format);
}

/**
 * Сколько подписей оси X влезает без наезда (мобилка ~235px plot → 3–4 тика).
 * labelChars — типичная длина подписи («май 2022» ≈ 8, «2023» ≈ 4).
 */
export function chartAxisTickBudget(plotWidthPx, labelChars = 8) {
  const w = Number(plotWidthPx) || 0;
  if (w <= 0) return 7;
  // ~6.2px на символ JetBrains Mono 11px + зазор между подписями.
  const perTick = Math.max(36, labelChars * 6.2 + 18);
  return Math.max(2, Math.min(7, Math.floor(w / perTick) + 1));
}

/** Равномерно N подписей по видимому окну (daily/weekly не заливают ось). */
export function pickChartAxisTicks(points, maxTicks = 7, dateKey = 'date') {
  if (!points?.length) return [];
  const get = (p) => (dateKey === 'date' ? p.date : p[dateKey]);
  if (points.length <= maxTicks) {
    return points.map(get);
  }
  const ticks = [get(points[0])];
  const step = (points.length - 1) / (maxTicks - 1);
  for (let i = 1; i < maxTicks - 1; i += 1) {
    const idx = Math.round(i * step);
    const date = get(points[idx]);
    if (ticks[ticks.length - 1] !== date) ticks.push(date);
  }
  const last = get(points[points.length - 1]);
  if (ticks[ticks.length - 1] !== last) ticks.push(last);
  return ticks;
}

/**
 * Единый резолвер формата даты для оси графика, таблицы и телеметрии —
 * чтобы период-лейблы везде совпадали по гранулярности отображаемого ряда.
 *
 * Для generic-семей `chartMode === 'cpi'` (нейтрально) и формат диктует
 * `frequency` самого ряда (квартальный sibling → 'quarterly' и т.д.).
 * Для legacy CPI/housing/ppi гранулярность диктует режим (chartMode/safeViewMode).
 * Ось графика дополнительно ужимает 'full' → 'short' на уровне тиков
 * (см. IndicatorChart tickFormatter), поэтому здесь 'full' безопасен.
 */
export function resolveDateFormat({ chartMode, frequency, safeViewMode } = {}) {
  if (safeViewMode === 'index-quarterly') return 'quarterly';
  if (safeViewMode === 'index-annual') return 'annual';
  if (chartMode === 'quarterly' || chartMode === 'qoq') return 'quarterly';
  if (chartMode === 'annual') return 'annual';
  // Частота ряда важнее режима: точка «год к году» на квартальных данных всё
  // равно датируется кварталом, а не месяцем. Иначе на карточках квартального
  // индикатора в режиме г/г выводилось «март 2026» вместо «I кв. 2026».
  if (frequency === 'quarterly') return 'quarterly';
  if (frequency === 'annual') return 'annual';
  // Недельные ряды (ИПЦ «Недельная», inflation-weekly): дата = конкретный день,
  // иначе ось и тултип показывают только «май 2026» без номера недели.
  if (chartMode === 'weekly' || frequency === 'weekly') return 'weekly';
  if (chartMode === 'yoy' || chartMode === 'period-monthly') return 'full';
  if (chartMode === 'period-weekly') return 'weekly';
  if (chartMode !== 'inflation' && frequency === 'daily') return 'day';
  return 'full';
}

export function formatDate(dateStr, format = 'short') {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return '—';
  const year = d.getUTCFullYear();
  if (format === 'annual') return year.toString();
  if (format === 'quarterly') {
    const q = Math.ceil((d.getUTCMonth() + 1) / 3);
    const roman = ['I', 'II', 'III', 'IV'][q - 1];
    return `${roman} кв. ${year}`;
  }
  const month = d.getUTCMonth();
  const day = d.getUTCDate();
  if (format === 'day') return `${day} ${monthsGenitive[month]} ${year}`;
  if (format === 'weekly') return `${day} ${monthsGenitive[month]} ${year}`;
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
  'индекс':    { digits: 2, suffix: '',          space: false },
  '‰':         { digits: 2, suffix: '‰',         space: false },
  'чел.':      { digits: 0, suffix: ' чел.',     space: false },
  'ед.':       { digits: 0, suffix: ' ед.',      space: false },
  'млн кв.м':  { digits: 1, suffix: ' млн кв.м', space: false },
};

function groupThousands(str) {
  return str.replace(/\B(?=(\d{3})+(?!\d))/g, '\u00A0');
}

// Десятичный разделитель — русская запятая (В-11): тысячи уже отделялись
// NBSP по-русски, дробная часть оставалась с английской точкой. CSV/Excel-
// экспорт не затронут — файлы собирает бэкенд из сырых значений.
function formatFixed(num, digits) {
  const fixed = num.toFixed(digits);
  const [intPart, decPart] = fixed.split('.');
  const sign = intPart.startsWith('-') ? '-' : '';
  const abs = intPart.replace('-', '');
  const grouped = groupThousands(abs);
  return decPart !== undefined ? `${sign}${grouped},${decPart}` : `${sign}${grouped}`;
}

export function formatValue(val, digits = 2) {
  if (val == null) return '—';
  const num = Number(val);
  if (!Number.isFinite(num)) return '—';
  return formatFixed(num, digits);
}

export function formatValueWithUnit(val, unit = '%', digits) {
  if (val == null) return '—';
  const num = Number(val);
  if (!Number.isFinite(num)) return '—';
  const cfg = UNIT_CONFIG[unit] || { digits: 2, suffix: ` ${unit}`, space: false };
  const d = digits ?? cfg.digits;
  return `${formatFixed(num, d)}${cfg.suffix}`;
}

export function unitSuffix(unit = '%') {
  const cfg = UNIT_CONFIG[unit];
  return cfg ? cfg.suffix.trim() : unit;
}

export function unitDigits(unit = '%') {
  return (UNIT_CONFIG[unit] || { digits: 2 }).digits;
}

/**
 * Точность числа на графике/в карточках. Единый стандарт — два знака после
 * запятой (правка созвона 2026-06-11): прежние 3-знаковые исключения для
 * недельного ИПЦ убраны вместе с недельным прогнозом.
 */
export function chartValueDigits(unit = '%') {
  return unitDigits(unit);
}

export function formatAxisTick(val, digits = 2) {
  if (val == null) return '';
  const num = Number(val);
  if (!Number.isFinite(num)) return '';
  const fixed = num.toFixed(digits);
  // Обрезка хвостовых нулей ДО замены точки на запятую (Р-25: regex завязан
  // на точку из toFixed).
  const cleaned = fixed.replace(/\.?0+$/, '');
  const [intPart, decPart] = cleaned.split('.');
  const sign = intPart.startsWith('-') ? '-' : '';
  const abs = intPart.replace('-', '');
  const grouped = groupThousands(abs);
  return decPart ? `${sign}${grouped},${decPart}` : `${sign}${grouped}`;
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
  'cpi',
  'cpi-food',
  'cpi-nonfood',
  'cpi-services',
  'inflation-quarterly',
  'cpi-food-quarterly',
  'cpi-nonfood-quarterly',
  'cpi-services-quarterly',
  'inflation-weekly',
  'inflation-weekly-food',
  'inflation-weekly-nonfood',
  'inflation-weekly-services',
]);

export function isCpiIndex(code) {
  return CPI_INDEX_CODES.has(code);
}

export function adjustCpiDisplay(value, code) {
  if (value == null || !isFinite(value)) return value;
  if (code !== undefined && !isCpiIndex(code)) return value;
  return +(Number(value) - 100).toFixed(2);
}

export function adjustCpiForecastDisplay(forecastResp, code) {
  if (!isCpiIndex(code) || !forecastResp?.forecast?.values?.length) return forecastResp;
  return {
    ...forecastResp,
    forecast: {
      ...forecastResp.forecast,
      values: forecastResp.forecast.values.map(v => ({
        ...v,
        value: adjustCpiDisplay(v.value, code),
        lower_bound: v.lower_bound == null ? v.lower_bound : adjustCpiDisplay(v.lower_bound, code),
        upper_bound: v.upper_bound == null ? v.upper_bound : adjustCpiDisplay(v.upper_bound, code),
      })),
    },
  };
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
