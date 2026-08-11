import { useEffect, useRef, useMemo, useState, useCallback } from 'react';
import gsap from 'gsap';
import {
  ResponsiveContainer, ComposedChart, Area, Line, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine, ReferenceArea,
} from 'recharts';
import { Activity, ZoomIn, AreaChart as AreaIcon, BarChart3, LineChart as LineIcon } from 'lucide-react';
import {
  formatDate, formatAxisTick, formatValue,
  chartValueDigits, unitSuffix, cn, pickChartAxisTicks, chartAxisTickBudget,
} from '../lib/format';
import { track, events } from '../lib/track';
import { mergeActualForecastChartSeries } from '../lib/chartForecastMerge';

const RANGE_PRESETS = {
  default: [
    { key: '3y', label: '3 года', months: 36 },
    { key: '5y', label: '5 лет', months: 60 },
    { key: '10y', label: '10 лет', months: 120 },
    { key: 'all', label: 'Все', months: null },
  ],
  annual: [
    { key: '10y', label: '10 лет', months: 120 },
    { key: '25y', label: '25 лет', months: 300 },
    { key: 'all', label: 'Все', months: null },
  ],
  quarterly: [
    { key: '5y', label: '5 лет', months: 60 },
    { key: '10y', label: '10 лет', months: 120 },
    { key: '25y', label: '25 лет', months: 300 },
    { key: 'all', label: 'Все', months: null },
  ],
  weekly: [
    { key: '6m', label: '6 мес', months: 6 },
    { key: '1y', label: '1 год', months: 12 },
    { key: '3y', label: '3 года', months: 36 },
    { key: 'all', label: 'Все', months: null },
  ],
  daily: [
    { key: '1y', label: '1 год', months: 12 },
    { key: '3y', label: '3 года', months: 36 },
    { key: '5y', label: '5 лет', months: 60 },
    { key: 'all', label: 'Все', months: null },
  ],
};

const RANGE_DEFAULTS = {
  default: '5y',
  annual: '10y',
  quarterly: '10y',
  weekly: '1y',
  daily: '3y',
};

const MIN_WINDOW = 10;
const ZOOM_STEP = 1.18;

function dateBasedWindowSize(data, months) {
  if (!months || !data.length) return data.length;
  const last = new Date(data[data.length - 1].date);
  const cutoff = new Date(last);
  cutoff.setUTCMonth(cutoff.getUTCMonth() - months);
  const cutoffStr = cutoff.toISOString().slice(0, 10);
  for (let i = 0; i < data.length; i++) {
    if (data[i].date >= cutoffStr) return Math.max(MIN_WINDOW, data.length - i);
  }
  return data.length;
}

function CustomTooltip({
  active, payload, label, mode, levelTooltipLabel, forecastTooltipLabel,
  dateFormat = 'full', unit = '%', valueDigits = 2, visible = true,
  numericTooltipOnly = false, comparisonSeries = [], actualSeriesLabel = '',
}) {
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
    ? (levelTooltipLabel || 'ИПЦ к пред. месяцу')
    : 'Инфляция (12 мес.)';
  const forecastLabel = forecastTooltipLabel
    || (mode === 'cpi' ? 'Прогноз' : 'Прогноз (12 мес.)');
  const compactNumeric = numericTooltipOnly && comparisons.length === 0;

  return (
    <div className={`glass-surface rounded-xl border border-border-subtle px-4 py-3 shadow-2xl ${compactNumeric ? 'min-w-[118px]' : 'min-w-[200px]'}`}>
      <p className="text-xs font-mono text-text-tertiary mb-2">{formatDate(label, dateFormat)}</p>

      {/* Bridge-точка (последний факт, от которого тянется прогнозная линия)
          несёт оба значения — приоритет у факта, иначе последняя фактическая
          точка ошибочно подписывалась «Прогноз». */}
      {actual && (
        <div className={compactNumeric ? 'text-left' : 'flex items-center justify-between gap-4'}>
          {(!numericTooltipOnly || comparisons.length > 0) && (
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-champagne" />
              <span className="max-w-[150px] truncate text-xs text-text-tertiary">
                {actualSeriesLabel || actualLabel}
              </span>
            </div>
          )}
          <span className="text-sm font-mono font-semibold text-champagne">
            {numericTooltipOnly
              ? formatValue(actual.value, valueDigits)
              : `${formatValue(actual.value, valueDigits)}${unitSuffix(unit)}`}
          </span>
        </div>
      )}

      {forecast && !actual && (
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full" style={{ background: '#7C3AED' }} />
            <span className="text-xs text-text-tertiary">{forecastLabel}</span>
          </div>
          <span className="text-sm font-mono font-semibold text-[#7C3AED]">
            {`${formatValue(forecast.value, valueDigits)}${unitSuffix(unit)}`}
          </span>
        </div>
      )}
      {comparisons.map((series, index) => (
        <div
          key={series.dataKey}
          className={`mt-1 flex items-center justify-between gap-4 ${numericTooltipOnly && index === 0 ? 'border-t border-border-subtle pt-1.5' : ''}`}
        >
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: series.color }} />
            <span className="max-w-[150px] truncate text-xs text-text-tertiary">
              {series.label || 'Сравнение'}
            </span>
          </div>
          <span className="font-mono text-sm font-semibold" style={{ color: series.color }}>
            {numericTooltipOnly
              ? formatValue(series.payload.value, valueDigits)
              : `${formatValue(series.payload.value, valueDigits)}${unitSuffix(unit)}`}
          </span>
        </div>
      ))}
    </div>
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
}) {
  const digits = chartValueDigits(unit, chartMode ?? mode);
  const ref = useRef(null);
  const chartAreaRef = useRef(null);
  const rangeOptions = RANGE_PRESETS[rangePreset] || RANGE_PRESETS.default;
  const defaultRange = RANGE_DEFAULTS[rangePreset] || RANGE_DEFAULTS.default;
  const [range, setRange] = useState(defaultRange);
  const [windowOverride, setWindowOverride] = useState(null);
  const [offset, setOffset] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [prevPreset, setPrevPreset] = useState(rangePreset);
  const [chartType, setChartType] = useState(defaultChartType);
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
        color: series.color || '#397C8C',
      }));
    }
    if (comparisonData?.length) {
      return [{
        data: comparisonData,
        dataKey: 'comparison_0',
        label: comparisonLabel || 'Сравнение',
        color: '#397C8C',
      }];
    }
    return [];
  }, [comparisonSeries, comparisonData, comparisonLabel]);

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

  useEffect(() => {
    if (!ref.current) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const tween = gsap.fromTo(ref.current,
      { y: 30, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out', delay: 0.5 }
    );
    return () => tween.kill();
  }, []);

  const chartData = useMemo(() => {
    let base;
    if (mode === 'cpi') {
      const points = cpiData || [];
      const fcValues = forecastData?.forecast?.values || [];
      base = mergeActualForecastChartSeries(points, fcValues, {
        showForecast,
        bridgeLine: chartType !== 'bar',
      });
    } else {
      if (!inflation) return [];
      const actuals = inflation.actuals || [];
      const forecasts = inflation.forecast || [];
      base = mergeActualForecastChartSeries(actuals, forecasts, {
        showForecast,
        bridgeLine: chartType !== 'bar',
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
  }, [inflation, cpiData, forecastData, showForecast, mode, chartType, resolvedComparisonSeries]);

  const dataLen = chartData.length;

  // Полный ряд (факт + прогноз) для выгрузки CSV/Excel — независимо от
  // видимого окна графика. Экспорт обязан отдавать всю историю, не 5-летний срез.
  useEffect(() => { onFullDataRef.current?.(chartData); }, [chartData]);

  const presetWindow = useMemo(() => {
    const opt = rangeOptions.find(r => r.key === range);
    return dateBasedWindowSize(chartData, opt?.months);
  }, [chartData, range, rangeOptions]);

  const windowSize = windowOverride ?? presetWindow;
  const maxOffset = Math.max(0, dataLen - windowSize);
  const clampedOffset = Math.min(Math.max(0, offset), maxOffset);

  const startIdx = Math.max(0, dataLen - windowSize - clampedOffset);
  const endIdx = dataLen - clampedOffset;
  const visibleData = useMemo(
    () => chartData.slice(startIdx, endIdx),
    [chartData, startIdx, endIdx]
  );

  const forecastStartDate = useMemo(() => {
    if (!showForecast) return null;
    for (let i = 0; i < visibleData.length; i++) {
      if (visibleData[i].actual != null && visibleData[i].forecast != null) {
        return visibleData[i].date;
      }
    }
    for (let i = 0; i < visibleData.length; i++) {
      if (visibleData[i].forecast != null) {
        return visibleData[i].date;
      }
    }
    return null;
  }, [visibleData, showForecast]);

  const forecastEndDate = useMemo(() => {
    if (!showForecast) return null;
    for (let i = visibleData.length - 1; i >= 0; i--) {
      if (visibleData[i].forecast != null) {
        return visibleData[i].date;
      }
    }
    return null;
  }, [visibleData, showForecast]);

  useEffect(() => { onChartDataRef.current?.(visibleData); }, [visibleData]);

  const handleRangeChange = (key) => {
    setRange(key);
    setWindowOverride(null);
    setOffset(0);
    onRangeChange?.(key);
    track(events.CHART_RANGE_CHANGE, { range: key, indicator: indicatorCode, indicatorCategory });
  };

  const handleSlider = useCallback((e) => {
    setOffset(maxOffset - Number(e.target.value));
  }, [maxOffset, setOffset]);

  /* ── Wheel zoom (TradingView-style) ── */
  const handleWheel = useCallback((e) => {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    e.stopPropagation();

    const zoomIn = e.deltaY < 0;
    const factor = zoomIn ? 1 / ZOOM_STEP : ZOOM_STEP;
    const current = windowOverride ?? presetWindow;
    const next = Math.max(MIN_WINDOW, Math.min(dataLen, Math.round(current * factor)));
    if (next === current) return;

    const rect = chartAreaRef.current?.getBoundingClientRect();
    if (rect) {
      const mouseRatio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const pointsAdded = next - current;
      const shiftLeft = Math.round(pointsAdded * mouseRatio);
      setOffset(prev => Math.max(0, Math.min(dataLen - next, prev - shiftLeft)));
    }

    setWindowOverride(next);
  }, [windowOverride, presetWindow, dataLen, setOffset, setWindowOverride]);

  useEffect(() => {
    const el = chartAreaRef.current;
    if (!el) return;
    el.addEventListener('wheel', handleWheel, { passive: false });
    return () => el.removeEventListener('wheel', handleWheel);
  }, [handleWheel]);

  /* ── Drag pan ── */
  const handlePointerDown = useCallback((e) => {
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
  }, [clampedOffset]);

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
    }

    d = dragRef.current;
    if (!d || d.phase !== 'dragging') return;

    const deltaX = e.clientX - d.startX;
    const pixelsPerPoint = d.chartWidth / (windowSize || 1);
    const shift = Math.round(deltaX / pixelsPerPoint);
    const newOffset = Math.max(0, Math.min(d.initOffset + shift, maxOffset));
    setOffset(newOffset);
  }, [windowSize, maxOffset, setOffset]);

  const handlePointerUp = useCallback((e) => {
    const d = dragRef.current;
    if (d?.phase === 'dragging') {
      try { e.currentTarget.releasePointerCapture(e.pointerId); } catch { /* ok */ }
    }
    dragRef.current = null;
    setIsDragging(false);
  }, []);

  const { yDomain, yWidth, yTicks } = useMemo(() => {
    if (!visibleData.length) return { yDomain: ['auto', 'auto'], yWidth: 55, yTicks: undefined };
    let min = Infinity; let max = -Infinity;
    for (const row of visibleData) {
      if (row.actual != null) { min = Math.min(min, row.actual); max = Math.max(max, row.actual); }
      if (row.forecast != null) { min = Math.min(min, row.forecast); max = Math.max(max, row.forecast); }
      for (const series of resolvedComparisonSeries) {
        const value = row[series.dataKey];
        if (value != null) { min = Math.min(min, value); max = Math.max(max, value); }
      }
    }
    if (!isFinite(min)) return { yDomain: ['auto', 'auto'], yWidth: 55, yTicks: undefined };

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
    const sampleLabel = formatAxisTick(niceMin < 0 ? niceMin : absMax, digits);
    const w = Math.max(45, Math.min(120, sampleLabel.length * 7.5 + 12));
    return { yDomain: [niceMin, niceMax], yWidth: w, yTicks: ticks };
  }, [visibleData, digits, resolvedComparisonSeries]);

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
  const xTicks = useMemo(() => {
    const cadence = dateFormat === 'annual' || dateFormat === 'quarterly'
      ? dateFormat
      : null;
    return pickChartAxisTicks(visibleData, xTickBudget, {
      cadence,
      plotWidthPx: xAxisPlotWidth,
      formatLabel: formatXAxisLabel,
    });
  }, [visibleData, xTickBudget, dateFormat, xAxisPlotWidth, formatXAxisLabel]);

  const title = cpiChartTitle
    ?? (mode === 'cpi'
      ? 'ИПЦ (к предыдущему месяцу, %)'
      : 'Инфляция (скользящие 12 месяцев)');

  const baselineY = referenceLineY !== undefined
    ? referenceLineY
    : 0;

  const sliderValue = maxOffset - clampedOffset;
  const hasForecast = mode === 'inflation'
    ? inflation?.forecast?.length > 0
    : forecastData?.forecast?.values?.length > 0;

  const isZoomed = windowOverride != null;

  if (!dataLen) {
    return (
      <div className="p-8 md:p-10 rounded-[2rem] bg-surface border border-border-subtle border-dashed shadow-sm min-h-[320px] flex flex-col items-center justify-center text-center gap-4">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-obsidian-lighter border border-border-subtle">
          <Activity className="w-7 h-7 text-champagne/80" aria-hidden />
        </div>
        <div className="max-w-md space-y-2">
          <p className="text-sm font-semibold text-text-primary">Нет данных для графика</p>
          <p className="text-sm text-text-tertiary leading-relaxed">
            {emptyHint || 'Загрузите ряд с сервера или проверьте доступность API. Если данные только что добавлены на backend — обновите страницу.'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div ref={ref} className="p-5 md:p-6 rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03]">
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
          {title}
        </h3>
        {/* ml-auto: при длинном заголовке контролы переносятся на новую строку,
            но всегда прижаты вправо (а не уезжают влево). Созвон 2026-06-16. */}
        <div className="flex items-center gap-2 flex-wrap ml-auto">
          <div
            className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle"
            role="radiogroup"
            aria-label="Тип графика"
          >
            {[
              { key: 'area', label: 'Линия с заливкой', icon: AreaIcon },
              { key: 'line', label: 'Линия', icon: LineIcon },
              { key: 'bar', label: 'Столбцы', icon: BarChart3 },
            ].map((opt) => {
              const IconComp = opt.icon;
              return (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => setChartType(opt.key)}
                  role="radio"
                  aria-checked={chartType === opt.key}
                  aria-label={opt.label}
                  title={opt.label}
                  className={cn(
                    'p-1.5 rounded-lg transition-colors duration-200',
                    chartType === opt.key
                      ? 'bg-champagne/15 text-champagne'
                      : 'text-text-tertiary hover:text-text-secondary'
                  )}
                >
                  <IconComp className="w-3.5 h-3.5" aria-hidden="true" />
                </button>
              );
            })}
          </div>
          {isZoomed && (
            <button
              type="button"
              onClick={() => { setWindowOverride(null); setOffset(0); track(events.CHART_ZOOM, { action: 'reset', indicator: indicatorCode, indicatorCategory }); }}
              className="px-2 py-1.5 text-[10px] font-mono uppercase tracking-wider text-text-tertiary hover:text-champagne transition-colors"
              title="Сбросить зум"
            >
              Сброс
            </button>
          )}
          <div className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle">
            {rangeOptions.map(opt => (
              <button
                key={opt.key}
                type="button"
                onClick={() => handleRangeChange(opt.key)}
                className={cn(
                  'px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
                  range === opt.key && !isZoomed
                    ? 'bg-champagne/15 text-champagne'
                    : 'text-text-tertiary hover:text-text-secondary'
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div
        ref={chartAreaRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}
        className={cn(
          'rounded-xl relative',
          isDragging ? 'cursor-grabbing select-none' : 'cursor-crosshair'
        )}
        style={{ touchAction: 'pan-y' }}
      >
        <div
          aria-hidden="true"
          className="pointer-events-none absolute left-1/2 top-[46%] z-10 -translate-x-1/2 -translate-y-1/2 -rotate-6 select-none whitespace-nowrap text-3xl font-display font-bold tracking-[0.18em] text-text-primary opacity-[0.055] md:text-5xl"
        >
          Forecast Economy
        </div>

        <ResponsiveContainer width="100%" height={420}>
          <ComposedChart data={visibleData} margin={{ top: 12, right: 36, bottom: 16, left: 0 }}>
            <defs>
              <linearGradient id="inflGradActual" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#B8942F" stopOpacity={0.15} />
                <stop offset="100%" stopColor="#B8942F" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(0,0,0,0.06)"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              tickFormatter={formatXAxisLabel}
              stroke="rgba(0,0,0,0.1)"
              tick={{ fill: 'rgba(0,0,0,0.4)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
              tickLine={false}
              ticks={xTicks}
              interval={0}
              tickMargin={10}
              height={42}
              padding={{ left: 8, right: 24 }}
            />
            <YAxis
              stroke="rgba(0,0,0,0.1)"
              tick={{ fill: 'rgba(0,0,0,0.4)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
              tickLine={false}
              axisLine={false}
              domain={yDomain}
              ticks={yTicks}
              tickFormatter={v => formatAxisTick(v, digits)}
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
              cursor={isDragging || !isHovering ? false : { stroke: 'rgba(0,0,0,0.15)', strokeWidth: 1 }}
              active={isHovering && !isDragging}
            />
            {baselineY !== null && (
              <ReferenceLine y={baselineY} stroke="rgba(0,0,0,0.12)" strokeDasharray="6 3" />
            )}

            {/* Полоса прогноза: только для area/line. Для bar её скрываем —
                столбцы прогноза уже отдельным цветом, заливка дублирует. */}
            {forecastStartDate && forecastEndDate && showForecast && chartType !== 'bar' && (
              <ReferenceArea
                x1={forecastStartDate}
                x2={forecastEndDate}
                fill="#7C3AED"
                fillOpacity={0.06}
                stroke="none"
                ifOverflow="visible"
                style={{ pointerEvents: 'none' }}
              />
            )}
            {forecastStartDate && showForecast && chartType !== 'bar' && (
              <ReferenceLine
                x={forecastStartDate}
                stroke="rgba(124,58,237,0.45)"
                strokeDasharray="4 4"
                strokeWidth={1}
                style={{ pointerEvents: 'none' }}
              />
            )}

            {chartType === 'bar' ? (
              <Bar
                dataKey="actual"
                fill="#B8942F"
                fillOpacity={0.7}
                stroke="#B8942F"
                isAnimationActive={false}
                maxBarSize={28}
              />
            ) : chartType === 'line' ? (
              <Line
                dataKey="actual"
                stroke="#B8942F"
                strokeWidth={2}
                dot={false}
                activeDot={isDragging ? false : { r: 4, fill: '#B8942F', stroke: '#FFFFFF', strokeWidth: 2 }}
                isAnimationActive={false}
                connectNulls
              />
            ) : (
              <Area
                dataKey="actual"
                stroke="#B8942F"
                strokeWidth={2}
                fill="url(#inflGradActual)"
                dot={false}
                activeDot={isDragging ? false : { r: 4, fill: '#B8942F', stroke: '#FFFFFF', strokeWidth: 2 }}
                isAnimationActive={false}
                connectNulls
              />
            )}

            {showForecast && (
              chartType === 'bar' ? (
                <Bar
                  dataKey="forecast"
                  fill="#7C3AED"
                  fillOpacity={0.55}
                  stroke="#7C3AED"
                  isAnimationActive={false}
                  maxBarSize={28}
                />
              ) : (
                <Line
                  dataKey="forecast"
                  stroke="#7C3AED"
                  strokeWidth={2.5}
                  connectNulls
                  strokeDasharray="8 4"
                  dot={false}
                  activeDot={isDragging ? false : { r: 5, fill: '#7C3AED', stroke: '#FFFFFF', strokeWidth: 2 }}
                  isAnimationActive={false}
                />
              )
            )}
            {resolvedComparisonSeries.map((series) => (
              <Line
                key={series.dataKey}
                dataKey={series.dataKey}
                stroke={series.color}
                strokeWidth={2}
                connectNulls
                dot={false}
                activeDot={isDragging ? false : { r: 4, fill: series.color, stroke: '#FFFFFF', strokeWidth: 2 }}
                isAnimationActive={false}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>

        {isHovering && !isDragging && (
          <div className="mt-1 flex justify-end pr-3">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-obsidian/70 backdrop-blur-sm border border-border-subtle/50 pointer-events-none opacity-60 transition-opacity">
              <ZoomIn className="w-3 h-3 text-text-tertiary" />
              <span className="text-[10px] font-mono text-text-tertiary">Ctrl + scroll — зум, drag — сдвиг</span>
            </div>
          </div>
        )}

      </div>

      {maxOffset > 0 && (
        <div className="px-2 mt-2">
          <input
            type="range"
            min={0}
            max={maxOffset}
            value={sliderValue}
            onChange={handleSlider}
            aria-label="Позиция окна по времени"
            className="w-full h-1.5 appearance-none bg-obsidian-lighter rounded-full
              [&::-webkit-slider-thumb]:appearance-none
              [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
              [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-champagne
              [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:shadow-md
              [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4
              [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-champagne
              [&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:border-0"
          />
          <div className="flex justify-between text-[10px] font-mono text-text-tertiary mt-1">
            <span>{visibleData[0] ? formatDate(visibleData[0].date, dateFormat) : ''}</span>
            <span>{visibleData.length ? formatDate(visibleData[visibleData.length - 1].date, dateFormat) : ''}</span>
          </div>
        </div>
      )}

      {resolvedComparisonSeries.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-border-subtle pt-3">
          <div className="flex items-center gap-2">
            <span className="h-0.5 w-5 rounded-full bg-champagne" />
            <span className="text-[11px] text-text-tertiary">{actualSeriesLabel || 'Основной ряд'}</span>
          </div>
          {resolvedComparisonSeries.map((series) => (
            <div key={series.dataKey} className="flex min-w-0 items-center gap-2">
              <span className="h-0.5 w-5 shrink-0 rounded-full" style={{ backgroundColor: series.color }} />
              <span className="max-w-[14rem] truncate text-[11px] text-text-tertiary">{series.label}</span>
            </div>
          ))}
        </div>
      )}

      {showForecast && hasForecast && (
        <div className="flex items-center gap-5 mt-4 pt-3 border-t border-border-subtle">
          <div className="flex items-center gap-2">
            <span className="w-5 h-0.5 bg-champagne rounded-full" />
            <span className="text-[11px] text-text-tertiary">Факт</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-5 h-0.5 rounded-full" style={{ background: '#7C3AED', opacity: 0.8 }} />
            <span className="text-[11px] text-text-tertiary">Прогноз</span>
          </div>
        </div>
      )}
    </div>
  );
}
