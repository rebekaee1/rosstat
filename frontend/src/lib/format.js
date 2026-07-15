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

/** JetBrains Mono 11px: чуть консервативнее реальной ширины кириллицы. */
const AXIS_PX_PER_CHAR = 6.6;
const AXIS_LABEL_GAP_PX = 12;

/**
 * Оценка ширины подписи оси X в px («7 июля 2025», «I кв. 2024», «2023»).
 * labelOrChars — строка подписи или число символов.
 */
export function estimateAxisLabelWidthPx(labelOrChars) {
  const n = typeof labelOrChars === 'number'
    ? Math.max(0, labelOrChars)
    : String(labelOrChars ?? '').length;
  return Math.max(16, Math.ceil(n * AXIS_PX_PER_CHAR));
}

/**
 * Сколько подписей оси X влезает без наезда.
 * 2-й аргумент: число символов, готовая ширина в px (>40), либо строка-образец
 * («7 июля 2025»). Потолок высокий — плотность режет ширина, не магическая «7».
 */
export function chartAxisTickBudget(plotWidthPx, labelCharsOrSample = 8) {
  const w = Number(plotWidthPx) || 0;
  // SSR / до ResizeObserver — умеренный дефолт; после замера пересчитается.
  if (w <= 0) return 8;

  let labelW;
  let chars;
  if (typeof labelCharsOrSample === 'string') {
    labelW = estimateAxisLabelWidthPx(labelCharsOrSample);
    chars = labelCharsOrSample.length;
  } else if (typeof labelCharsOrSample === 'number' && labelCharsOrSample > 40) {
    // Уже ширина в px (редко; для явной передачи estimateAxisLabelWidthPx).
    labelW = labelCharsOrSample;
    chars = Math.ceil(labelW / AXIS_PX_PER_CHAR);
  } else {
    chars = Number(labelCharsOrSample) || 8;
    labelW = estimateAxisLabelWidthPx(chars);
  }

  const gapPx = chars <= 4 ? 10 : AXIS_LABEL_GAP_PX;
  const perTick = Math.max(28, labelW + gapPx);
  // (N-1)*perTick + labelW ≤ w  →  N ≤ (w - labelW)/perTick + 1
  // Эквивалент floor(w/perTick)+1 при labelW≈perTick-gap; для длинных RU-дат
  // вычитаем половину крайних подписей, чтобы не завышать бюджет.
  const usable = Math.max(0, w - labelW * 0.35);
  return Math.max(2, Math.min(36, Math.floor(usable / perTick) + 1));
}

/**
 * Плотнейший календарный шаг ≤ maxTicks (включая first+last).
 * 1) ceil — максимум подписей без превышения бюджета;
 * 2) если ближайший больший делитель span даёт почти ту же плотность
 *    (не теряем больше одного тика) — берём его, чтобы last-gap = step.
 */
export function densestCalendarStep(span, maxTicks) {
  if (span <= 0) return 1;
  const slots = Math.max(1, maxTicks - 1);
  const minStep = Math.max(1, Math.ceil(span / slots));
  const ceilCount = Math.floor(span / minStep) + 1;
  for (let step = minStep; step <= span; step += 1) {
    if (span % step !== 0) continue;
    const evenCount = span / step + 1;
    if (evenCount >= ceilCount - 1) return step;
    break;
  }
  return minStep;
}

function parseUtcParts(value) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return { year: value, month: 0 };
  }
  const d = new Date(value);
  if (isNaN(d.getTime())) return null;
  return { year: d.getUTCFullYear(), month: d.getUTCMonth() };
}

/**
 * Пересекаются ли подписи на категориальной оси (позиция ∝ индекс в ряду).
 * items: [{ index, label }], maxIndex — последний индекс данных.
 */
export function axisTickLabelsOverlap(items, maxIndex, plotWidthPx, gapPx = AXIS_LABEL_GAP_PX) {
  const w = Number(plotWidthPx) || 0;
  if (w <= 0 || !items?.length || items.length < 2) return false;
  const span = Math.max(1, maxIndex);
  let prevRight = -Infinity;
  for (const it of items) {
    const x = (it.index / span) * w;
    const half = estimateAxisLabelWidthPx(it.label) / 2;
    const left = x - half;
    if (left < prevRight + gapPx) return true;
    prevRight = x + half;
  }
  return false;
}

function buildTickItems(values, indices, formatLabel) {
  return indices.map((index) => ({
    index,
    value: values[index],
    label: formatLabel ? String(formatLabel(values[index]) ?? '') : String(values[index] ?? ''),
  }));
}

function indexStepTicks(values, step) {
  const last = values.length - 1;
  const indices = [0];
  for (let i = step; i < last; i += step) indices.push(i);
  if (indices[indices.length - 1] !== last) indices.push(last);
  return indices;
}

/**
 * Календарные тики annual/quarterly: максимальная плотность без наезда,
 * равный шаг (1y/2y… или 1q/2q/1y…), всегда first+last.
 * Возвращает { values, indices } либо null.
 */
function pickCalendarAlignedTicks(values, maxTicks, cadence) {
  if (!values.length) return { values: [], indices: [] };
  if (values.length <= maxTicks) {
    return {
      values: [...values],
      indices: values.map((_, i) => i),
    };
  }

  const first = values[0];
  const last = values[values.length - 1];
  const a = parseUtcParts(first);
  const b = parseUtcParts(last);
  if (!a || !b) return null;

  const valueIndex = new Map();
  values.forEach((v, i) => {
    if (!valueIndex.has(v)) valueIndex.set(v, i);
  });

  if (cadence === 'annual') {
    const span = b.year - a.year;
    if (span <= 0) {
      return { values: [first, last], indices: [0, values.length - 1] };
    }
    const step = densestCalendarStep(span, maxTicks);
    const byYear = new Map();
    for (const v of values) {
      const p = parseUtcParts(v);
      if (p && !byYear.has(p.year)) byYear.set(p.year, v);
    }
    const ticks = [first];
    for (let y = a.year + step; y < b.year; y += step) {
      const hit = byYear.get(y);
      if (hit != null) ticks.push(hit);
    }
    if (ticks[ticks.length - 1] !== last) ticks.push(last);
    return {
      values: ticks,
      indices: ticks.map((v) => valueIndex.get(v)),
    };
  }

  // quarterly: шаг в кварталах
  const toQ = (p) => p.year * 4 + Math.floor(p.month / 3);
  const q0 = toQ(a);
  const q1 = toQ(b);
  const span = q1 - q0;
  if (span <= 0) {
    return { values: [first, last], indices: [0, values.length - 1] };
  }
  const step = densestCalendarStep(span, maxTicks);
  const byQ = new Map();
  for (const v of values) {
    const p = parseUtcParts(v);
    if (!p) continue;
    const q = toQ(p);
    if (!byQ.has(q)) byQ.set(q, v);
  }
  const ticks = [first];
  for (let q = q0 + step; q < q1; q += step) {
    const hit = byQ.get(q);
    if (hit != null) ticks.push(hit);
  }
  if (ticks[ticks.length - 1] !== last) ticks.push(last);
  return {
    values: ticks,
    indices: ticks.map((v) => valueIndex.get(v)),
  };
}

/**
 * Равный шаг по индексу (daily/weekly/monthly): densestCalendarStep на span точек.
 */
function pickIndexAlignedTicks(values, maxTicks) {
  if (!values.length) return { values: [], indices: [] };
  if (values.length <= maxTicks) {
    return {
      values: [...values],
      indices: values.map((_, i) => i),
    };
  }
  const span = values.length - 1;
  const step = densestCalendarStep(span, maxTicks);
  const indices = indexStepTicks(values, step);
  return {
    values: indices.map((i) => values[i]),
    indices,
  };
}

/**
 * Ужимаем maxTicks, пока подписи не перестанут наезжать (plotWidth + formatLabel).
 * Предпочитаем календарный/index-aligned шаг; всегда first+last, если влезают.
 */
function fitTicksNoOverlap(values, maxTicks, cadence, plotWidthPx, formatLabel) {
  const maxIndex = values.length - 1;
  if (maxIndex < 0) return [];
  if (maxIndex === 0) return [values[0]];

  const tryBudget = (budget) => {
    if (cadence === 'annual' || cadence === 'quarterly') {
      return pickCalendarAlignedTicks(values, budget, cadence);
    }
    return pickIndexAlignedTicks(values, budget);
  };

  // Верхняя оценка по самой длинной подписи в окне (не по среднему).
  let budget = Math.max(2, maxTicks);
  if (plotWidthPx > 0 && formatLabel) {
    let longest = '';
    const stride = Math.max(1, Math.floor(values.length / 48));
    for (let i = 0; i < values.length; i += stride) {
      const s = String(formatLabel(values[i]) ?? '');
      if (s.length > longest.length) longest = s;
    }
    const tail = String(formatLabel(values[maxIndex]) ?? '');
    if (tail.length > longest.length) longest = tail;
    budget = Math.min(budget, chartAxisTickBudget(plotWidthPx, longest || 8));
  }

  for (let b = budget; b >= 2; b -= 1) {
    const picked = tryBudget(b);
    if (!picked) continue;
    if (!(plotWidthPx > 0 && formatLabel)) return picked.values;
    const items = buildTickItems(values, picked.indices, formatLabel);
    if (!axisTickLabelsOverlap(items, maxIndex, plotWidthPx)) return picked.values;
  }

  // Крайний случай: только first+last, если они не наезжают; иначе — оба всё равно
  // (иначе ось без якорей), вызывающий код уже сузил окно.
  return [values[0], values[maxIndex]];
}

/**
 * Подписи оси X: плотнейший набор без наезда, всегда first+last.
 * cadence: 'annual' | 'quarterly' — календарный шаг; иначе равный шаг по индексу
 * (daily/weekly/плотный monthly).
 * options: { dateKey, cadence, plotWidthPx, formatLabel }.
 * 3-й аргумент — dateKey (строка) или options.
 */
export function pickChartAxisTicks(points, maxTicks = 7, dateKeyOrOptions = 'date') {
  if (!points?.length) return [];
  const opts = typeof dateKeyOrOptions === 'object' && dateKeyOrOptions != null
    ? dateKeyOrOptions
    : { dateKey: dateKeyOrOptions };
  const dateKey = opts.dateKey ?? 'date';
  const cadence = opts.cadence ?? null;
  const plotWidthPx = Number(opts.plotWidthPx) || 0;
  const formatLabel = typeof opts.formatLabel === 'function' ? opts.formatLabel : null;
  const get = (p) => (dateKey === 'date' ? p.date : p[dateKey]);
  const values = points.map(get);

  if (plotWidthPx > 0 && formatLabel) {
    return fitTicksNoOverlap(values, maxTicks, cadence, plotWidthPx, formatLabel);
  }

  if (cadence === 'annual' || cadence === 'quarterly') {
    const calendar = pickCalendarAlignedTicks(values, maxTicks, cadence);
    if (calendar) return calendar.values;
  }

  if (points.length <= maxTicks) return values;
  // Без plotWidth — прежнее равномерное index-sampling (SSR / legacy callers).
  const ticks = [values[0]];
  const step = (points.length - 1) / (maxTicks - 1);
  for (let i = 1; i < maxTicks - 1; i += 1) {
    const idx = Math.round(i * step);
    const date = values[idx];
    if (ticks[ticks.length - 1] !== date) ticks.push(date);
  }
  const last = values[values.length - 1];
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
  // Обрезаем только дробный хвост `.0+` (Р-25). Без точки `\.?0+$` съедал
  // нули целой части: digits=0 → 15000.toFixed(0)="15000" → "15".
  const cleaned = fixed.includes('.')
    ? fixed.replace(/\.?0+$/, '')
    : fixed;
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
