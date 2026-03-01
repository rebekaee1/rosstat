import { useEffect, useRef, useMemo, useState, useCallback } from 'react';
import gsap from 'gsap';
import {
  ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine, Brush,
} from 'recharts';
import { formatDate, cn } from '../lib/format';

const RANGE_OPTIONS = [
  { key: '3y', label: '3 года', months: 36 },
  { key: '5y', label: '5 лет', months: 60 },
  { key: '10y', label: '10 лет', months: 120 },
  { key: 'all', label: 'Все', months: null },
];

function CustomTooltip({ active, payload, label, mode }) {
  if (!active || !payload?.length) return null;

  const actual = payload.find(p => p.dataKey === 'actual' && p.value != null);
  const forecast = payload.find(p => p.dataKey === 'forecast' && p.value != null);

  const actualLabel = mode === 'cpi' ? 'ИПЦ к пред. месяцу' : 'Инфляция (12 мес.)';
  const forecastLabel = mode === 'cpi' ? 'Прогноз ИПЦ' : 'Прогноз (12 мес.)';

  return (
    <div className="glass-surface rounded-xl border border-border-subtle px-4 py-3 shadow-2xl min-w-[200px]">
      <p className="text-xs font-mono text-text-tertiary mb-2">{formatDate(label, 'full')}</p>

      {actual && (
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-champagne" />
            <span className="text-xs text-text-tertiary">{actualLabel}</span>
          </div>
          <span className="text-sm font-mono font-semibold text-champagne">
            {actual.value.toFixed(2)}%
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
            {forecast.value.toFixed(2)}%
          </span>
        </div>
      )}
    </div>
  );
}

export default function CpiChart({
  inflation,
  showForecast = true,
  mode = 'inflation',
  cpiData,
  forecastData,
  onChartData,
  onRangeChange,
}) {
  const ref = useRef(null);
  const chartAreaRef = useRef(null);
  const [range, setRange] = useState('5y');
  const [brushRange, setBrushRange] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef(null);
  const onChartDataRef = useRef(onChartData);
  onChartDataRef.current = onChartData;

  useEffect(() => {
    if (!ref.current) return;
    gsap.fromTo(ref.current,
      { y: 30, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out', delay: 0.5 }
    );
  }, []);

  const { chartData, forecastStartDate } = useMemo(() => {
    if (mode === 'cpi') {
      const points = cpiData || [];
      const fcValues = forecastData?.forecast?.values || [];

      const merged = points.map(p => ({ date: p.date, actual: p.value }));
      let startDate = null;

      if (showForecast && fcValues.length > 0 && merged.length > 0) {
        const last = merged[merged.length - 1];
        last.forecast = last.actual;
        startDate = last.date;

        for (const fv of fcValues) {
          merged.push({ date: fv.date, forecast: fv.value });
        }
      }

      return { chartData: merged, forecastStartDate: startDate };
    }

    if (!inflation) return { chartData: [], forecastStartDate: null };

    const actuals = inflation.actuals || [];
    const forecasts = inflation.forecast || [];

    const merged = actuals.map(a => ({ date: a.date, actual: a.value }));
    let startDate = null;

    if (showForecast && forecasts.length > 0 && merged.length > 0) {
      const last = merged[merged.length - 1];
      last.forecast = last.actual;
      startDate = last.date;

      for (const fp of forecasts) {
        merged.push({ date: fp.date, forecast: fp.value });
      }
    }

    return { chartData: merged, forecastStartDate: startDate };
  }, [inflation, cpiData, forecastData, showForecast, mode]);

  const dataLen = chartData.length;

  useEffect(() => {
    if (!dataLen) return;
    const opt = RANGE_OPTIONS.find(r => r.key === range);
    const win = opt?.months ?? dataLen;
    const newStart = Math.max(0, dataLen - win);
    const newEnd = dataLen - 1;
    setBrushRange({ start: newStart, end: newEnd });
    onChartDataRef.current?.(chartData.slice(newStart, newEnd + 1));
  }, [dataLen, mode]);

  const handleRangeChange = (key) => {
    setRange(key);
    onRangeChange?.(key);
    const opt = RANGE_OPTIONS.find(r => r.key === key);
    const win = opt?.months ?? dataLen;
    const newStart = Math.max(0, dataLen - win);
    const newEnd = dataLen - 1;
    setBrushRange({ start: newStart, end: newEnd });
    onChartDataRef.current?.(chartData.slice(newStart, newEnd + 1));
  };

  const handleBrushChange = useCallback(({ startIndex, endIndex }) => {
    setBrushRange(prev => {
      if (prev && prev.start === startIndex && prev.end === endIndex) return prev;
      return { start: startIndex, end: endIndex };
    });
    onChartDataRef.current?.(chartData.slice(startIndex, endIndex + 1));
  }, [chartData]);

  const applyPan = useCallback((newStart, newEnd) => {
    setBrushRange({ start: newStart, end: newEnd });
    onChartDataRef.current?.(chartData.slice(newStart, newEnd + 1));
  }, [chartData]);

  const handlePointerDown = useCallback((e) => {
    if (e.target.closest('.recharts-brush')) return;
    const rect = chartAreaRef.current?.getBoundingClientRect();
    if (!rect || !brushRange) return;
    dragRef.current = {
      startX: e.clientX,
      initStart: brushRange.start,
      initEnd: brushRange.end,
      chartWidth: rect.width,
    };
    setIsDragging(true);
    e.currentTarget.setPointerCapture(e.pointerId);
  }, [brushRange]);

  const handlePointerMove = useCallback((e) => {
    const d = dragRef.current;
    if (!d) return;
    const deltaX = e.clientX - d.startX;
    const windowSize = d.initEnd - d.initStart;
    const pixelsPerPoint = d.chartWidth / (windowSize || 1);
    const shift = -Math.round(deltaX / pixelsPerPoint);
    let newStart = d.initStart + shift;
    newStart = Math.max(0, Math.min(newStart, dataLen - 1 - windowSize));
    const newEnd = newStart + windowSize;
    applyPan(newStart, newEnd);
  }, [dataLen, applyPan]);

  const handlePointerUp = useCallback((e) => {
    if (!dragRef.current) return;
    dragRef.current = null;
    setIsDragging(false);
    e.currentTarget.releasePointerCapture(e.pointerId);
  }, []);

  const title = mode === 'cpi'
    ? 'ИПЦ (к предыдущему месяцу, %)'
    : 'Инфляция (скользящие 12 месяцев)';

  if (!brushRange) return null;

  return (
    <div ref={ref} className="p-5 md:p-6 rounded-[2rem] bg-surface border border-border-subtle">
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
          {title}
        </h3>
        <div className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle">
          {RANGE_OPTIONS.map(opt => (
            <button
              key={opt.key}
              onClick={() => handleRangeChange(opt.key)}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
                range === opt.key
                  ? 'bg-champagne/15 text-champagne'
                  : 'text-text-tertiary hover:text-text-secondary'
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div
        ref={chartAreaRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        className={isDragging ? 'cursor-grabbing select-none' : 'cursor-grab'}
        style={{ touchAction: 'pan-y' }}
      >
        <ResponsiveContainer width="100%" height={420}>
          <ComposedChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: -5 }}>
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
            domain={['auto', 'auto']}
            tickFormatter={v => `${v}%`}
            width={mode === 'cpi' ? 70 : 55}
          />
            <Tooltip
              content={<CustomTooltip mode={mode} />}
              cursor={isDragging ? false : { stroke: 'rgba(0,0,0,0.08)' }}
              active={!isDragging}
            />
            <ReferenceLine y={mode === 'cpi' ? 100 : 0} stroke="rgba(0,0,0,0.12)" strokeDasharray="6 3" />

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
            />

            {showForecast && (
              <Line
                dataKey="forecast"
                stroke="#7C3AED"
                strokeWidth={2.5}
                strokeDasharray="8 4"
                dot={false}
                activeDot={isDragging ? false : { r: 5, fill: '#7C3AED', stroke: '#FFFFFF', strokeWidth: 2 }}
              />
            )}

            <Brush
              dataKey="date"
              height={30}
              stroke="#B8942F"
              fill="#F8F9FC"
              tickFormatter={d => formatDate(d)}
              startIndex={brushRange.start}
              endIndex={brushRange.end}
              onChange={handleBrushChange}
              travellerWidth={8}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {showForecast && (
        (mode === 'inflation' ? inflation?.forecast?.length > 0 : forecastData?.forecast?.values?.length > 0) && (
          <div className="flex items-center gap-5 mt-4 pt-3 border-t border-border-subtle">
            <div className="flex items-center gap-2">
              <span className="w-5 h-0.5 bg-champagne rounded-full" />
              <span className="text-[11px] text-text-tertiary">Факт</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-5 h-0.5 rounded-full" style={{ background: '#7C3AED', opacity: 0.8 }} />
              <span className="text-[11px] text-text-tertiary">Прогноз OLS</span>
            </div>
          </div>
        )
      )}
    </div>
  );
}
