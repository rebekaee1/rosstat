// Единая тема графиков: оси, сетка, шрифт, палитра, подсказка, высота по ширине.
// Круг 6: основная линия (факт) — холодная синяя лента (поля gold* сохранили имена, значения теперь синие), прогноз — золото (`forecast*`),
// сравнения — единая палитра `series`.
// Раунд 3 (K4, «хрусталь без границ»): заливка уходит к оси 0, сетка — чередование полос без пунктира, второй ряд — сапфир.
// Круг 10 (Г1, звонок 08.10): линия и область одного цвета, без градиента по длине, без блика-штриха и без смещённой тени
// (раньше они читались как «две линии»); прогноз — тонкая линия сплошного цвета. Диапазона прогноза на графике нет: только линия.
// Градиенты (теперь из одинаковых остановок) рисует components/ChartGlassDefs.jsx по этим же значениям.
// Страницы не пишут hex/rgba в разметке графика — берут отсюда.
//
// Контраст подписей осей: #55627A на белой карточке графика 6,1:1, на фоне страницы
// (#F4F5F7) 5,6:1 — оба выше порога 4,5:1 для текста.
export const CHART_THEME = Object.freeze({
  ink: '#202A3C',
  // Основное золото линий и заливок (не для мелкого текста: контраст на белом 3,2:1).
  gold: '#2C4A8A',
  goldBright: '#4F78B8',
  champagne: '#3D5F9E',
  // Прогноз: золото (тонкая линия и точка), текст прогноза — тёмное золото.
  forecast: '#B08A3E',
  forecastInk: '#80642F',
  // Тёмный оттенок акцента для ТЕКСТА (на белом 6,0:1); champagne и gold — только для линий и заливок.
  champagneInk: '#1E3A6E',
  blue: '#6B8299',
  ice: '#CAD8E5',
  pearl: '#F4F5F7',
  surface: '#FFFFFF',
  grid: 'rgba(32,42,60,0.09)',
  axis: '#55627A',
  axisLine: 'rgba(32,42,60,0.18)',
  refLine: 'rgba(32,42,60,0.32)',
  cursor: 'rgba(44,74,138,0.5)',
  // Светлое и тёмное золото ленты: градиент по длине линии идёт goldLight → goldBright → goldDeep.
  goldLight: '#9DB6DD',
  goldDeep: '#1E3A6E',
  // Второй ряд: графитово-сланцевая лента (светлый → тёмный); имя sapphire прежнее.
  sapphire: '#46526B',
  sapphireLight: '#8A96AD',
  sapphireDeep: '#1E2638',
  font: 'Manrope, system-ui, sans-serif',
  // Оси читаются: 12 px (было 11).
  tickSize: 12,
  // Чередующиеся полосы сетки (3 % холодного графита, края размыты в k4-charts.css) вместо пунктирных линий.
  gridBand: 'rgba(30,38,56,0.03)',
  // До 10 различимых цветов для рядов «Сравнения»; первый — золото, второй — графит.
  series: Object.freeze([
    '#2C4A8A', '#202A3C', '#5E86A8', '#4F8A7B', '#8E6FA0',
    '#B5675B', '#7E8A4B', '#5A6A86', '#A27B5C', '#6C93A8',
  ]),
});

/**
 * Круг 8 (C1): цвета рядов «Сравнения». Один источник на линию, легенду, точку на конце, заливку, подсказку и карточки.
 * Первый ряд — глубокий синий, второй — бирюза (заметно светлее и в другой тон: синий и графит почти не различались),
 * дальше цвета общей палитры без повторов. Золото в рядах не участвует.
 */
export const COMPARE_COLORS = Object.freeze([
  '#2C4A8A', '#238F9B', ...CHART_THEME.series.slice(2), CHART_THEME.series[1],
]);

/** Смешивает цвет #RRGGBB с белым: amount 0 — исходный цвет, 1 — белый. */
export function mixWithWhite(hex, amount = 0.3) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || ''));
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  const k = Math.max(0, Math.min(1, amount));
  const ch = (v) => Math.round(v + (255 - v) * k).toString(16).padStart(2, '0');
  return `#${ch((n >> 16) & 255)}${ch((n >> 8) & 255)}${ch(n & 255)}`.toUpperCase();
}

/**
 * Остановки «ленты» ряда по длине линии. Круг 10 (Г1): цвет один на всю длину (раньше светлее слева, и линия с областью
 * под ней читались как две разные линии). Функция сохранена, чтобы графики, строящие градиент из цвета ряда, не менялись.
 */
export function ribbonStopsFor(color) {
  return [
    { offset: '0%', color },
    { offset: '100%', color },
  ];
}

/** Основная линия: сплошной цвет 2,5 px со скруглёнными концами (круг 10, Г1: без градиента и блика). */
export const CHART_LINE = Object.freeze({
  stroke: CHART_THEME.gold,
  strokeWidth: 2.5,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
});

/** Заливка под линией: у линии 20 % того же цвета, что и линия, к оси 0 (круг 10, Г1: один цвет, а не светлая подложка). */
export const CHART_AREA = Object.freeze({ top: 0.2, bottom: 0 });

/** Цвет заливки под линией: тот же, что у линии. */
export const CHART_AREA_COLOR = CHART_THEME.gold;

/** Остановки «ленты» по длине линии (`x1=0 → x2=1`): один цвет (круг 10, Г1). */
export const RIBBON_STOPS = Object.freeze([
  { offset: '0%', color: CHART_THEME.gold },
  { offset: '100%', color: CHART_THEME.gold },
]);
export const SAPPHIRE_STOPS = Object.freeze([
  { offset: '0%', color: CHART_THEME.sapphire },
  { offset: '100%', color: CHART_THEME.sapphire },
]);

/** Стопы градиента заливки для `<linearGradient>`: `areaGradientStops().map(...)`. Цвет по умолчанию — золото. */
export function areaGradientStops(color = CHART_THEME.gold, { top = CHART_AREA.top, bottom = CHART_AREA.bottom } = {}) {
  return [
    { offset: '0%', stopColor: color, stopOpacity: top },
    { offset: '100%', stopColor: color, stopOpacity: bottom },
  ];
}

/** Движение графика: линия рисуется слева направо 900 мс, смена серии плавная. Для `animationDuration` Recharts. */
export const CHART_MOTION = Object.freeze({
  drawMs: 900,
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

/**
 * Общие свойства `<CartesianGrid>`: без пунктира. Горизонтальные полосы чередуются (3 % тёплого тона и пусто),
 * сами линии почти не видны — читается ритм, а не решётка.
 */
export const GRID_PROPS = Object.freeze({
  stroke: 'rgba(32,42,60,0.025)',
  vertical: false,
  horizontalFill: Object.freeze([CHART_THEME.gridBand, 'rgba(30,38,56,0)']),
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
    boxShadow: '0 14px 34px -20px rgba(30,38,56,0.5), inset 0 1px 0 rgba(255,255,255,0.85)',
    padding: '10px 12px',
  }),
  labelStyle: Object.freeze({ color: CHART_THEME.axis, fontWeight: 600, marginBottom: 4 }),
  itemStyle: Object.freeze({ color: CHART_THEME.ink, padding: '1px 0' }),
  // Вертикальная золотая линия под курсором (сплошная, без пунктира).
  cursor: Object.freeze({ stroke: CHART_THEME.cursor, strokeWidth: 1.5 }),
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
    extraCssText: 'border-radius:14px;box-shadow:0 14px 34px -20px rgba(30,38,56,.5),inset 0 1px 0 rgba(255,255,255,.85);backdrop-filter:blur(14px) saturate(1.25);',
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
