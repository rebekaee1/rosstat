/**
 * Единственная палитра карты мира и планеты. История: круг 3 — «лёд → золото» (снята принципом владельца «не слишком жёлтый»);
 * круг 10 — бирюза → синий → индиго, то есть два оттенка одной холодной гаммы, на экране читалась как «всё синее».
 * Круг 12 (звонок «На правки 23», тестер 11.10, слова владельца 12.10: «сине-коричневый градиент»): настоящий двойной градиент,
 * два разных цвета: СИНИЙ на малых значениях и КОРИЧНЕВЫЙ (умбра, не рыжий, не жёлтый, не золотой) на больших, семь ступеней.
 *
 *   ступень   0        1        2        3 (центр) 4        5        6
 *   цвет      #1D3A82  #3F74BB  #7BA2D3  #ADB2BC   #B9957A  #8C5F42  #52311F
 *   Lab L*    26       48       66       72        64       45       24
 *
 * Центр — холодный серый #ADB2BC (медиана в режиме relative, ноль в режиме diverging); от центра в обе стороны цвет темнеет и
 * насыщается: влево до глубокого синего, вправо до тёмной умбры. Центр намеренно темнее «нет данных» и океана, иначе середина
 * сливалась бы с ними. Расчёт (CIEDE2000, контраст WCAG; воспроизводится `python3 scripts/dev/world-map-palette-check.py`):
 *   - центр против океана #DCE8F3: ΔE 13,2, контраст 1,71:1; против «нет данных» #E6E3DC: ΔE 15,0, контраст 1,66:1;
 *     все остальные ступени от них дальше (ΔE ≥ 21,8; контраст ≥ 2,06:1; крайние ступени 8,5–9,3:1);
 *   - соседние ступени различаются на ΔE 14,4–20,9 (порог «ясно разные» около 10); при дальтонизме (протанопия, дейтеранопия,
 *     тританопия, модель Machado 2009, тяжесть 1,0) наименьший шаг между любыми двумя ступенями 13,3 / 15,1 / 14,5, от океана и
 *     суши без данных все ступени ≥ 12,8: пара «синий — коричневый» различима, потому что отличается и тоном, и светлотой;
 *   - коричневый — оттенок 21–26° по HSL при насыщенности 31–46 %: не рыжий (насыщенность за 70 %) и не золото (оттенок 41°, насыщенность 53 %).
 * Какая сторона какая: малые значения синие, большие коричневые (тёплое = больше), ни один из цветов не несёт оценки
 * «хорошо/плохо» (поэтому нет красного и зелёного). Направление сортировки (`direction`) просто переворачивает стороны.
 *
 * Золота на карте нет совсем: страна на первом месте не выделяется (первое место видно в списке справа, на карте это просто
 * самая тёмная ступень со стороны выбранного порядка).
 *
 * Палитра одна для всех показателей и всех лет. Раньше шкала выбиралась по данным выбранного года: если срез пересекал ноль,
 * включалась отдельная бордово-зелёная гамма, и при перетаскивании ползунка лет карта меняла цвет на том же показателе.
 * Меняется только привязка центра (медиана или ноль), цвета остаются те же.
 */
export const WORLD_MAP_SCALE = ['#1D3A82', '#3F74BB', '#7BA2D3', '#ADB2BC', '#B9957A', '#8C5F42', '#52311F'];

// Цвет подписи полосы (подсказка на светлом стекле): чернила своей стороны шкалы, контраст с белым не ниже 4,5:1.
// Индекс — ступень шкалы. Синяя сторона, нейтральный центр, коричневая сторона.
const WORLD_LABEL_INK = ['#1D3A82', '#2F5FA3', '#4B596F', '#4B596F', '#7A4F34', '#6B4229', '#52311F'];

export const WORLD_RELATIVE_SCALE = WORLD_MAP_SCALE;
export const WORLD_DIVERGING_SCALE = WORLD_MAP_SCALE;

// «Нет данных»: нейтральная суша без штриховки.
export const WORLD_NO_DATA = '#E6E3DC';
// Океан карты и шара: холодный лёд.
export const WORLD_OCEAN_COLOR = '#DCE8F3';
// Выбранная страна на плоской карте: светлая «льдина» поверх цвета шкалы и тёмная графитово-синяя кромка (видна и на светлых, и на тёмных ступенях).
export const WORLD_SELECT_FILL = 'rgba(255,255,255,0.4)';
export const WORLD_SELECT_HALO = '#FFFFFF';
export const WORLD_SELECT_INK = '#16264F';

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

function relativeModel(values, { direction = null } = {}) {
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
      return WORLD_LABEL_INK[index];
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
      return WORLD_LABEL_INK[index];
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
