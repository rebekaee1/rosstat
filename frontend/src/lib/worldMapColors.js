/**
 * Единственная палитра карты мира: холодные синие тона на одном конце,
 * фирменные золотисто-коричневые на другом, светлый центр посередине.
 * Без оценочного смысла «хорошо/плохо».
 *
 * Палитра одна для всех показателей и всех лет. Раньше шкала выбиралась по
 * данным выбранного года: если срез пересекал ноль, включалась отдельная
 * бордово-зелёная гамма — и при перетаскивании ползунка лет карта меняла цвет
 * на том же показателе. Меняется только привязка центра (медиана или ноль),
 * цвета остаются те же.
 */
export const WORLD_MAP_SCALE = [
  '#315A7D',
  '#648DAA',
  '#AFC8D7',
  '#EEE9DC',
  '#E3C486',
  '#C68D3D',
  '#87591F',
];

export const WORLD_RELATIVE_SCALE = WORLD_MAP_SCALE;
export const WORLD_DIVERGING_SCALE = WORLD_MAP_SCALE;

export const WORLD_NO_DATA = '#E5E7E5';

// Модуль остаётся без текстов: подписи полос живут в словарях, иначе
// англоязычная версия карты показывала бы русскую легенду.
const RELATIVE_LABELS = [
  'world.map.band.rel0',
  'world.map.band.rel1',
  'world.map.band.rel2',
  'world.map.band.rel3',
  'world.map.band.rel4',
  'world.map.band.rel5',
  'world.map.band.rel6',
];

const DIVERGING_LABELS = [
  'world.map.band.zero0',
  'world.map.band.zero1',
  'world.map.band.zero2',
  'world.map.band.zero3',
  'world.map.band.zero4',
  'world.map.band.zero5',
  'world.map.band.zero6',
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

function shiftForDirection(band, direction, size) {
  // Инверсия шкалы: при порядке «по возрастанию» лучшими становятся малые
  // значения, поэтому они получают насыщенный край палитры, а крупные —
  // противоположный. Направление не задано — привязка по возрастанию значения.
  return direction === 'asc' ? size - 1 - band : band;
}

function relativeModel(values, { direction = null } = {}) {
  const size = WORLD_RELATIVE_SCALE.length;
  const colorIndexFor = (band) => shiftForDirection(band, direction, size);
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
    bins: WORLD_RELATIVE_SCALE.map((_, index) => ({
      color: WORLD_RELATIVE_SCALE[colorIndexFor(index)],
      min: index === 0 ? null : thresholds[index - 1],
      max: index === WORLD_RELATIVE_SCALE.length - 1 ? null : thresholds[index],
      labelKey: RELATIVE_LABELS[index],
    })),
    colorFor: (value) => {
      const band = bandFor(value);
      return band < 0 ? WORLD_NO_DATA : WORLD_RELATIVE_SCALE[colorIndexFor(band)];
    },
    labelColorFor: (value) => {
      const band = bandFor(value);
      if (band < 0) return '#6F746F';
      const index = colorIndexFor(band);
      if (index <= 2) return '#315A7D';
      if (index >= 4) return '#87591F';
      return '#6F685A';
    },
    describe: (value) => {
      const band = bandFor(value);
      if (band < 0) return null;
      return { key: RELATIVE_LABELS[band], rank: percentile(values, value) };
    },
  };
}

function divergingModel(values, { direction = null } = {}) {
  const size = WORLD_DIVERGING_SCALE.length;
  const colorIndexFor = (band) => shiftForDirection(band, direction, size);
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
      { color: WORLD_DIVERGING_SCALE[colorIndexFor(0)], min: null, max: -twoThirds, labelKey: DIVERGING_LABELS[0] },
      { color: WORLD_DIVERGING_SCALE[colorIndexFor(1)], min: -twoThirds, max: -third, labelKey: DIVERGING_LABELS[1] },
      { color: WORLD_DIVERGING_SCALE[colorIndexFor(2)], min: -third, max: 0, labelKey: DIVERGING_LABELS[2] },
      { color: WORLD_DIVERGING_SCALE[colorIndexFor(3)], min: 0, max: 0, zero: true, labelKey: DIVERGING_LABELS[3] },
      { color: WORLD_DIVERGING_SCALE[colorIndexFor(4)], min: 0, max: third, labelKey: DIVERGING_LABELS[4] },
      { color: WORLD_DIVERGING_SCALE[colorIndexFor(5)], min: third, max: twoThirds, labelKey: DIVERGING_LABELS[5] },
      { color: WORLD_DIVERGING_SCALE[colorIndexFor(6)], min: twoThirds, max: null, labelKey: DIVERGING_LABELS[6] },
    ],
    colorFor: (value) => {
      const band = bandFor(value);
      return band < 0 ? WORLD_NO_DATA : WORLD_DIVERGING_SCALE[colorIndexFor(band)];
    },
    labelColorFor: (value) => {
      const band = bandFor(value);
      if (band < 0) return '#6F746F';
      const index = colorIndexFor(band);
      if (index <= 2) return '#315A7D';
      if (index >= 4) return '#87591F';
      return '#6F685A';
    },
    describe: (value) => {
      const band = bandFor(value);
      return band < 0 ? null : { key: DIVERGING_LABELS[band], rank: null };
    },
  };
}

/**
 * Привязка центра шкалы задаётся показателем, а не данными года:
 * `relative` — центр по медиане стран, `diverging` — центр по нулю (для
 * показателей, где знак содержателен: сальдо бюджета, приток капитала).
 * Выбор по значениям убран намеренно — он «перекрашивал» карту между годами.
 *
 * `direction` привязывает шкалу к смыслу текущей сортировки: `desc` —
 * насыщенный край палитры у максимальных значений (по умолчанию), `asc` —
 * у минимальных. Так переключение порядка в таблице переворачивает раскраску
 * карты: лидер нового порядка всегда акцентный, антилидер — бледный.
 */
export function buildWorldColorModel(valuesByCode, { mode = 'relative', direction = null } = {}) {
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
      describe: () => null,
    };
  }
  const options = { direction };
  return mode === 'diverging' ? divergingModel(values, options) : relativeModel(values, options);
}
