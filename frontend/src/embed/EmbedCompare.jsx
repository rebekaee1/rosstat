import { useMemo, useState } from 'react';
import {
  ResponsiveContainer, ComposedChart, Line, XAxis, YAxis,
  Tooltip, CartesianGrid,
} from 'recharts';
import { useIndicator, useIndicatorData } from '../lib/hooks';
import { formatDate, formatAxisTick, formatValueWithUnit, unitDigits } from '../lib/format';
import { useEmbedParams, useEmbedImpression, useEmbedAutoHeight, PERIODS, THEME_COLORS } from './useEmbedParams';
import Attribution from './Attribution';

const COLOR_A = '#B8942F';
const COLOR_B = '#7C3AED';

function CompareTooltip({ active, payload, label, unitA, unitB, nameA, nameB, colors }) {
  if (!active || !payload?.length) return null;
  const a = payload.find(p => p.dataKey === 'a');
  const b = payload.find(p => p.dataKey === 'b');
  return (
    <div style={{ background: colors.bg, border: `1px solid ${colors.border}`, borderRadius: 8, padding: '8px 12px', fontSize: 11, fontFamily: 'system-ui', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}>
      <div style={{ fontSize: 10, color: colors.textTertiary, marginBottom: 4, fontFamily: 'ui-monospace, monospace' }}>{formatDate(label)}</div>
      {a?.value != null && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
          <span style={{ width: 8, height: 2, background: COLOR_A, borderRadius: 1 }} />
          <span style={{ color: colors.textSecondary, fontSize: 10 }}>{nameA}</span>
          <span style={{ fontWeight: 600, color: COLOR_A, fontFamily: 'ui-monospace, monospace', marginLeft: 'auto' }}>{formatValueWithUnit(a.value, unitA)}</span>
        </div>
      )}
      {b?.value != null && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 8, height: 2, background: COLOR_B, borderRadius: 1 }} />
          <span style={{ color: colors.textSecondary, fontSize: 10 }}>{nameB}</span>
          <span style={{ fontWeight: 600, color: COLOR_B, fontFamily: 'ui-monospace, monospace', marginLeft: 'auto' }}>{formatValueWithUnit(b.value, unitB)}</span>
        </div>
      )}
    </div>
  );
}

export default function EmbedCompare() {
  const { theme, height, period: initPeriod, codeA, codeB, showTitle } = useEmbedParams();
  const [period, setPeriod] = useState(initPeriod);
  const colors = THEME_COLORS[theme];

  useEmbedImpression(`${codeA}+${codeB}`, 'compare');
  useEmbedAutoHeight();

  const { data: metaA } = useIndicator(codeA);
  const { data: metaB } = useIndicator(codeB);
  const { data: dataA } = useIndicatorData(codeA);
  const { data: dataB } = useIndicatorData(codeB);

  const chartData = useMemo(() => {
    const ptsA = dataA?.data || [];
    const ptsB = dataB?.data || [];
    if (!ptsA.length && !ptsB.length) return [];

    const periodObj = PERIODS.find(p => p.key === period);
    let cutStr = null;
    if (periodObj?.months) {
      const cutoff = new Date();
      cutoff.setMonth(cutoff.getMonth() - periodObj.months);
      cutStr = cutoff.toISOString().slice(0, 10);
    }

    const mapA = new Map(ptsA.map(p => [p.date, p.value]));
    const mapB = new Map(ptsB.map(p => [p.date, p.value]));
    const allDates = [...new Set([...mapA.keys(), ...mapB.keys()])].sort();

    return allDates
      .filter(d => !cutStr || d >= cutStr)
      .map(d => ({ date: d, a: mapA.get(d) ?? null, b: mapB.get(d) ?? null }));
  }, [dataA, dataB, period]);

  const unitA = metaA?.unit || '%';
  const unitB = metaB?.unit || '%';
  const nameA = metaA?.name || codeA;
  const nameB = metaB?.name || codeB;
  const chartH = height - (showTitle ? 40 : 0) - 32;

  return (
    <div style={{ background: colors.bg, height, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {showTitle && (
        <div style={{ padding: '10px 16px 4px', display: 'flex', alignItems: 'center', gap: 12, fontSize: 12, fontWeight: 600, fontFamily: 'system-ui' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 10, height: 3, background: COLOR_A, borderRadius: 2 }} />
            <span style={{ color: colors.textSecondary }}>{nameA}</span>
          </span>
          <span style={{ color: colors.textTertiary }}>vs</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 10, height: 3, background: COLOR_B, borderRadius: 2 }} />
            <span style={{ color: colors.textSecondary }}>{nameB}</span>
          </span>
        </div>
      )}

      <div style={{ flex: 1, minHeight: 0 }}>
        {chartData.length === 0 ? (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.textTertiary, fontSize: 13 }}>
            Нет данных
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(120, chartH)}>
            <ComposedChart data={chartData} margin={{ top: 8, right: 8, bottom: 4, left: -4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} vertical={false} />
              <XAxis dataKey="date" tickFormatter={d => formatDate(d)} stroke={colors.grid}
                tick={{ fill: colors.tick, fontSize: 10, fontFamily: 'ui-monospace, monospace' }}
                tickLine={false} interval="preserveStartEnd" minTickGap={50} />
              <YAxis yAxisId="left" stroke={colors.grid}
                tick={{ fill: COLOR_A, fontSize: 10, fontFamily: 'ui-monospace, monospace' }}
                tickLine={false} axisLine={false}
                tickFormatter={v => formatAxisTick(v, unitDigits(unitA))} width={55} />
              <YAxis yAxisId="right" orientation="right" stroke={colors.grid}
                tick={{ fill: COLOR_B, fontSize: 10, fontFamily: 'ui-monospace, monospace' }}
                tickLine={false} axisLine={false}
                tickFormatter={v => formatAxisTick(v, unitDigits(unitB))} width={55} />
              <Tooltip content={<CompareTooltip unitA={unitA} unitB={unitB} nameA={nameA} nameB={nameB} colors={colors} />} />
              <Line yAxisId="left" dataKey="a" stroke={COLOR_A} strokeWidth={2} dot={false}
                connectNulls={false} isAnimationActive={false} />
              <Line yAxisId="right" dataKey="b" stroke={COLOR_B} strokeWidth={2} dot={false}
                connectNulls={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 8px', flexShrink: 0 }}>
        {height > 280 && (
          <div style={{ display: 'flex', gap: 2 }}>
            {PERIODS.map(p => (
              <button key={p.key} onClick={() => setPeriod(p.key)}
                style={{ border: 'none', cursor: 'pointer', fontSize: 10, fontWeight: 500, fontFamily: 'system-ui', padding: '3px 8px', borderRadius: 6, background: period === p.key ? 'rgba(184,148,47,0.12)' : 'transparent', color: period === p.key ? '#B8942F' : colors.textTertiary }}>
                {p.label}
              </button>
            ))}
          </div>
        )}
        <Attribution code={codeA} dark={theme === 'dark'} />
      </div>
    </div>
  );
}
