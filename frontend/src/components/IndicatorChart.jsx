import { useEffect, useRef, useMemo, useState, useCallback } from 'react';
import gsap from 'gsap';
import {
  ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine,
} from 'recharts';
import { Activity, ZoomIn } from 'lucide-react';
import { formatDate, formatValue, formatAxisTick, formatValueWithUnit, unitSuffix, unitDigits, cn } from '../lib/format';

const RANGE_OPTIONS = [
  { key: '3y', label: '3 года', months: 36 },
  { key: '5y', label: '5 лет', months: 60 },
  { key: '10y', label: '10 лет', months: 120 },
  { key: 'all', label: 'Все', months: null },
];

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

function CustomTooltip({ active, payload, label, mode, levelTooltipLabel, dateFormat = 'full', unit = '%', visible = true }) {
  if (!visible || !active || !payload?.length) return null;

  const actual = payload.find(p => p.dataKey === 'actual' && p.value != null);
  const forecast = payload.find(p => p.dataKey === 'forecast' && p.value != null);

  const actualLabel = mode === 'cpi'
    ? (levelTooltipLabel || 'ИПЦ к пред. месяцу')
    : 'Инфляция (12 мес.)';
  const forecastLabel = mode === 'cpi' ? 'Прогноз' : 'Прогноз (12 мес.)';

  return (
    <div className="glass-surface rounded-xl border border-border-subtle px-4 py-3 shadow-2xl min-w-[200px]">
      <p className="text-xs font-mono text-text-tertiary mb-2">{formatDate(label, dateFormat)}</p>

      {actual && (
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-champagne" />
            <span className="text-xs text-text-tertiary">{actualLabel}</span>
          </div>
          <span className="text-sm font-mono font-semibold text-champagne">
            {formatValueWithUnit(actual.value, unit)}
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
            {formatValueWithUnit(forecast.value, unit)}
          </span>
        </div>
      )}
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
  onRangeChange,
  referenceLineY,
  cpiChartTitle,
  levelTooltipLabel,
  emptyHint,
  dateFormat = 'full',
  unit = '%',
}) {
  const ref = useRef(null);
  const chartAreaRef = useRef(null);
  const [range, setRange] = useState('5y');
  const [windowOverride, setWindowOverride] = useState(null);
  const [offset, setOffset] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const dragRef = useRef(null);
  const onChartDataRef = useRef(onChartData);

  useEffect(() => { onChartDataRef.current = onChartData; }, [onChartData]);

  useEffect(() => {
    if (!ref.current) return;
    gsap.fromTo(ref.current,
      { y: 30, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out', delay: 0.5 }
    );
  }, []);

  const chartData = useMemo(() => {
    if (mode === 'cpi') {
      const points = cpiData || [];
      const fcValues = forecastData?.forecast?.values || [];
      const merged = points.map(p => ({ date: p.date, actual: p.value }));

      if (showForecast && fcValues.length > 0 && merged.length > 0) {
        const last = merged[merged.length - 1];
        last.forecast = last.actual;
        for (const fv of fcValues) {
          merged.push({ date: fv.date, forecast: fv.value });
        }
      }
      return merged;
    }

    if (!inflation) return [];

    const actuals = inflation.actuals || [];
    const forecasts = inflation.forecast || [];
    const merged = actuals.map(a => ({ date: a.date, actual: a.value }));

    if (showForecast && forecasts.length > 0 && merged.length > 0) {
      const last = merged[merged.length - 1];
      last.forecast = last.actual;
      for (const fp of forecasts) {
        merged.push({ date: fp.date, forecast: fp.value });
      }
    }
    return merged;
  }, [inflation, cpiData, forecastData, showForecast, mode]);

  const dataLen = chartData.length;

  const presetWindow = useMemo(() => {
    const opt = RANGE_OPTIONS.find(r => r.key === range);
    return dateBasedWindowSize(chartData, opt?.months);
  }, [chartData, range]);

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
    return null;
  }, [visibleData, showForecast]);

  useEffect(() => { onChartDataRef.current?.(visibleData); }, [visibleData]);

  const handleRangeChange = (key) => {
    setRange(key);
    setWindowOverride(null);
    setOffset(0);
    onRangeChange?.(key);
  };

  const handleSlider = useCallback((e) => {
    setOffset(maxOffset - Number(e.target.value));
  }, [maxOffset]);

  /* ── Wheel zoom (TradingView-style) ── */
  const handleWheel = useCallback((e) => {
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
  }, [windowOverride, presetWindow, dataLen]);

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
  }, [windowSize, maxOffset]);

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
    }
    if (!isFinite(min)) return { yDomain: ['auto', 'auto'], yWidth: 55, yTicks: undefined };

    const range = max - min || 1;
    const rough = range / 5;
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
    const sampleLabel = formatAxisTick(niceMin < 0 ? niceMin : absMax, unitDigits(unit));
    const w = Math.max(45, Math.min(120, sampleLabel.length * 7.5 + 12));
    return { yDomain: [niceMin, niceMax], yWidth: w, yTicks: ticks };
  }, [visibleData, unit]);

  const title = mode === 'cpi'
    ? (cpiChartTitle || 'ИПЦ (к предыдущему месяцу, %)')
    : 'Инфляция (скользящие 12 месяцев)';

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
        <div className="flex items-center gap-2">
          {isZoomed && (
            <button
              type="button"
              onClick={() => { setWindowOverride(null); setOffset(0); }}
              className="px-2 py-1.5 text-[10px] font-mono uppercase tracking-wider text-text-tertiary hover:text-champagne transition-colors"
              title="Сбросить зум"
            >
              Сброс
            </button>
          )}
          <div className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle">
            {RANGE_OPTIONS.map(opt => (
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
        <ResponsiveContainer width="100%" height={420}>
          <ComposedChart data={visibleData} margin={{ top: 5, right: 10, bottom: 5, left: -5 }}>
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
              tickFormatter={d => formatDate(d)}
              stroke="rgba(0,0,0,0.1)"
              tick={{ fill: 'rgba(0,0,0,0.4)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
              tickLine={false}
              interval="preserveStartEnd"
              minTickGap={50}
            />
            <YAxis
              stroke="rgba(0,0,0,0.1)"
              tick={{ fill: 'rgba(0,0,0,0.4)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
              tickLine={false}
              axisLine={false}
              domain={yDomain}
              ticks={yTicks}
              tickFormatter={v => formatAxisTick(v, unitDigits(unit))}
              width={yWidth}
            />
            <Tooltip
              content={<CustomTooltip mode={mode} levelTooltipLabel={levelTooltipLabel} dateFormat={dateFormat} unit={unit} visible={isHovering} />}
              cursor={isDragging || !isHovering ? false : { stroke: 'rgba(0,0,0,0.15)', strokeWidth: 1 }}
              active={isHovering && !isDragging}
            />
            {baselineY !== null && (
              <ReferenceLine y={baselineY} stroke="rgba(0,0,0,0.12)" strokeDasharray="6 3" />
            )}

            {forecastStartDate && showForecast && (
              <ReferenceLine
                x={forecastStartDate}
                stroke="rgba(124,58,237,0.35)"
                strokeDasharray="4 4"
                strokeWidth={1}
              />
            )}

            <Area
              dataKey="actual"
              stroke="#B8942F"
              strokeWidth={2}
              fill="url(#inflGradActual)"
              dot={false}
              activeDot={isDragging ? false : { r: 4, fill: '#B8942F', stroke: '#FFFFFF', strokeWidth: 2 }}
              isAnimationActive={false}
            />

            {showForecast && (
              <Line
                dataKey="forecast"
                stroke="#7C3AED"
                strokeWidth={2.5}
                strokeDasharray="8 4"
                dot={false}
                activeDot={isDragging ? false : { r: 5, fill: '#7C3AED', stroke: '#FFFFFF', strokeWidth: 2 }}
                isAnimationActive={false}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>

        {isHovering && !isDragging && (
          <div className="absolute bottom-3 right-3 flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-obsidian/70 backdrop-blur-sm border border-border-subtle/50 pointer-events-none opacity-60 transition-opacity">
            <ZoomIn className="w-3 h-3 text-text-tertiary" />
            <span className="text-[10px] font-mono text-text-tertiary">scroll — зум · drag — сдвиг</span>
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
            <span>{visibleData[0] ? formatDate(visibleData[0].date) : ''}</span>
            <span>{visibleData.length ? formatDate(visibleData[visibleData.length - 1].date) : ''}</span>
          </div>
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
