// Единая тема графиков: оси, сетка, шрифт, палитра, подсказка, высота по ширине.
// Данные имеют фиксированную семантику: наблюдения = ink, прогноз = пунктир champagne,
// сравнения = холодный slate. Страницы не пишут hex/rgba в разметке графика — берут отсюда.
//
// Контраст подписей осей: #59697F на белой карточке графика 5,6:1, на фоне страницы
// (#EEF0F4) 4,9:1 — оба выше порога 4,5:1 для текста.
export const CHART_THEME = Object.freeze({
  ink: '#202A3C',
  champagne: '#AD8A48',
  // Тёмный оттенок акцента для ТЕКСТА (на белом 5,5:1); champagne — только для линий и заливок.
  champagneInk: '#80642F',
  blue: '#6B8299',
  ice: '#CAD8E5',
  pearl: '#EEF0F4',
  surface: '#FFFFFF',
  grid: 'rgba(32,42,60,0.09)',
  axis: '#59697F',
  axisLine: 'rgba(32,42,60,0.18)',
  refLine: 'rgba(32,42,60,0.32)',
  cursor: 'rgba(32,42,60,0.24)',
  font: 'Manrope, system-ui, sans-serif',
  tickSize: 11,
  // До 10 различимых цветов для рядов «Сравнения»; первый — ink, второй — champagne.
  series: Object.freeze([
    '#202A3C', '#AD8A48', '#6B8299', '#5D857F', '#957D9C',
    '#A86F65', '#818754', '#59677D', '#987B68', '#708B9E',
  ]),
});

/** Стиль подписи оси для `tick={...}` Recharts. */
export function axisTick(overrides = {}) {
  return {
    fill: CHART_THEME.axis,
    fontSize: CHART_THEME.tickSize,
    fontFamily: CHART_THEME.font,
    ...overrides,
  };
}

/** Общие свойства `<CartesianGrid>`: пунктир, только горизонтальные линии. */
export const GRID_PROPS = Object.freeze({
  strokeDasharray: '3 3',
  stroke: CHART_THEME.grid,
  vertical: false,
});

/** Свойства линии оси (`axisLine`) и подписи вдоль неё. */
export const AXIS_LINE = Object.freeze({ stroke: CHART_THEME.axisLine });

/** Подпись опорной линии (ReferenceLine label): тот же шрифт и контраст, что у осей. */
export function refLabel(value, position = 'insideTopRight') {
  return {
    value,
    position,
    fill: CHART_THEME.axis,
    fontSize: CHART_THEME.tickSize,
    fontFamily: CHART_THEME.font,
  };
}

/**
 * Внешний вид стандартной подсказки Recharts (где свой контент не нужен):
 * тот же шрифт, рамка и радиус, что у собственных подсказок страниц.
 */
export const TOOLTIP_STYLES = Object.freeze({
  contentStyle: Object.freeze({
    fontFamily: CHART_THEME.font,
    fontSize: 12,
    color: CHART_THEME.ink,
    background: CHART_THEME.surface,
    border: '1px solid rgba(68,87,115,0.18)',
    borderRadius: 12,
    boxShadow: '0 12px 32px -18px rgba(38,52,78,0.45)',
    padding: '10px 12px',
  }),
  labelStyle: Object.freeze({ color: CHART_THEME.axis, fontWeight: 600, marginBottom: 4 }),
  itemStyle: Object.freeze({ color: CHART_THEME.ink, padding: '1px 0' }),
  cursor: Object.freeze({ stroke: CHART_THEME.cursor, strokeWidth: 1 }),
});

/**
 * Высота графика по ширине его контейнера: 280 (телефон) / 390 (планшет) / 480 (компьютер).
 * Пороги подобраны под ширину внешней карточки; пока ширина неизвестна (SSR, первый кадр)
 * берётся средняя — скелетон и график используют одну и ту же функцию, поэтому не прыгают.
 */
export const CHART_HEIGHTS = Object.freeze({ compact: 280, medium: 390, wide: 480 });

export function chartHeightForWidth(width) {
  const w = Number(width);
  if (!Number.isFinite(w) || w <= 0) return CHART_HEIGHTS.medium;
  if (w < 560) return CHART_HEIGHTS.compact;
  if (w < 900) return CHART_HEIGHTS.medium;
  return CHART_HEIGHTS.wide;
}

/** Ширина, при которой график считается «узким»: подписи и оси ужимаются, лишние надписи прячутся. */
export const NARROW_CHART_WIDTH = 420;

/**
 * Ширина оси Y под самую длинную подпись. Подпись прижата к правому краю оси, поэтому ширина
 * считается по числу знаков (цифра ≈ 6,6 px при шрифте 11) плюс запас: подпись не режется слева,
 * ось просто становится шире.
 */
export function axisWidthForLabels(labels, { min = 36, max = 110, perChar = 7, pad = 10 } = {}) {
  const longest = (labels || []).reduce((n, label) => Math.max(n, String(label ?? '').length), 0);
  return Math.max(min, Math.min(max, Math.round(longest * perChar) + pad));
}

/**
 * Значения-образцы для расчёта ширины оси: края данных плюс запас 10 % на «красивый» домен,
 * который Recharts достраивает за пределы данных («355 000» → «400 000», «999» → «1 000»).
 */
export function axisSampleValues(values) {
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values || []) {
    const n = Number(v);
    if (!Number.isFinite(n)) continue;
    if (n < lo) lo = n;
    if (n > hi) hi = n;
  }
  if (!Number.isFinite(lo)) return [];
  const pad = (Math.abs(hi - lo) || Math.abs(hi) || 1) * 0.1;
  return [lo - pad, hi + pad, lo, hi];
}

/**
 * «Ровная» ось Y: шаг только 1, 2 или 5 × 10^k, границы кратны шагу. Автодомен Recharts
 * иногда даёт шаг вроде 55 000 («3 190 000 / 3 245 000 / 3 300 000») — читается как рваный.
 * Возвращает { domain: [lo, hi], ticks } либо null, если данных нет.
 */
export function niceAxis(values, tickCount = 5) {
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values || []) {
    if (v == null) continue;
    const n = Number(v);
    if (!Number.isFinite(n)) continue;
    if (n < lo) lo = n;
    if (n > hi) hi = n;
  }
  if (!Number.isFinite(lo)) return null;
  if (lo === hi) {
    const pad = Math.abs(lo) * 0.05 || 1;
    lo -= pad;
    hi += pad;
  }
  const raw = (hi - lo) / Math.max(1, tickCount - 1);
  const pow = 10 ** Math.floor(Math.log10(raw));
  const frac = raw / pow;
  const step = (frac <= 1 ? 1 : frac <= 2 ? 2 : frac <= 5 ? 5 : 10) * pow;
  const start = Math.floor(lo / step + 1e-9) * step;
  const end = Math.ceil(hi / step - 1e-9) * step;
  const ticks = [];
  for (let v = start, i = 0; v <= end + step * 1e-6 && i < 20; v += step, i += 1) {
    ticks.push(Math.abs(v) < step * 1e-9 ? 0 : Number(v.toPrecision(12)));
  }
  return { domain: [ticks[0], ticks[ticks.length - 1]], ticks };
}
