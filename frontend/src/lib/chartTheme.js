// Единая тема графиков: оси, сетка, шрифт, палитра, подсказка, высота по ширине.
// Раунд 2 (DS7): основная линия графика золотая (`gold`), заливка под ней золото 30 % → 0, прогноз — пунктир ink,
// сравнения — единая палитра `series` (золото, графит, затем спокойные приглушённые цвета).
// Страницы не пишут hex/rgba в разметке графика — берут отсюда.
//
// Контраст подписей осей: #566379 на белой карточке графика 6,1:1, на фоне страницы
// (#F6F2EA) 5,4:1 — оба выше порога 4,5:1 для текста.
export const CHART_THEME = Object.freeze({
  ink: '#202A3C',
  // Основное золото линий и заливок (не для мелкого текста: контраст на белом 3,2:1).
  gold: '#B08A3E',
  goldBright: '#C9A24D',
  champagne: '#AD8A48',
  // Тёмный оттенок акцента для ТЕКСТА (на белом 6,0:1); champagne и gold — только для линий и заливок.
  champagneInk: '#7A5F2A',
  blue: '#6B8299',
  ice: '#CAD8E5',
  pearl: '#F6F2EA',
  surface: '#FFFFFF',
  grid: 'rgba(32,42,60,0.09)',
  axis: '#566379',
  axisLine: 'rgba(32,42,60,0.18)',
  refLine: 'rgba(32,42,60,0.32)',
  cursor: 'rgba(176,138,62,0.6)',
  font: 'Manrope, system-ui, sans-serif',
  // Оси читаются: 12 px (было 11).
  tickSize: 12,
  // До 10 различимых цветов для рядов «Сравнения»; первый — золото, второй — графит.
  series: Object.freeze([
    '#B08A3E', '#202A3C', '#5E86A8', '#4F8A7B', '#8E6FA0',
    '#B5675B', '#7E8A4B', '#5A6A86', '#A27B5C', '#6C93A8',
  ]),
});

/** Основная линия: золото 2,75 px со скруглёнными концами (DS7 просит 2,5–3 px). */
export const CHART_LINE = Object.freeze({
  stroke: CHART_THEME.gold,
  strokeWidth: 2.75,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
});

/** Заливка под линией: у линии 30 %, к оси 2 % (в диапазоне 12–35 % из DS7). */
export const CHART_AREA = Object.freeze({ top: 0.3, bottom: 0.02 });

/** Стопы градиента заливки для `<linearGradient>`: `areaGradientStops().map(...)`. Цвет по умолчанию — золото. */
export function areaGradientStops(color = CHART_THEME.gold, { top = CHART_AREA.top, bottom = CHART_AREA.bottom } = {}) {
  return [
    { offset: '0%', stopColor: color, stopOpacity: top },
    { offset: '100%', stopColor: color, stopOpacity: bottom },
  ];
}

/** Движение графика: линия рисуется слева направо 700 мс, смена серии плавная. Для `animationDuration` Recharts. */
export const CHART_MOTION = Object.freeze({
  drawMs: 700,
  switchMs: 450,
  easing: 'ease-out',
});

/**
 * Плашка с последним значением справа от линии («28,1 млн»): размеры под текст.
 * Ширина считается по числу знаков (цифра ≈ 0,58 em), поэтому плашка не режет подпись и не налезает на линию:
 * сдвиньте её на `gap` вправо от точки.
 */
export function lastPointTag(text, { fontSize = 12, padX = 8, height = 22, gap = 10 } = {}) {
  const chars = String(text ?? '').length;
  const width = Math.max(height, Math.ceil(chars * fontSize * 0.6) + padX * 2);
  return { width, height, radius: height / 2, gap, fontSize, padX };
}

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
 * тот же шрифт, стекло без рамки и радиус, что у собственных подсказок страниц.
 */
export const TOOLTIP_STYLES = Object.freeze({
  // Стеклянная плашка (слой L2): полупрозрачная белая с размытием фона, блик сверху и тень снизу, без рамки.
  contentStyle: Object.freeze({
    fontFamily: CHART_THEME.font,
    fontSize: 13,
    color: CHART_THEME.ink,
    background: 'rgba(255,255,255,0.78)',
    backdropFilter: 'blur(14px) saturate(1.25)',
    border: 0,
    borderRadius: 14,
    boxShadow: '0 14px 34px -20px rgba(60,48,24,0.5), inset 0 1px 0 rgba(255,255,255,0.85)',
    padding: '10px 12px',
  }),
  labelStyle: Object.freeze({ color: CHART_THEME.axis, fontWeight: 600, marginBottom: 4 }),
  itemStyle: Object.freeze({ color: CHART_THEME.ink, padding: '1px 0' }),
  // Вертикальная золотая линия под курсором.
  cursor: Object.freeze({ stroke: CHART_THEME.cursor, strokeWidth: 1 }),
});

/** Базовые настройки ECharts (BI и сложные диаграммы): та же палитра, шрифт и стеклянная подсказка. */
export const ECHART_BASE = Object.freeze({
  color: CHART_THEME.series,
  textStyle: Object.freeze({ fontFamily: CHART_THEME.font, color: CHART_THEME.axis }),
  tooltip: Object.freeze({
    backgroundColor: 'rgba(255,255,255,0.82)',
    borderColor: 'transparent',
    borderWidth: 0,
    padding: [10, 12],
    textStyle: Object.freeze({ color: CHART_THEME.ink, fontFamily: CHART_THEME.font, fontSize: 13 }),
    extraCssText: 'border-radius:14px;box-shadow:0 14px 34px -20px rgba(60,48,24,.5),inset 0 1px 0 rgba(255,255,255,.85);backdrop-filter:blur(14px) saturate(1.25);',
  }),
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
export function axisWidthForLabels(labels, { min = 36, max = 110, perChar = 7.6, pad = 10 } = {}) {
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
