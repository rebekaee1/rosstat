import { rememberAuthView, restoredAuthView } from '../lib/authReturn';
import { useEffect, useRef, useMemo, useState, useCallback } from 'react';
import {
  ResponsiveContainer, ComposedChart, Area, Line, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine, ReferenceArea, ReferenceDot,
} from 'recharts';
import { Activity, AreaChart as AreaIcon, BarChart3, LineChart as LineIcon } from 'lucide-react';
import {
  formatDate, formatAxisTick, formatValue,
  chartValueDigits, cn, pickChartAxisTicks, chartAxisTickBudget,
} from '../lib/format';
import { track, events } from '../lib/track';
import { valueWithUnit } from '../lib/valueText';
import { buildForecastVisualSeries, mergeActualForecastChartSeries } from '../lib/chartForecastMerge';
import { useLocale, useT } from '../i18n';
import { CHART_THEME, GRID_PROPS } from '../lib/chartTheme';
import { useChartGlassIds } from '../lib/chartHooks';
import {
  formatAxisTickCompact, needsCompactAxis, spansManyYears, yearAxisTicks,
} from '../lib/chartAxis';
import ChartBrandCaption from './ChartBrandCaption';
import ChartGlassDefs from './ChartGlassDefs';
import ChartBrush from './ChartBrush';
import { formatPointLabel, pointLabelWidth } from '../lib/chartPointLabel';
import Chip from './Chip';
import ChipGroup from './ChipGroup';
import '../styles/chart-controls.css';
import '../styles/z4-indicator.css';
import '../styles/k4-charts.css';
import '../lib/glassChartDefs';

// Основная линия: «стеклянная лента» 3 px (K4.1). Сплошной цвет нужен подсказке, легенде и шарику; сама линия — градиент ribbon.
const LINE = CHART_THEME.gold ?? CHART_THEME.line ?? '#B08A3E';
// Прогноз: тот же ряд продолжается золотой линией, которая тает по прозрачности вдоль, чтобы факт и прогноз не сливались.
const FORECAST = CHART_THEME.forecast;
// Ряд сравнения по умолчанию — сапфир (светлый → тёмный); чужие цвета рисуются как заданы.
const SAPPHIRE_LINES = new Set([CHART_THEME.sapphire, CHART_THEME.blue]);

// Одни и те же короткие подписи на всех страницах: «1 г., 5 л., 10 л., Всё». У годовых рядов нет смысла в «1 г.»
// (одна точка), поэтому там начинаем с 5 лет и добавляем 25.
const R_1Y = { key: '1y', labelKey: 'w6e.range.1y', months: 12 };
const R_5Y = { key: '5y', labelKey: 'w6e.range.5y', months: 60 };
const R_10Y = { key: '10y', labelKey: 'w6e.range.10y', months: 120 };
const R_25Y = { key: '25y', labelKey: 'w6e.range.25y', months: 300 };
const R_ALL = { key: 'all', labelKey: 'w6e.range.all', months: null };
const SHORT_RANGES = [R_1Y, R_5Y, R_10Y, R_ALL];

const RANGE_PRESETS = {
  default: SHORT_RANGES,
  annual: [R_5Y, R_10Y, R_25Y, R_ALL],
  quarterly: SHORT_RANGES,
  weekly: SHORT_RANGES,
  daily: SHORT_RANGES,
};

const RANGE_DEFAULTS = {
  default: '5y',
  annual: '10y',
  quarterly: '5y',
  weekly: '1y',
  daily: '1y',
};

// Наименьшее окно в точках: у годовых рядов «5 лет» это 5 точек, у квартальных «1 год» это 4.
const MIN_WINDOWS = {
  default: 10, annual: 5, quarterly: 6, weekly: 10, daily: 10,
};
const MIN_WINDOW = 10;
// Появление блока средствами CSS: без задержки, график виден сразу (раньше gsap скрывал его на ~1.3 с).
const REVEAL_STYLE = { '--fe-duration': '0.28s', '--fe-rise': '8px' };
const ZOOM_STEP = 1.18;
const TYPE_OPTIONS = [
  { key: 'area', labelKey: 'w6e.type.area', icon: AreaIcon },
  { key: 'line', labelKey: 'w6e.type.line', icon: LineIcon },
  { key: 'bar', labelKey: 'w6e.type.bar', icon: BarChart3 },
];

function dateBasedWindowSize(data, months, minWindow = MIN_WINDOW) {
  if (!months || !data.length) return data.length;
  const last = new Date(data[data.length - 1].date);
  const cutoff = new Date(last);
  cutoff.setUTCMonth(cutoff.getUTCMonth() - months);
  const cutoffStr = cutoff.toISOString().slice(0, 10);
  for (let i = 0; i < data.length; i++) {
    if (data[i].date >= cutoffStr) return Math.max(minWindow, data.length - i);
  }
  return data.length;
}

/**
 * Сдвигает ряд так, чтобы первая точка видимого окна равнялась 100 у основной страны и у каждой выбранной.
 * Базой служит первая строка окна, где у всех положительные значения; без такой строки возвращаем null.
 */
function rebaseVisibleRows(rows, series) {
  if (!rows.length || !series.length) return null;
  const start = rows.findIndex((row) => Number(row.actual) > 0
    && series.every((item) => Number(row[item.dataKey]) > 0));
  if (start < 0) return null;
  const baseActual = Number(rows[start].actual);
  const bases = series.map((item) => Number(rows[start][item.dataKey]));
  const mapped = rows.slice(start).map((row) => {
    const next = { date: row.date };
    if (row.actual != null) next.actual = (Number(row.actual) / baseActual) * 100;
    series.forEach((item, i) => {
      const v = row[item.dataKey];
      if (v != null) next[item.dataKey] = (Number(v) / bases[i]) * 100;
    });
    return next;
  });
  return { rows: mapped, startDate: rows[start].date };
}

function CustomTooltip({
  active, payload, label, mode, levelTooltipLabel, forecastTooltipLabel,
  dateFormat = 'full', unit = '%', valueDigits = 2, visible = true,
  numericTooltipOnly = false, comparisonSeries = [], actualSeriesLabel = '',
}) {
  const t = useT();
  if (!visible || !active || !payload?.length) return null;

  const actual = payload.find(p => p.dataKey === 'actual' && p.value != null && !isNaN(p.value));
  const forecast = payload.find(p => p.dataKey === 'forecast' && p.value != null && !isNaN(p.value));
  const comparisons = comparisonSeries
    .map((series) => ({
      ...series,
      payload: payload.find(
        (item) => item.dataKey === series.dataKey && item.value != null && !isNaN(item.value),
      ),
    }))
    .filter((series) => series.payload);

  const actualLabel = mode === 'cpi'
    ? (levelTooltipLabel || t('chart.tooltip.cpiMom'))
    : t('chart.tooltip.inflation12m');
  const forecastLabel = forecastTooltipLabel
    || (mode === 'cpi' ? t('common.forecast') : t('chart.tooltip.forecast12m'));
  const compactNumeric = numericTooltipOnly && comparisons.length === 0;

  // Один ряд: узкая подсказка в одну строку «дата  значение». Она стоит над линией (см. position у Tooltip) и ничего не закрывает.
  if (comparisons.length === 0 && (actual || forecast)) {
    const main = actual || forecast;
    const isForecast = !actual;
    return (
      <div className="fe-chart-tip fe-chart-tooltip">
        <span className="fe-chart-tip__date">{formatDate(label, dateFormat)}</span>
        <span
          className="fe-chart-tip__value"
          style={isForecast ? { color: CHART_THEME.forecastInk } : undefined}
        >
          {numericTooltipOnly
            ? formatValue(main.value, valueDigits)
            : valueWithUnit(main.value, valueDigits, unit)}
        </span>
        {isForecast && (
          <span className="fe-chart-tip__tag">
            {forecastTooltipLabel || t('common.forecast')}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className={`fe-chart-tooltip fe-chart-tooltip--stack ${compactNumeric ? 'min-w-[118px]' : 'min-w-[200px]'}`}>
      <p className="text-xs text-text-secondary mb-2">{formatDate(label, dateFormat)}</p>

      {/* Bridge-точка (последний факт, от которого тянется прогнозная линия)
          несёт оба значения — приоритет у факта, иначе последняя фактическая
          точка ошибочно подписывалась «Прогноз». */}
      {actual && (
        <div className={compactNumeric ? 'text-left' : 'flex items-center justify-between gap-4'}>
          {(!numericTooltipOnly || comparisons.length > 0) && (
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full" style={{ background: LINE }} />
              <span className="max-w-[150px] truncate text-xs text-text-tertiary">
                {actualSeriesLabel || actualLabel}
              </span>
            </div>
          )}
          <span className="text-sm font-semibold tabular-nums text-text-primary">
            {numericTooltipOnly
              ? formatValue(actual.value, valueDigits)
              : valueWithUnit(actual.value, valueDigits, unit)}
          </span>
        </div>
      )}

      {forecast && !actual && (
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full" style={{ background: CHART_THEME.champagne }} />
            <span className="text-xs text-text-tertiary">{forecastLabel}</span>
          </div>
          <span className="text-sm font-semibold tabular-nums text-champagne-muted">
            {valueWithUnit(forecast.value, valueDigits, unit)}
          </span>
        </div>
      )}
      {comparisons.map((series, index) => (
        <div
          key={series.dataKey}
          className={`mt-1 flex items-center justify-between gap-4 ${numericTooltipOnly && index === 0 ? 'fe-divider pt-1.5' : ''}`}
        >
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: series.color }} />
            <span className="max-w-[150px] truncate text-xs text-text-tertiary">
              {series.label || t('chart.compareSeries')}
            </span>
          </div>
          <span className="text-sm font-semibold tabular-nums" style={{ color: series.color }}>
            {numericTooltipOnly
              ? formatValue(series.payload.value, valueDigits)
              : valueWithUnit(series.payload.value, valueDigits, unit)}
          </span>
        </div>
      ))}
    </div>
  );
}

/**
 * Точка последнего наблюдения с подписью значения плашкой: число читается без наведения.
 * Плашка стоит с той стороны линии, где пусто: над точкой у растущего ряда, под ней у падающего.
 */
function LastPointMarker({ cx, cy, text, anchorEnd, below, beadId }) {
  if (!Number.isFinite(cx) || !Number.isFinite(cy)) return null;
  const width = pointLabelWidth(text);
  const height = 22;
  const x = anchorEnd ? cx - width + 12 : cx - 12;
  const y = below ? cy + 14 : cy - 14 - height;
  return (
    <g pointerEvents="none" className="z4-lastpoint k4-lastpoint">
      {/* Гало пульсирует три раза (класс k4-lastpoint__halo), затем остаётся тихим кругом. */}
      <circle className="k4-lastpoint__halo" cx={cx} cy={cy} r={11} fill={CHART_THEME.goldBright} fillOpacity={0.28} />
      {/* Гранёная бусина 12 px: тёмный низ, светлая грань сверху слева, белый блик. */}
      <circle cx={cx} cy={cy} r={6.5} fill={`url(#${beadId})`} />
      <path d={`M${cx - 4.4} ${cy - 1.4} L${cx - 1.2} ${cy - 5.2} L${cx + 2.6} ${cy - 3.6} Z`} fill="#fff" fillOpacity={0.55} />
      <path d={`M${cx + 5.2} ${cy + 1.4} L${cx + 1.8} ${cy + 5.4} L${cx - 1.6} ${cy + 4.6} Z`} fill={CHART_THEME.goldDeep} fillOpacity={0.35} />
      <circle cx={cx - 2} cy={cy - 2.2} r={1.3} fill="#fff" fillOpacity={0.9} />
      {/* Плашка значения — стеклянная: без обводки, мягкая тень (класс k4-lastpoint__tag), блик сверху. */}
      <rect className="k4-lastpoint__tag" x={x} y={y} width={width} height={height} rx={11} fill="#FFFFFF" fillOpacity={0.92} />
      <rect x={x + 6} y={y + 1} width={Math.max(0, width - 12)} height={1.2} rx={0.6} fill="#FFFFFF" />
      <text
        x={x + width / 2}
        y={y + height / 2 + 4.2}
        textAnchor="middle"
        fill={CHART_THEME.ink}
        fontSize={12}
        fontWeight={700}
        fontFamily={CHART_THEME.font}
      >
        {text}
      </text>
    </g>
  );
}

/**
 * Вертикальный «луч» на границе факта и прогноза: тонкая светлая линия, тающая к краям, и размытое свечение рядом.
 * Градиент задан в координатах плота (userSpaceOnUse), потому что у вертикальной линии нулевая ширина ограничивающей рамки.
 */
function NowBeam({ x1, y1, y2, beamId }) {
  if (![x1, y1, y2].every(Number.isFinite)) return null;
  return (
    <g pointerEvents="none" className="k4-beam">
      <defs>
        <linearGradient id={beamId} gradientUnits="userSpaceOnUse" x1={x1} y1={y1} x2={x1} y2={y2}>
          <stop offset="0%" stopColor={CHART_THEME.goldLight} stopOpacity={0} />
          <stop offset="35%" stopColor={CHART_THEME.goldBright} stopOpacity={0.95} />
          <stop offset="75%" stopColor={CHART_THEME.goldLight} stopOpacity={0.7} />
          <stop offset="100%" stopColor={CHART_THEME.goldLight} stopOpacity={0} />
        </linearGradient>
      </defs>
      <line className="k4-beam__glow" x1={x1} x2={x1} y1={y1} y2={y2} stroke={`url(#${beamId})`} strokeWidth={9} strokeLinecap="round" opacity={0.55} />
      <line x1={x1} x2={x1} y1={y1} y2={y2} stroke={`url(#${beamId})`} strokeWidth={1.6} strokeLinecap="round" />
    </g>
  );
}

export default function IndicatorChart({
  inflation,
  showForecast = true,
  mode = 'inflation',
  cpiData,
  forecastData,
  onChartData,
  onFullData,
  onRangeChange,
  referenceLineY,
  cpiChartTitle,
  levelTooltipLabel,
  forecastTooltipLabel,
  emptyHint,
  dateFormat = 'full',
  unit = '%',
  rangePreset = 'default',
  chartMode,
  indicatorCode,
  indicatorCategory,
  defaultChartType = 'area',
  numericTooltipOnly = false,
  comparisonData = null,
  comparisonLabel = '',
  comparisonSeries = null,
  actualSeriesLabel = '',
  rebaseVisible = false,
  ariaTitle = '',
  chartTitleBuilder = null,
}) {
  const t = useT();
  const { locale } = useLocale();
  const digits = chartValueDigits(unit, chartMode ?? mode);
  const glass = useChartGlassIds('k4');
  const chartAreaRef = useRef(null);
  const rangeOptions = (RANGE_PRESETS[rangePreset] || RANGE_PRESETS.default).map((opt) => ({
    ...opt,
    label: t(opt.labelKey),
  }));
  const defaultRange = RANGE_DEFAULTS[rangePreset] || RANGE_DEFAULTS.default;
  const minWindow = MIN_WINDOWS[rangePreset] ?? MIN_WINDOW;
  const viewKey = `${indicatorCode}:${chartMode ?? mode}:${rangePreset}`;
  const [savedView] = useState(() => restoredAuthView(viewKey));
  const [range, setRange] = useState(savedView?.range ?? defaultRange);
  const [windowOverride, setWindowOverride] = useState(savedView?.windowOverride ?? null);
  const [offset, setOffset] = useState(savedView?.offset ?? 0);
  const [isDragging, setIsDragging] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  // Последнее взаимодействие — касанием: подсказку открываем тапом по плоту и закрываем тапом вне плота.
  const [touchMode, setTouchMode] = useState(false);
  const [prevPreset, setPrevPreset] = useState(rangePreset);
  const [chartType, setChartType] = useState(savedView?.chartType ?? defaultChartType);
  useEffect(() => {
    const save = () => rememberAuthView(viewKey, { range, windowOverride, offset, chartType });
    window.addEventListener('fe:auth-leave', save);
    return () => window.removeEventListener('fe:auth-leave', save);
  }, [viewKey, range, windowOverride, offset, chartType]);
  // Ширина plot-area: на мобилке 7 длинных тиков («май 2022») наезжают друг
  // на друга при interval={0} — бюджет тиков считаем от фактической ширины.
  const [plotWidth, setPlotWidth] = useState(0);
  const dragRef = useRef(null);
  const onChartDataRef = useRef(onChartData);
  const onFullDataRef = useRef(onFullData);
  const resolvedComparisonSeries = useMemo(() => {
    if (comparisonSeries?.length) {
      return comparisonSeries.map((series, index) => ({
        ...series,
        dataKey: series.dataKey || `comparison_${index}`,
        color: series.color || CHART_THEME.sapphire,
      }));
    }
    if (comparisonData?.length) {
      return [{
        data: comparisonData,
        dataKey: 'comparison_0',
        label: comparisonLabel || t('chart.compareSeries'),
        color: CHART_THEME.sapphire,
      }];
    }
    return [];
  }, [comparisonSeries, comparisonData, comparisonLabel, t]);

  useEffect(() => { onChartDataRef.current = onChartData; }, [onChartData]);
  useEffect(() => { onFullDataRef.current = onFullData; }, [onFullData]);

  useEffect(() => {
    const el = chartAreaRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect?.width;
      if (w) setPlotWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  if (prevPreset !== rangePreset) {
    setPrevPreset(rangePreset);
    setRange(defaultRange);
    setWindowOverride(null);
    setOffset(0);
  }

  const chartData = useMemo(() => {
    let base;
    if (mode === 'cpi') {
      const points = cpiData || [];
      const fcValues = forecastData?.forecast?.values || [];
      base = mergeActualForecastChartSeries(points, fcValues, {
        showForecast,
        replacePartialActual: forecastData?.forecast?.replaces_partial_actual === true,
      });
    } else {
      if (!inflation) return [];
      const actuals = inflation.actuals || [];
      const forecasts = inflation.forecast || [];
      base = mergeActualForecastChartSeries(actuals, forecasts, {
        showForecast,
      });
    }

    if (!resolvedComparisonSeries.length) return base;
    const rows = new Map(base.map((row) => [row.date, { ...row }]));
    for (const series of resolvedComparisonSeries) {
      for (const point of series.data || []) {
        const date = point.date;
        if (!date || point.value == null) continue;
        const row = rows.get(date) || { date, actual: null, forecast: null };
        row[series.dataKey] = Number(point.value);
        rows.set(date, row);
      }
    }
    return [...rows.values()].sort((a, b) => a.date.localeCompare(b.date));
  }, [inflation, cpiData, forecastData, showForecast, mode, resolvedComparisonSeries]);

  const dataLen = chartData.length;

  // Полный ряд (факт + прогноз) для выгрузки CSV/Excel — независимо от
  // видимого окна графика. Экспорт обязан отдавать всю историю, не 5-летний срез.
  useEffect(() => { onFullDataRef.current?.(chartData); }, [chartData]);

  // Сохранённый до входа вид мог указывать на период, которого больше нет в списке (например, «3 года»).
  const activeRange = rangeOptions.some((r) => r.key === range) ? range : defaultRange;
  const presetWindow = useMemo(() => {
    const opt = rangeOptions.find(r => r.key === activeRange);
    return dateBasedWindowSize(chartData, opt?.months, minWindow);
  }, [chartData, activeRange, rangeOptions, minWindow]);

  const windowSize = windowOverride ?? presetWindow;
  const maxOffset = Math.max(0, dataLen - windowSize);
  const clampedOffset = Math.min(Math.max(0, offset), maxOffset);

  const startIdx = Math.max(0, dataLen - windowSize - clampedOffset);
  const endIdx = dataLen - clampedOffset;
  const windowRows = useMemo(
    () => chartData.slice(startIdx, endIdx),
    [chartData, startIdx, endIdx]
  );
  // «Динамика (=100)»: база на начале выбранного окна, а не на общей давней дате. Линии стартуют ровно со 100.
  const rebased = useMemo(
    () => (rebaseVisible && resolvedComparisonSeries.length
      ? rebaseVisibleRows(windowRows, resolvedComparisonSeries)
      : null),
    [rebaseVisible, windowRows, resolvedComparisonSeries],
  );
  const visibleData = rebased ? rebased.rows : windowRows;

  const forecastEndDate = useMemo(() => {
    if (!showForecast) return null;
    for (let i = visibleData.length - 1; i >= 0; i--) {
      if (visibleData[i].forecast != null) {
        return visibleData[i].date;
      }
    }
    return null;
  }, [visibleData, showForecast]);
  const forecastLast = useMemo(
    () => [...visibleData].reverse().find((row) => row.forecast != null && row.actual == null),
    [visibleData],
  );
  const { data: visualData, boundaryDate: forecastBoundaryDate } = useMemo(() => {
    if (!(showForecast && chartType !== 'bar')) return { data: visibleData, boundaryDate: null };
    return buildForecastVisualSeries(visibleData);
  }, [visibleData, showForecast, chartType]);

  useEffect(() => { onChartDataRef.current?.(visibleData); }, [visibleData]);

  const handleRangeChange = (key) => {
    setRange(key);
    setWindowOverride(null);
    setOffset(0);
    onRangeChange?.(key);
    track(events.CHART_RANGE_CHANGE, { range: key, indicator: indicatorCode, indicatorCategory });
  };

  // Рамка выбора под графиком: левая и правая ручки задают начало и конец окна, середина двигает его целиком.
  const handleBrush = useCallback((start, end) => {
    setWindowOverride(Math.max(minWindow, end - start));
    setOffset(Math.max(0, dataLen - end));
  }, [dataLen, minWindow, setOffset, setWindowOverride]);

  /* ── Wheel zoom (TradingView-style) ── */
  const handleWheel = useCallback((e) => {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    e.stopPropagation();

    const zoomIn = e.deltaY < 0;
    const factor = zoomIn ? 1 / ZOOM_STEP : ZOOM_STEP;
    const current = windowOverride ?? presetWindow;
    const next = Math.max(minWindow, Math.min(dataLen, Math.round(current * factor)));
    if (next === current) return;

    const rect = chartAreaRef.current?.getBoundingClientRect();
    if (rect) {
      const mouseRatio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const pointsAdded = next - current;
      const shiftLeft = Math.round(pointsAdded * mouseRatio);
      setOffset(prev => Math.max(0, Math.min(dataLen - next, prev - shiftLeft)));
    }

    setWindowOverride(next);
  }, [windowOverride, presetWindow, dataLen, minWindow, setOffset, setWindowOverride]);

  useEffect(() => {
    const el = chartAreaRef.current;
    if (!el) return;
    el.addEventListener('wheel', handleWheel, { passive: false });
    return () => el.removeEventListener('wheel', handleWheel);
  }, [handleWheel]);

  /* ── Drag pan ── */
  const handlePointerDown = useCallback((e) => {
    const isTouch = e.pointerType === 'touch';
    setTouchMode(isTouch);
    if (isTouch) setIsHovering(true);
    const rect = chartAreaRef.current?.getBoundingClientRect();
    if (!rect) return;
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initOffset: clampedOffset,
      chartWidth: rect.width,
      pointerId: e.pointerId,
      phase: 'deciding',
    };
  }, [clampedOffset, setTouchMode, setIsHovering]);

  const handlePointerMove = useCallback((e) => {
    let d = dragRef.current;
    if (!d) return;

    if (d.phase === 'deciding') {
      const dx = e.clientX - d.startX;
      const dy = e.clientY - d.startY;
      if (Math.hypot(dx, dy) < 8) return;
      if (Math.abs(dy) >= Math.abs(dx)) {
        dragRef.current = null;
        return;
      }
      d.phase = 'dragging';
      try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* ok */ }
      setIsDragging(true);
      // Сдвиг пальцем — это не наведение: подсказка не должна «залипать» над сдвинутым рядом.
      if (e.pointerType === 'touch') setIsHovering(false);
    }

    d = dragRef.current;
    if (!d || d.phase !== 'dragging') return;

    const deltaX = e.clientX - d.startX;
    const pixelsPerPoint = d.chartWidth / (windowSize || 1);
    const shift = Math.round(deltaX / pixelsPerPoint);
    const newOffset = Math.max(0, Math.min(d.initOffset + shift, maxOffset));
    setOffset(newOffset);
  }, [windowSize, maxOffset, setOffset, setIsDragging, setIsHovering]);

  const handlePointerUp = useCallback((e) => {
    const d = dragRef.current;
    if (d?.phase === 'dragging') {
      try { e.currentTarget.releasePointerCapture(e.pointerId); } catch { /* ok */ }
    } else if (e.pointerType === 'touch') {
      if (e.type === 'pointercancel') {
        // Браузер забрал жест под прокрутку страницы — подсказку убираем.
        setIsHovering(false);
      } else {
        // Тап: часть сенсорных браузеров не шлёт эмулированный mousemove, а Recharts без него не знает
        // точку. Передаём ему координаты тапа сами; лишний дубль от браузера ничего не меняет.
        const wrapper = e.currentTarget.querySelector('.recharts-wrapper');
        if (wrapper) {
          wrapper.dispatchEvent(new MouseEvent('mousemove', {
            bubbles: true, clientX: e.clientX, clientY: e.clientY,
          }));
        }
      }
    }
    dragRef.current = null;
    setIsDragging(false);
  }, [setIsDragging, setIsHovering]);

  // Тап вне плота закрывает подсказку (на сенсоре нет mouseleave).
  useEffect(() => {
    if (!isHovering || !touchMode) return undefined;
    const onOutside = (event) => {
      if (!chartAreaRef.current?.contains(event.target)) setIsHovering(false);
    };
    document.addEventListener('pointerdown', onOutside, true);
    return () => document.removeEventListener('pointerdown', onOutside, true);
  }, [isHovering, touchMode]);

  const { yDomain, yWidth, yTicks, yCompact } = useMemo(() => {
    if (!visibleData.length) return { yDomain: ['auto', 'auto'], yWidth: 55, yTicks: undefined, yCompact: false };
    let min = Infinity; let max = -Infinity;
    for (const row of visibleData) {
      if (row.actual != null) { min = Math.min(min, row.actual); max = Math.max(max, row.actual); }
      if (row.forecast != null) { min = Math.min(min, row.forecast); max = Math.max(max, row.forecast); }
      for (const series of resolvedComparisonSeries) {
        const value = row[series.dataKey];
        if (value != null) { min = Math.min(min, value); max = Math.max(max, value); }
      }
    }
    if (!isFinite(min)) return { yDomain: ['auto', 'auto'], yWidth: 55, yTicks: undefined, yCompact: false };

    const span = max - min || 1;
    const rough = span / 5;
    const pow = Math.pow(10, Math.floor(Math.log10(rough)));
    const frac = rough / pow;
    const step = frac <= 1.5 ? pow : frac <= 3.5 ? 2 * pow : frac <= 7.5 ? 5 * pow : 10 * pow;

    const niceMin = Math.floor(min / step) * step;
    const niceMax = Math.ceil(max / step) * step;
    const ticks = [];
    for (let v = niceMin; v <= niceMax + step * 0.01; v += step) {
      ticks.push(Math.round(v * 1e6) / 1e6);
    }

    const absMax = Math.max(Math.abs(niceMin), Math.abs(niceMax));
    // Крупные числа подписываем «24 млн», а не «24 000 000»: ось не съедает четверть ширины графика.
    const compact = needsCompactAxis(absMax);
    const sampleLabel = compact
      ? formatAxisTickCompact(niceMin < 0 ? niceMin : absMax, digits, locale)
      : formatAxisTick(niceMin < 0 ? niceMin : absMax, digits);
    const w = Math.max(40, Math.min(120, sampleLabel.length * 7.5 + 12));
    return { yDomain: [niceMin, niceMax], yWidth: w, yTicks: ticks, yCompact: compact };
  }, [visibleData, digits, resolvedComparisonSeries, locale]);

  // Подписи оси X: бюджет от ширины + фактическая RU-строка («7 июля 2025»),
  // затем densest step без пересечения (см. pickChartAxisTicks).
  const axisDateFormat = dateFormat === 'full' ? 'short' : dateFormat;
  const formatXAxisLabel = useCallback(
    (d) => formatDate(d, axisDateFormat),
    [axisDateFormat],
  );
  const xAxisPlotWidth = Math.max(0, plotWidth - 80);
  const xTickBudget = useMemo(() => {
    const sample = visibleData[0]?.date ?? visibleData[visibleData.length - 1]?.date;
    const sampleLabel = sample != null ? formatXAxisLabel(sample) : '';
    const labelSpec = sampleLabel
      || (dateFormat === 'annual' ? 4
        : dateFormat === 'quarterly' ? 10
          : dateFormat === 'day' || dateFormat === 'weekly' ? '7 июля 2025'
            : 8);
    return chartAxisTickBudget(xAxisPlotWidth, labelSpec);
  }, [xAxisPlotWidth, dateFormat, visibleData, formatXAxisLabel]);
  // Окно длиннее двух с половиной лет: подписи по годам («2022, 2023, 2024»), а не «авг 2022, июн 2023, апр 2024».
  const yearTicks = useMemo(() => {
    if (dateFormat === 'annual') return null;
    const dates = visibleData.map((row) => row.date);
    return spansManyYears(dates) ? yearAxisTicks(dates, xAxisPlotWidth) : null;
  }, [visibleData, dateFormat, xAxisPlotWidth]);
  const xTickFormat = useCallback(
    (d) => (yearTicks ? String(d).slice(0, 4) : formatXAxisLabel(d)),
    [yearTicks, formatXAxisLabel],
  );
  const xTicks = useMemo(() => {
    if (yearTicks) return yearTicks;
    const cadence = dateFormat === 'annual' || dateFormat === 'quarterly'
      ? dateFormat
      : null;
    return pickChartAxisTicks(visibleData, xTickBudget, {
      cadence,
      plotWidthPx: xAxisPlotWidth,
      formatLabel: formatXAxisLabel,
    });
  }, [yearTicks, visibleData, xTickBudget, dateFormat, xAxisPlotWidth, formatXAxisLabel]);

  // Заголовок со словами о периоде («ВВП, США: за 10 лет, млрд $»); пока окно подвинули вручную, период не называем.
  const rangeText = windowOverride == null ? t(`z4.range.${activeRange}`) : '';
  const builtTitle = chartTitleBuilder ? chartTitleBuilder(rangeText) : null;
  const title = builtTitle
    ?? cpiChartTitle
    ?? (mode === 'cpi'
      ? t('chart.title.cpiMom')
      : t('chart.title.inflation12m'));

  // Подпись плота для скринридера: название и последнее фактическое значение ряда.
  const lastActualRow = useMemo(() => {
    for (let i = chartData.length - 1; i >= 0; i--) {
      const v = chartData[i].actual;
      if (v != null && !Number.isNaN(Number(v))) return chartData[i];
    }
    return null;
  }, [chartData]);
  const plotAriaLabel = lastActualRow
    ? t('chart.plotAria', {
      title: ariaTitle || title,
      value: valueWithUnit(lastActualRow.actual, digits, unit),
      date: formatDate(lastActualRow.date, dateFormat),
    })
    : title;

  const baselineY = referenceLineY !== undefined
    ? referenceLineY
    : 0;

  const hasForecast = mode === 'inflation'
    ? inflation?.forecast?.length > 0
    : forecastData?.forecast?.values?.length > 0;

  const isZoomed = windowOverride != null;
  // Подпись последней фактической точки: значение прямо у линии, без наведения.
  const lastPointRow = useMemo(() => {
    for (let i = visualData.length - 1; i >= 0; i -= 1) {
      if (visualData[i].actual != null && Number.isFinite(Number(visualData[i].actual))) return visualData[i];
    }
    return null;
  }, [visualData]);
  // Предыдущее значение: у падающего ряда плашка с подписью уходит под линию, у растущего стоит над ней.
  const lastPointBelow = useMemo(() => {
    if (!lastPointRow) return false;
    const idx = visualData.indexOf(lastPointRow);
    for (let i = idx - 1; i >= 0; i -= 1) {
      const v = visualData[i].actual;
      if (v != null && Number.isFinite(Number(v))) return Number(v) > Number(lastPointRow.actual);
    }
    return false;
  }, [visualData, lastPointRow]);
  const showBrush = dataLen >= minWindow * 2;

  if (!dataLen) {
    return (
      <div role="status" className="fe-chart-card fe-reveal p-8 md:p-10 shadow-sm min-h-[240px] flex flex-col items-center justify-center text-center gap-4" style={REVEAL_STYLE}>
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl fe-glass-lite">
          <Activity className="w-7 h-7 text-champagne/80" aria-hidden />
        </div>
        <div className="max-w-md space-y-2">
          <p className="text-sm font-semibold text-text-primary">{t('chart.emptyTitle')}</p>
          <p className="text-sm text-text-secondary leading-relaxed">
            {emptyHint || t('chart.emptyHint')}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="fe-panel fe-chart-card fe-reveal" style={REVEAL_STYLE}>
      <div className="fe-chart-toolbar flex items-center justify-between mb-5 flex-wrap gap-3">
        <h3 className="fe-chart-title">
          {title}
        </h3>
        {/* ml-auto: при длинном заголовке контролы переносятся на новую строку,
            но всегда прижаты вправо (а не уезжают влево). Созвон 2026-06-16. */}
        <div className="flex items-center gap-2 flex-wrap ml-auto">
          <ChipGroup label={t('chart.typeAria')} className="fe-seg" style={{ '--seg-i': TYPE_OPTIONS.findIndex((o) => o.key === chartType), '--seg-n': TYPE_OPTIONS.length }}>
            {/* Бегунок общего жёлоба: сам едет под выбранную кнопку (transform), кнопки лежат поверх. */}
            <span className="fe-seg__thumb" aria-hidden="true" />
            {TYPE_OPTIONS.map((opt) => {
              const IconComp = opt.icon;
              return (
                <Chip
                  key={opt.key}
                  active={chartType === opt.key}
                  onClick={() => setChartType(opt.key)}
                  className="fe-chip--seg"
                >
                  <IconComp className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
                  <span>{t(opt.labelKey)}</span>
                </Chip>
              );
            })}
          </ChipGroup>
          {isZoomed && (
            <Chip
              aria-pressed={undefined}
              onClick={() => { setWindowOverride(null); setOffset(0); track(events.CHART_ZOOM, { action: 'reset', indicator: indicatorCode, indicatorCategory }); }}
              className="fe-chip--ghost"
              title={t('chart.resetZoomTitle')}
            >
              {t('chart.resetZoom')}
            </Chip>
          )}
          <ChipGroup label={t('chart.rangeAria')} className="fe-chip-row--tight">
            {rangeOptions.map(opt => (
              <Chip
                key={opt.key}
                active={activeRange === opt.key && !isZoomed}
                onClick={() => handleRangeChange(opt.key)}
              >
                {opt.label}
              </Chip>
            ))}
          </ChipGroup>
        </div>
      </div>

      {rebased && (
        <p className="fe-chart-note" role="note">
          {t('w6e.compare.baseStart', { date: formatDate(rebased.startDate, dateFormat === 'full' ? 'short' : dateFormat) })}
        </p>
      )}

      <div
        ref={chartAreaRef}
        role="img"
        aria-label={plotAriaLabel}
        data-touch-tooltip={touchMode && isHovering ? 'open' : undefined}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}
        className={cn(
          'fe-chart-plot z4-plot fe-chart-draw rounded-xl relative',
          isDragging ? 'cursor-grabbing select-none' : 'cursor-crosshair'
        )}
        style={{ touchAction: 'pan-y' }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={visualData} margin={{ top: 38, right: 14, bottom: 16, left: 0 }}>
            <defs>
              <ChartGlassDefs ids={glass} forecastColor={FORECAST} width={Math.max(plotWidth, 320)} />
            </defs>

            {/* Сетка без пунктира: полосы 4,5 % чередуются (K4.1), линии едва заметны. */}
            <CartesianGrid {...GRID_PROPS} />
            <XAxis
              dataKey="date"
              tickFormatter={xTickFormat}
              stroke="rgba(88,74,46,0.12)"
              tick={{ fill: CHART_THEME.axis, fontSize: CHART_THEME.tickSize, fontFamily: CHART_THEME.font }}
              tickLine={false}
              ticks={xTicks}
              interval={0}
              tickMargin={10}
              height={42}
              padding={{ left: 8, right: 10 }}
            />
            <YAxis
              stroke="rgba(88,74,46,0.12)"
              tick={{ fill: CHART_THEME.axis, fontSize: CHART_THEME.tickSize, fontFamily: CHART_THEME.font }}
              tickLine={false}
              axisLine={false}
              domain={yDomain}
              ticks={yTicks}
              tickFormatter={(v) => (yCompact ? formatAxisTickCompact(v, digits, locale) : formatAxisTick(v, digits))}
              width={yWidth}
            />
            <Tooltip
              content={(
                <CustomTooltip
                  mode={mode}
                  levelTooltipLabel={levelTooltipLabel}
                  forecastTooltipLabel={forecastTooltipLabel}
                  dateFormat={dateFormat}
                  unit={unit}
                  valueDigits={digits}
                  visible={isHovering}
                  numericTooltipOnly={numericTooltipOnly}
                  comparisonSeries={resolvedComparisonSeries}
                  actualSeriesLabel={actualSeriesLabel}
                />
              )}
              cursor={isDragging || !isHovering ? false : { stroke: CHART_THEME.cursor, strokeWidth: 1.5 }}
              active={isHovering && !isDragging}
              position={resolvedComparisonSeries.length ? undefined : { y: 0 }}
              wrapperStyle={{ pointerEvents: 'none', zIndex: 20 }}
              isAnimationActive={false}
            />
            {baselineY !== null && (
              <ReferenceLine y={baselineY} stroke="rgba(88,74,46,0.2)" strokeWidth={1} />
            )}

            {/* Полоса прогноза: только для area/line. Для bar её скрываем —
                столбцы прогноза уже отдельным цветом, заливка дублирует. */}
            {forecastBoundaryDate && forecastEndDate && showForecast && chartType !== 'bar' && (
              <ReferenceArea
                x1={forecastBoundaryDate}
                x2={forecastEndDate}
                fill={CHART_THEME.champagne}
                fillOpacity={0.07}
                stroke="none"
                ifOverflow="visible"
                style={{ pointerEvents: 'none' }}
              />
            )}
            {/* «Сейчас»: вертикальный луч света вместо штриховой линии. */}
            {forecastBoundaryDate && showForecast && chartType !== 'bar' && (
              <ReferenceLine
                x={forecastBoundaryDate}
                ifOverflow="visible"
                shape={(props) => (
                  <NowBeam x1={props.x1 ?? props.x} y1={props.y1} y2={props.y2} beamId={glass.beam} />
                )}
              />
            )}

            {chartType === 'bar' ? (
              <Bar
                dataKey="actual"
                fill={`url(#${glass.bar})`}
                stroke="none"
                radius={[7, 7, 0, 0]}
                isAnimationActive={false}
                maxBarSize={28}
              />
            ) : chartType === 'line' ? (
              <>
                <Line
                  className="k4-ribbon"
                  dataKey="actual"
                  stroke={`url(#${glass.ribbon})`}
                  strokeWidth={3}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  dot={false}
                  activeDot={isDragging ? false : { r: 5, fill: LINE, stroke: '#FFFFFF', strokeWidth: 2 }}
                  isAnimationActive={false}
                  connectNulls
                />
                {/* Белый блик-штрих 1 px поверх ленты, смещён на 1 px вверх (css k4-gloss). */}
                <Line
                  className="k4-gloss"
                  dataKey="actual"
                  stroke="rgba(255,255,255,0.72)"
                  strokeWidth={1}
                  strokeLinecap="round"
                  dot={false}
                  activeDot={false}
                  isAnimationActive={false}
                  connectNulls
                  legendType="none"
                  tooltipType="none"
                />
              </>
            ) : (
              <>
                <Area
                  className="k4-ribbon"
                  dataKey="actual"
                  stroke={`url(#${glass.ribbon})`}
                  strokeWidth={3}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  fill={`url(#${glass.area})`}
                  dot={false}
                  activeDot={isDragging ? false : { r: 5, fill: LINE, stroke: '#FFFFFF', strokeWidth: 2 }}
                  isAnimationActive={false}
                  connectNulls
                />
                <Line
                  className="k4-gloss"
                  dataKey="actual"
                  stroke="rgba(255,255,255,0.72)"
                  strokeWidth={1}
                  strokeLinecap="round"
                  dot={false}
                  activeDot={false}
                  isAnimationActive={false}
                  connectNulls
                  legendType="none"
                  tooltipType="none"
                />
              </>
            )}

            {showForecast && (
              chartType === 'bar' ? (
                <Bar
                  dataKey="forecast"
                  fill={`url(#${glass.barForecast})`}
                  stroke="none"
                  radius={[7, 7, 0, 0]}
                  isAnimationActive={false}
                  maxBarSize={28}
                />
              ) : (
                <Line
                  className="k4-forecast"
                  dataKey="forecast"
                  stroke={`url(#${glass.forecast})`}
                  strokeWidth={3}
                  strokeLinecap="round"
                  connectNulls
                  dot={(props) => (props.payload?.date === forecastLast?.date
                    ? <circle cx={props.cx} cy={props.cy} r="5" fill={FORECAST} fillOpacity={0.9} stroke="#fff" strokeWidth="2" />
                    : null)}
                  activeDot={isDragging ? false : { r: 6, fill: FORECAST, stroke: '#FFFFFF', strokeWidth: 2 }}
                  isAnimationActive={false}
                />
              )
            )}
            {resolvedComparisonSeries.map((series) => {
              const sapphire = SAPPHIRE_LINES.has(series.color);
              return (
                <Line
                  key={series.dataKey}
                  className={sapphire ? 'k4-ribbon k4-ribbon--sapphire' : 'k4-ribbon k4-ribbon--plain'}
                  dataKey={series.dataKey}
                  stroke={sapphire ? `url(#${glass.sapphire})` : series.color}
                  strokeWidth={2.5}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  connectNulls
                  dot={false}
                  activeDot={isDragging ? false : { r: 4.5, fill: series.color, stroke: '#FFFFFF', strokeWidth: 2 }}
                  isAnimationActive={false}
                />
              );
            })}
            {lastPointRow && chartType !== 'bar' && !isDragging && (
              <ReferenceDot
                x={lastPointRow.date}
                y={Number(lastPointRow.actual)}
                r={4.5}
                ifOverflow="visible"
                shape={(props) => (
                  <LastPointMarker
                    cx={props.cx}
                    cy={props.cy}
                    text={formatPointLabel(lastPointRow.actual, digits, locale)}
                    anchorEnd={Number(props.cx) > plotWidth * 0.45}
                    below={lastPointBelow}
                    beadId={glass.bead}
                  />
                )}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>

      </div>

      {showBrush && (
        <ChartBrush
          rows={chartData}
          start={startIdx}
          end={endIdx}
          minWindow={minWindow}
          onChange={handleBrush}
          labels={{
            group: t('chart.windowAria'),
            from: t('w6e.brush.from'),
            to: t('w6e.brush.to'),
          }}
        />
      )}

      {resolvedComparisonSeries.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 pt-3 fe-divider">
          <div className="flex items-center gap-2">
            <span className="k4-swatch k4-swatch--ribbon" aria-hidden="true" />
            <span className="text-xs text-text-secondary">{actualSeriesLabel || t('chart.primarySeries')}</span>
          </div>
          {resolvedComparisonSeries.map((series) => (
            <div key={series.dataKey} className="flex min-w-0 items-center gap-2">
              <span className={SAPPHIRE_LINES.has(series.color) ? 'k4-swatch k4-swatch--sapphire shrink-0' : 'k4-swatch shrink-0'} style={SAPPHIRE_LINES.has(series.color) ? undefined : { backgroundColor: series.color }} aria-hidden="true" />
              <span className="max-w-[14rem] truncate text-xs text-text-secondary">{series.label}</span>
            </div>
          ))}
        </div>
      )}

      {showForecast && hasForecast && (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 mt-4 pt-3 fe-divider">
          <div className="flex items-center gap-2">
            <span className="k4-swatch k4-swatch--ribbon" aria-hidden="true" />
            <span className="text-xs text-text-secondary">{t('chart.legend.actual')}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="k4-swatch k4-swatch--forecast" aria-hidden="true" />
            <span className="text-xs text-text-secondary">{t('common.forecast')}</span>
          </div>
        </div>
      )}
      <ChartBrandCaption />
    </div>
  );
}
