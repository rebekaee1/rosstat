import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine,
} from 'recharts';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { useIndicator, useIndicatorData, useForecast } from '../lib/hooks';
import { formatDate, formatAxisTick, formatValueWithUnit, formatChange, unitDigits, isCpiIndex, cn } from '../lib/format';
import { useEmbedParams, useEmbedImpression, useEmbedAutoHeight, PERIODS, THEME_COLORS } from './useEmbedParams';
import Attribution from './Attribution';

function EmbedTooltip({ active, payload, label, unit, colors }) {
  if (!active || !payload?.length) return null;
  const actual = payload.find(p => p.dataKey === 'actual' && p.value != null && !isNaN(p.value));
  const forecast = payload.find(p => p.dataKey === 'forecast' && p.value != null && !isNaN(p.value));
  if (!actual && !forecast) return null;

  return (
    <div style={{
      background: colors.bg, border: `1px solid ${colors.border}`,
      borderRadius: 8, padding: '8px 12px', fontSize: 12,
      fontFamily: 'system-ui, sans-serif', boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
    }}>
      <div style={{ color: colors.textTertiary, fontSize: 10, marginBottom: 4, fontFamily: 'ui-monospace, monospace' }}>
        {formatDate(label)}
      </div>
      {actual && (
        <div style={{ color: '#B8942F', fontWeight: 600, fontFamily: 'ui-monospace, monospace' }}>
          {formatValueWithUnit(actual.value, unit)}
        </div>
      )}
      {forecast && !actual && (
        <div style={{ color: '#7C3AED', fontWeight: 600, fontFamily: 'ui-monospace, monospace' }}>
          {formatValueWithUnit(forecast.value, unit)}
        </div>
      )}
    </div>
  );
}

export default function EmbedChart() {
  const { code } = useParams();
  const { theme, height, period: initPeriod, showTitle, showForecast } = useEmbedParams();
  const [period, setPeriod] = useState(initPeriod);
  const colors = THEME_COLORS[theme];

  useEmbedImpression(code, 'chart');
  useEmbedAutoHeight();

  const { data: meta } = useIndicator(code);
  const { data: dataResp, isLoading } = useIndicatorData(code);
  const { data: forecastResp } = useForecast(code);

  const chartData = useMemo(() => {
    const points = dataResp?.data || [];
    if (!points.length) return [];

    const periodObj = PERIODS.find(p => p.key === period);
    let filtered = points;
    if (periodObj?.months) {
      const cutoff = new Date();
      cutoff.setMonth(cutoff.getMonth() - periodObj.months);
      const cutStr = cutoff.toISOString().slice(0, 10);
      filtered = points.filter(p => p.date >= cutStr);
    }

    const merged = filtered.map(p => ({ date: p.date, actual: p.value }));

    if (showForecast && forecastResp?.forecast?.values?.length && merged.length) {
      const fcVals = forecastResp.forecast.values;
      merged[merged.length - 1].forecast = merged[merged.length - 1].actual;
      for (const fv of fcVals) merged.push({ date: fv.date, forecast: fv.value });
    }
    return merged;
  }, [dataResp, forecastResp, period, showForecast]);

  const forecastStartDate = useMemo(() => {
    if (!showForecast) return null;
    for (const d of chartData) {
      if (d.actual != null && d.forecast != null) return d.date;
    }
    return null;
  }, [chartData, showForecast]);

  const { yDomain, yTicks, yWidth } = useMemo(() => {
    if (!chartData.length) return { yDomain: ['auto', 'auto'], yTicks: undefined, yWidth: 50 };
    let min = Infinity, max = -Infinity;
    for (const r of chartData) {
      if (r.actual != null) { min = Math.min(min, r.actual); max = Math.max(max, r.actual); }
      if (r.forecast != null) { min = Math.min(min, r.forecast); max = Math.max(max, r.forecast); }
    }
    if (!isFinite(min)) return { yDomain: ['auto', 'auto'], yTicks: undefined, yWidth: 50 };
    const span = max - min || 1;
    const rough = span / 5;
    const pow = Math.pow(10, Math.floor(Math.log10(rough)));
    const frac = rough / pow;
    const step = frac <= 1.5 ? pow : frac <= 3.5 ? 2 * pow : frac <= 7.5 ? 5 * pow : 10 * pow;
    const niceMin = Math.floor(min / step) * step;
    const niceMax = Math.ceil(max / step) * step;
    const ticks = [];
    for (let v = niceMin; v <= niceMax + step * 0.01; v += step) ticks.push(Math.round(v * 1e6) / 1e6);
    const digits = unitDigits(meta?.unit);
    const sample = formatAxisTick(Math.abs(niceMin) > Math.abs(niceMax) ? niceMin : niceMax, digits);
    const w = Math.max(40, Math.min(100, sample.length * 7.5 + 10));
    return { yDomain: [niceMin, niceMax], yTicks: ticks, yWidth: w };
  }, [chartData, meta?.unit]);

  const unit = meta?.unit || '%';
  const displayVal = isCpiIndex(code) && meta?.current_value != null
    ? +(meta.current_value - 100).toFixed(2) : meta?.current_value;
  const change = meta?.change;
  const chartH = height - (showTitle ? 50 : 0) - 28;

  return (
    <div style={{ background: colors.bg, height, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {showTitle && meta && (
        <div style={{ padding: '12px 16px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: colors.textSecondary, fontFamily: 'system-ui, sans-serif', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {meta.name}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexShrink: 0 }}>
            <span style={{ fontSize: 20, fontWeight: 700, fontFamily: 'ui-monospace, monospace', color: colors.text }}>
              {formatValueWithUnit(displayVal, unit)}
            </span>
            {change != null && (
              <span style={{
                fontSize: 12, fontWeight: 600, fontFamily: 'ui-monospace, monospace',
                color: change > 0 ? '#16a34a' : change < 0 ? '#dc2626' : colors.textTertiary,
                display: 'inline-flex', alignItems: 'center', gap: 2,
              }}>
                {change > 0 ? <TrendingUp size={12} /> : change < 0 ? <TrendingDown size={12} /> : null}
                {formatChange(change)}
              </span>
            )}
          </div>
        </div>
      )}

      <div style={{ flex: 1, minHeight: 0 }}>
        {isLoading ? (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ width: 24, height: 24, border: '2px solid', borderColor: `${colors.border} transparent`, borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
          </div>
        ) : chartData.length === 0 ? (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.textTertiary, fontSize: 13, fontFamily: 'system-ui' }}>
            Нет данных
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(120, chartH)}>
            <ComposedChart data={chartData} margin={{ top: 8, right: 8, bottom: 4, left: -4 }}>
              <defs>
                <linearGradient id="eg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#B8942F" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#B8942F" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} vertical={false} />
              <XAxis
                dataKey="date" tickFormatter={d => formatDate(d)}
                stroke={colors.grid} tick={{ fill: colors.tick, fontSize: 10, fontFamily: 'ui-monospace, monospace' }}
                tickLine={false} interval="preserveStartEnd" minTickGap={50}
              />
              <YAxis
                stroke={colors.grid} tick={{ fill: colors.tick, fontSize: 10, fontFamily: 'ui-monospace, monospace' }}
                tickLine={false} axisLine={false} domain={yDomain} ticks={yTicks}
                tickFormatter={v => formatAxisTick(v, unitDigits(unit))} width={yWidth}
              />
              <Tooltip content={<EmbedTooltip unit={unit} colors={colors} />} cursor={{ stroke: colors.tick, strokeWidth: 1, strokeOpacity: 0.3 }} />
              <ReferenceLine y={0} stroke={colors.grid} strokeDasharray="6 3" />
              {forecastStartDate && <ReferenceLine x={forecastStartDate} stroke="rgba(124,58,237,0.35)" strokeDasharray="4 4" />}
              <Area dataKey="actual" stroke="#B8942F" strokeWidth={2} fill="url(#eg)" dot={false}
                activeDot={{ r: 3, fill: '#B8942F', stroke: colors.bg, strokeWidth: 2 }} isAnimationActive={false} />
              {showForecast && (
                <Line dataKey="forecast" stroke="#7C3AED" strokeWidth={2} strokeDasharray="8 4"
                  dot={false} activeDot={{ r: 4, fill: '#7C3AED', stroke: colors.bg, strokeWidth: 2 }} isAnimationActive={false} />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 8px', flexShrink: 0 }}>
        {height > 280 && (
          <div style={{ display: 'flex', gap: 2 }}>
            {PERIODS.map(p => (
              <button key={p.key} onClick={() => setPeriod(p.key)}
                style={{
                  border: 'none', cursor: 'pointer', fontSize: 10, fontWeight: 500,
                  fontFamily: 'system-ui', padding: '3px 8px', borderRadius: 6, transition: 'all 0.15s',
                  background: period === p.key ? 'rgba(184,148,47,0.12)' : 'transparent',
                  color: period === p.key ? '#B8942F' : colors.textTertiary,
                }}>
                {p.label}
              </button>
            ))}
          </div>
        )}
        <Attribution code={code} dark={theme === 'dark'} />
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  );
}
