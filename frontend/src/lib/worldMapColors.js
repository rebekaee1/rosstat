// Двусторонняя rank-шкала без оценочного смысла «хорошо/плохо»:
// холодные тона = ниже медианы, светлый центр = около медианы,
// фирменные золотые тона = выше медианы.
export const WORLD_RELATIVE_SCALE = [
  '#315A7D',
  '#648DAA',
  '#AFC8D7',
  '#EEE9DC',
  '#E3C486',
  '#C68D3D',
  '#87591F',
];

export const WORLD_DIVERGING_SCALE = [
  '#7B293B',
  '#B55262',
  '#D99A9E',
  '#F1EADD',
  '#9CCABC',
  '#4B9485',
  '#1B6259',
];

export const WORLD_NO_DATA = '#E5E7E5';

const RELATIVE_LABELS = [
  'Нижние 15% стран',
  'Заметно ниже медианы',
  'Ниже медианы',
  'Около медианы',
  'Выше медианы',
  'Заметно выше медианы',
  'Верхние 15% стран',
];

const DIVERGING_LABELS = [
  'Сильно ниже нуля',
  'Умеренно ниже нуля',
  'Ниже нуля · близко к нулю',
  'Около нуля',
  'Выше нуля · близко к нулю',
  'Умеренно выше нуля',
  'Сильно выше нуля',
];

function numericValues(valuesByCode) {
  const entries = valuesByCode instanceof Map
    ? [...valuesByCode.entries()]
    : Object.entries(valuesByCode || {});
  return entries
    .map(([, value]) => Number(value))
    .filter(Number.isFinite)
    .sort((a, b) => a - b);
}

function quantile(sorted, share) {
  if (!sorted.length) return null;
  return sorted[Math.min(
    sorted.length - 1,
    Math.max(0, Math.ceil(share * sorted.length) - 1),
  )];
}

function percentile(values, rawValue) {
  const value = Number(rawValue);
  if (!Number.isFinite(value) || !values.length) return null;
  let first = values.findIndex((item) => item >= value);
  if (first === -1) first = values.length;
  let last = first;
  while (last < values.length && values[last] === value) last += 1;
  const midpointRank = first + (last - first) / 2;
  return Math.max(1, Math.min(99, Math.round((midpointRank / values.length) * 100)));
}

function relativeModel(values) {
  const thresholds = WORLD_RELATIVE_SCALE
    .slice(0, -1)
    .map((_, index) => quantile(values, (index + 1) / WORLD_RELATIVE_SCALE.length));
  const bandFor = (rawValue) => {
    if (rawValue == null || rawValue === '') return -1;
    const value = Number(rawValue);
    if (!Number.isFinite(value)) return -1;
    const index = thresholds.findIndex((threshold) => value <= threshold);
    return index === -1 ? WORLD_RELATIVE_SCALE.length - 1 : index;
  };
  return {
    kind: 'relative',
    scale: WORLD_RELATIVE_SCALE,
    median: quantile(values, 0.5),
    sampleSize: values.length,
    bins: WORLD_RELATIVE_SCALE.map((color, index) => ({
      color,
      min: index === 0 ? null : thresholds[index - 1],
      max: index === WORLD_RELATIVE_SCALE.length - 1 ? null : thresholds[index],
      label: RELATIVE_LABELS[index],
    })),
    colorFor: (value) => {
      const band = bandFor(value);
      return band < 0 ? WORLD_NO_DATA : WORLD_RELATIVE_SCALE[band];
    },
    labelColorFor: (value) => {
      const band = bandFor(value);
      if (band < 0) return '#6F746F';
      if (band <= 2) return '#315A7D';
      if (band >= 4) return '#87591F';
      return '#6F685A';
    },
    describe: (value) => {
      const band = bandFor(value);
      if (band < 0) return '';
      const rank = percentile(values, value);
      return `${RELATIVE_LABELS[band]} · ${rank}-й процентиль`;
    },
  };
}

function divergingModel(values) {
  const maxAbs = Math.max(...values.map(Math.abs), 1);
  const third = maxAbs / 3;
  const twoThirds = third * 2;
  const bandFor = (rawValue) => {
    if (rawValue == null || rawValue === '') return -1;
    const value = Number(rawValue);
    if (!Number.isFinite(value)) return -1;
    if (value <= -twoThirds) return 0;
    if (value <= -third) return 1;
    if (value < 0) return 2;
    if (value === 0) return 3;
    if (value < third) return 4;
    if (value < twoThirds) return 5;
    return 6;
  };
  return {
    kind: 'diverging',
    scale: WORLD_DIVERGING_SCALE,
    median: quantile(values, 0.5),
    sampleSize: values.length,
    bins: [
      { color: WORLD_DIVERGING_SCALE[0], min: null, max: -twoThirds, label: DIVERGING_LABELS[0] },
      { color: WORLD_DIVERGING_SCALE[1], min: -twoThirds, max: -third, label: DIVERGING_LABELS[1] },
      { color: WORLD_DIVERGING_SCALE[2], min: -third, max: 0, label: DIVERGING_LABELS[2] },
      { color: WORLD_DIVERGING_SCALE[3], min: 0, max: 0, zero: true, label: DIVERGING_LABELS[3] },
      { color: WORLD_DIVERGING_SCALE[4], min: 0, max: third, label: DIVERGING_LABELS[4] },
      { color: WORLD_DIVERGING_SCALE[5], min: third, max: twoThirds, label: DIVERGING_LABELS[5] },
      { color: WORLD_DIVERGING_SCALE[6], min: twoThirds, max: null, label: DIVERGING_LABELS[6] },
    ],
    colorFor: (value) => {
      const band = bandFor(value);
      return band < 0 ? WORLD_NO_DATA : WORLD_DIVERGING_SCALE[band];
    },
    labelColorFor: (value) => {
      const band = bandFor(value);
      if (band < 0) return '#6F746F';
      if (band <= 2) return '#8A3345';
      if (band >= 4) return '#1E655D';
      return '#6F685A';
    },
    describe: (value) => {
      const band = bandFor(value);
      return band < 0 ? '' : DIVERGING_LABELS[band];
    },
  };
}

/**
 * Для обычных показателей цвет показывает квантиль среди стран выбранного года.
 * Если срез пересекает ноль, шкала становится дивергентной: знак нельзя прятать
 * в одном последовательном градиенте.
 */
export function buildWorldColorModel(valuesByCode, { mode = 'auto' } = {}) {
  const values = numericValues(valuesByCode);
  if (!values.length) {
    return {
      kind: 'empty',
      scale: WORLD_RELATIVE_SCALE,
      median: null,
      sampleSize: 0,
      bins: [],
      colorFor: () => WORLD_NO_DATA,
      labelColorFor: () => '#6F746F',
      describe: () => '',
    };
  }
  return mode === 'diverging' || (values[0] < 0 && values.at(-1) > 0)
    ? divergingModel(values)
    : relativeModel(values);
}
