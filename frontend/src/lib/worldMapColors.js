/**
 * Единственная палитра карты мира и планеты (круг 6, зона G; прежняя «тёплая» золотая шкала снята по принципу владельца
 * «не слишком жёлтый»): холодный лёд #C9D7EA на малых значениях → глубокий синий #1E3A6E на больших, семь равных ступеней
 * (опорные цвета: лёд, средний синий #7C9AC9, глубокий синий). Страна без данных — нейтральная суша #E6E3DC (не синяя и не
 * золотая, не сливается ни со шкалой, ни с океаном), океан — #DCE8F3. Золото `#C9A24D` есть только у страны на первом
 * месте (`isTop`), это не ступень шкалы и в легенду-полосу не входит. Без оценочного смысла «хорошо/плохо».
 *
 * Палитра одна для всех показателей и всех лет. Раньше шкала выбиралась по
 * данным выбранного года: если срез пересекал ноль, включалась отдельная
 * бордово-зелёная гамма — и при перетаскивании ползунка лет карта меняла цвет
 * на том же показателе. Меняется только привязка центра (медиана или ноль),
 * цвета остаются те же.
 */
const WORLD_SCALE_STOPS = ['#C9D7EA', '#7C9AC9', '#1E3A6E'];

function mixHex(a, b, f) {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  return `#${pa.map((v, i) => Math.round(v + (pb[i] - v) * f).toString(16).padStart(2, '0')).join('').toUpperCase()}`;
}

function buildScale(stops, steps) {
  return Array.from({ length: steps }, (_, i) => {
    const pos = (i / (steps - 1)) * (stops.length - 1);
    const lo = Math.floor(pos);
    const hi = Math.min(stops.length - 1, lo + 1);
    return mixHex(stops[lo], stops[hi], pos - lo);
  });
}

export const WORLD_MAP_SCALE = buildScale(WORLD_SCALE_STOPS, 7);

export const WORLD_RELATIVE_SCALE = WORLD_MAP_SCALE;
export const WORLD_DIVERGING_SCALE = WORLD_MAP_SCALE;

// «Нет данных»: нейтральная суша без штриховки.
export const WORLD_NO_DATA = '#E6E3DC';
// Океан карты и шара: холодный лёд.
export const WORLD_OCEAN_COLOR = '#DCE8F3';
// Страна на первом месте списка — единственное золото на карте.
export const WORLD_TOP_COLOR = '#C9A24D';

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

function numericValue(rawValue) {
  if (typeof rawValue !== 'number' && typeof rawValue !== 'string') return null;
  if (typeof rawValue === 'string' && rawValue.trim() === '') return null;
  const value = Number(rawValue);
  return Number.isFinite(value) ? value : null;
}

function numericValues(valuesByCode) {
  const entries = valuesByCode instanceof Map
    ? [...valuesByCode.entries()]
    : Object.entries(valuesByCode || {});
  return entries
    .map(([, value]) => numericValue(value))
    .filter((value) => value !== null)
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
  const value = numericValue(rawValue);
  if (value === null || !values.length) return null;
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

/** Лучшее значение списка: наибольшее, а при порядке «по возрастанию» — наименьшее; одно значение «первого места» не делает. */
function topChecker(values, direction, enabled = true) {
  if (!enabled || values.length < 2) return () => false;
  const best = direction === 'asc' ? values[0] : values[values.length - 1];
  return (rawValue) => numericValue(rawValue) === best;
}

function relativeModel(values, { direction = null, highlightTop = true } = {}) {
  const size = WORLD_RELATIVE_SCALE.length;
  const colorIndexFor = (band) => shiftForDirection(band, direction, size);
  const thresholds = WORLD_RELATIVE_SCALE
    .slice(0, -1)
    .map((_, index) => quantile(values, (index + 1) / WORLD_RELATIVE_SCALE.length));
  const bandFor = (rawValue) => {
    const value = numericValue(rawValue);
    if (value === null) return -1;
    const index = thresholds.findIndex((threshold) => value <= threshold);
    return index === -1 ? WORLD_RELATIVE_SCALE.length - 1 : index;
  };
  return {
    kind: 'relative',
    isTop: topChecker(values, direction, highlightTop),
    hasTop: highlightTop && values.length > 1,
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
      if (index <= 2) return '#4B596F';
      return '#1E3A6E';
    },
    describe: (value) => {
      const band = bandFor(value);
      if (band < 0) return null;
      return { key: RELATIVE_LABELS[band], rank: percentile(values, value) };
    },
  };
}

function divergingModel(values, { direction = null, highlightTop = true } = {}) {
  const size = WORLD_DIVERGING_SCALE.length;
  const colorIndexFor = (band) => shiftForDirection(band, direction, size);
  const maxAbs = Math.max(...values.map(Math.abs), 1);
  const third = maxAbs / 3;
  const twoThirds = third * 2;
  const bandFor = (rawValue) => {
    const value = numericValue(rawValue);
    if (value === null) return -1;
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
    isTop: topChecker(values, direction, highlightTop),
    hasTop: highlightTop && values.length > 1,
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
      if (index <= 2) return '#4B596F';
      return '#1E3A6E';
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
export function buildWorldColorModel(valuesByCode, { mode = 'relative', direction = null, highlightTop = true } = {}) {
  const values = numericValues(valuesByCode);
  if (!values.length) {
    return {
      kind: 'empty',
      isTop: () => false,
      hasTop: false,
      scale: WORLD_RELATIVE_SCALE,
      median: null,
      sampleSize: 0,
      bins: [],
      colorFor: () => WORLD_NO_DATA,
      labelColorFor: () => '#6F746F',
      describe: () => null,
    };
  }
  const options = { direction, highlightTop };
  return mode === 'diverging' ? divergingModel(values, options) : relativeModel(values, options);
}
