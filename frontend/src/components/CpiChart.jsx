import { useEffect, useRef, useMemo, useState } from 'react';
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
  const [range, setRange] = useState('5y');
  const [brushRange, setBrushRange] = useState({ start: 0, end: 0 });

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

  useEffect(() => {
    if (!chartData.length) return;
    const opt = RANGE_OPTIONS.find(r => r.key === range);
    const window = opt?.months ?? chartData.length;
    setBrushRange({
      start: Math.max(0, chartData.length - window),
      end: chartData.length - 1,
    });
  }, [chartData.length, mode]);

  const handleRangeChange = (key) => {
    setRange(key);
    onRangeChange?.(key);
    const opt = RANGE_OPTIONS.find(r => r.key === key);
    const window = opt?.months ?? chartData.length;
    setBrushRange({
      start: Math.max(0, chartData.length - window),
      end: chartData.length - 1,
    });
  };

  useEffect(() => {
    if (!chartData.length) return;
    const visible = chartData.slice(brushRange.start, brushRange.end + 1);
    onChartData?.(visible);
  }, [chartData, brushRange, onChartData]);

  const title = mode === 'cpi'
    ? 'ИПЦ (к предыдущему месяцу, %)'
    : 'Инфляция (скользящие 12 месяцев)';

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
            width={55}
          />
          <Tooltip content={<CustomTooltip mode={mode} />} cursor={{ stroke: 'rgba(0,0,0,0.08)' }} />
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
            activeDot={{ r: 4, fill: '#B8942F', stroke: '#FFFFFF', strokeWidth: 2 }}
          />

          {showForecast && (
            <Line
              dataKey="forecast"
              stroke="#7C3AED"
              strokeWidth={2.5}
              strokeDasharray="8 4"
              dot={false}
              activeDot={{ r: 5, fill: '#7C3AED', stroke: '#FFFFFF', strokeWidth: 2 }}
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
            onChange={({ startIndex, endIndex }) => setBrushRange({ start: startIndex, end: endIndex })}
            travellerWidth={8}
          />
        </ComposedChart>
      </ResponsiveContainer>

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
