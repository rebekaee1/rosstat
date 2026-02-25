import { useEffect, useRef, useMemo, useState } from 'react';
import gsap from 'gsap';
import {
  ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine,
} from 'recharts';
import { formatDate, cn } from '../lib/format';

const RANGE_OPTIONS = [
  { key: '3y', label: '3 года', months: 36 },
  { key: '5y', label: '5 лет', months: 60 },
  { key: '10y', label: '10 лет', months: 120 },
  { key: 'all', label: 'Все', months: null },
];

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  const actual = payload.find(p => p.dataKey === 'actual' && p.value != null);
  const forecast = payload.find(p => p.dataKey === 'forecast' && p.value != null);
  const upper = payload.find(p => p.dataKey === 'upper' && p.value != null);
  const lower = payload.find(p => p.dataKey === 'lower' && p.value != null);

  return (
    <div className="glass-surface rounded-xl border border-border-subtle px-4 py-3 shadow-2xl min-w-[200px]">
      <p className="text-xs font-mono text-text-tertiary mb-2">{formatDate(label, 'full')}</p>

      {actual && (
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-champagne" />
            <span className="text-xs text-text-tertiary">Инфляция (12 мес.)</span>
          </div>
          <span className="text-sm font-mono font-semibold text-champagne">
            {actual.value.toFixed(2)}%
          </span>
        </div>
      )}

      {forecast && !actual && (
        <>
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full" style={{ background: '#A78BFA' }} />
              <span className="text-xs text-text-tertiary">Прогноз (12 мес.)</span>
            </div>
            <span className="text-sm font-mono font-semibold text-[#A78BFA]">
              {forecast.value.toFixed(2)}%
            </span>
          </div>
          {lower && upper && (
            <div className="flex items-center justify-between gap-4 mt-1.5 pt-1.5 border-t border-white/5">
              <span className="text-[10px] text-text-tertiary">95% CI</span>
              <span className="text-[10px] font-mono text-text-tertiary">
                {lower.value.toFixed(2)} – {upper.value.toFixed(2)}%
              </span>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function CpiChart({ inflation, showForecast = true }) {
  const ref = useRef(null);
  const [range, setRange] = useState('5y');

  useEffect(() => {
    if (!ref.current) return;
    gsap.fromTo(ref.current,
      { y: 30, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out', delay: 0.5 }
    );
  }, []);

  const { chartData, forecastStartDate } = useMemo(() => {
    if (!inflation) return { chartData: [], forecastStartDate: null };

    const actuals = inflation.actuals || [];
    const forecasts = inflation.forecast || [];

    const rangeOpt = RANGE_OPTIONS.find(r => r.key === range);
    let sliced = actuals;
    if (rangeOpt?.months && sliced.length > rangeOpt.months) {
      sliced = sliced.slice(-rangeOpt.months);
    }

    const merged = sliced.map(a => ({ date: a.date, actual: a.value }));

    let startDate = null;

    if (showForecast && forecasts.length > 0 && merged.length > 0) {
      const last = merged[merged.length - 1];
      last.forecast = last.actual;
      startDate = last.date;

      for (const fp of forecasts) {
        merged.push({
          date: fp.date,
          forecast: fp.value,
          lower: fp.lower_bound,
          upper: fp.upper_bound,
        });
      }
    }

    return { chartData: merged, forecastStartDate: startDate };
  }, [inflation, showForecast, range]);

  return (
    <div ref={ref} className="p-5 md:p-6 rounded-[2rem] bg-surface border border-border-subtle">
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
          Инфляция (скользящие 12 месяцев)
        </h3>
        <div className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle">
          {RANGE_OPTIONS.map(opt => (
            <button
              key={opt.key}
              onClick={() => setRange(opt.key)}
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

      <ResponsiveContainer width="100%" height={380}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: -5 }}>
          <defs>
            <linearGradient id="inflGradActual" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#C9A84C" stopOpacity={0.2} />
              <stop offset="100%" stopColor="#C9A84C" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="inflGradCI" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#A78BFA" stopOpacity={0.12} />
              <stop offset="100%" stopColor="#A78BFA" stopOpacity={0.02} />
            </linearGradient>
          </defs>

          <CartesianGrid
            strokeDasharray="3 3"
            stroke="rgba(255,255,255,0.04)"
            vertical={false}
          />
          <XAxis
            dataKey="date"
            tickFormatter={d => formatDate(d)}
            stroke="rgba(255,255,255,0.1)"
            tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            tickLine={false}
            interval="preserveStartEnd"
            minTickGap={50}
          />
          <YAxis
            stroke="rgba(255,255,255,0.1)"
            tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            tickLine={false}
            axisLine={false}
            domain={['auto', 'auto']}
            tickFormatter={v => `${v}%`}
            width={55}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.08)' }} />
          <ReferenceLine y={0} stroke="rgba(255,255,255,0.12)" strokeDasharray="6 3" />

          {forecastStartDate && showForecast && (
            <ReferenceLine
              x={forecastStartDate}
              stroke="rgba(167,139,250,0.35)"
              strokeDasharray="4 4"
              strokeWidth={1}
            />
          )}

          <Area
            dataKey="actual"
            stroke="#C9A84C"
            strokeWidth={2}
            fill="url(#inflGradActual)"
            dot={false}
            activeDot={{ r: 4, fill: '#C9A84C', stroke: '#0D0D12', strokeWidth: 2 }}
          />

          {showForecast && (
            <>
              <Area
                dataKey="upper"
                stroke="none"
                fill="url(#inflGradCI)"
                dot={false}
                activeDot={false}
              />
              <Area
                dataKey="lower"
                stroke="none"
                fill="#16161E"
                dot={false}
                activeDot={false}
              />
              <Line
                dataKey="upper"
                stroke="rgba(167,139,250,0.2)"
                strokeWidth={1}
                strokeDasharray="3 3"
                dot={false}
                activeDot={false}
              />
              <Line
                dataKey="lower"
                stroke="rgba(167,139,250,0.2)"
                strokeWidth={1}
                strokeDasharray="3 3"
                dot={false}
                activeDot={false}
              />
              <Line
                dataKey="forecast"
                stroke="#A78BFA"
                strokeWidth={2.5}
                strokeDasharray="8 4"
                dot={false}
                activeDot={{ r: 5, fill: '#A78BFA', stroke: '#0D0D12', strokeWidth: 2 }}
              />
            </>
          )}
        </ComposedChart>
      </ResponsiveContainer>

      {showForecast && inflation?.forecast?.length > 0 && (
        <div className="flex items-center gap-5 mt-4 pt-3 border-t border-border-subtle">
          <div className="flex items-center gap-2">
            <span className="w-5 h-0.5 bg-champagne rounded-full" />
            <span className="text-[11px] text-text-tertiary">Факт</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-5 h-0.5 rounded-full" style={{ background: '#A78BFA', opacity: 0.8 }} />
            <span className="text-[11px] text-text-tertiary">Прогноз OLS</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-5 h-3 rounded-sm" style={{ background: 'rgba(167,139,250,0.15)' }} />
            <span className="text-[11px] text-text-tertiary">95% CI</span>
          </div>
        </div>
      )}
    </div>
  );
}
