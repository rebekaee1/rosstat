import { useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { useIndicator, useIndicatorData } from '../lib/hooks';
import { formatValueWithUnit, formatChange, formatDate, isCpiIndex } from '../lib/format';
import { useEmbedParams, useEmbedImpression, useEmbedAutoHeight, THEME_COLORS } from './useEmbedParams';
import Attribution from './Attribution';

function MiniSparkline({ data, width = 140, height = 36, color = '#B8942F' }) {
  const points = useMemo(() => {
    if (!data?.length || data.length < 2) return '';
    const vals = data.map(d => d.value);
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const span = hi - lo || 1;
    return vals.map((v, i) => {
      const x = (width * i) / (vals.length - 1);
      const y = height - 2 - ((v - lo) / span) * (height - 4);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  }, [data, width, height]);

  if (!points) return null;

  const lastParts = points.split(' ').pop().split(',');

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      <defs>
        <linearGradient id="mcg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.15} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <polygon points={`0,${height} ${points} ${width},${height}`} fill="url(#mcg)" />
      <polyline points={points} fill="none" stroke={color}
        strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lastParts[0]} cy={lastParts[1]} r="2.5" fill={color} />
    </svg>
  );
}

export default function EmbedCard() {
  const { code } = useParams();
  const { theme } = useEmbedParams();
  const colors = THEME_COLORS[theme];

  useEmbedImpression(code, 'card');
  useEmbedAutoHeight();

  const { data: meta } = useIndicator(code);
  const { data: dataResp } = useIndicatorData(code);

  const recentPoints = useMemo(() => {
    const pts = dataResp?.data || [];
    return pts.slice(-60);
  }, [dataResp]);

  if (!meta) {
    return (
      <div style={{ background: colors.bg, borderRadius: 16, border: `1px solid ${colors.border}`, height: 160, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ width: 20, height: 20, border: '2px solid', borderColor: `${colors.border} transparent`, borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      </div>
    );
  }

  const unit = meta.unit || '%';
  const displayVal = isCpiIndex(code) && meta.current_value != null
    ? +(meta.current_value - 100).toFixed(2) : meta.current_value;
  const change = meta.change;
  const isUp = change != null && change > 0;
  const isDown = change != null && change < 0;

  return (
    <div style={{
      background: colors.bg, borderRadius: 16, border: `1px solid ${colors.border}`,
      padding: 16, display: 'flex', flexDirection: 'column', gap: 8,
      fontFamily: 'system-ui, -apple-system, sans-serif', overflow: 'hidden',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div style={{ fontSize: 11, fontWeight: 500, color: colors.textSecondary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '65%' }}>
          {meta.name}
        </div>
        {change != null && (
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 3,
            fontSize: 11, fontWeight: 600, fontFamily: 'ui-monospace, monospace',
            padding: '2px 8px', borderRadius: 6,
            background: isUp ? 'rgba(22,163,74,0.1)' : isDown ? 'rgba(220,38,38,0.1)' : colors.surface,
            color: isUp ? '#16a34a' : isDown ? '#dc2626' : colors.textTertiary,
          }}>
            {isUp ? <TrendingUp size={11} /> : isDown ? <TrendingDown size={11} /> : null}
            {formatChange(change)}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontSize: 28, fontWeight: 700, color: colors.text, fontFamily: 'ui-monospace, monospace', letterSpacing: '-0.02em' }}>
          {formatValueWithUnit(displayVal, unit)}
        </span>
      </div>

      <div style={{ flex: 1, marginTop: 2, marginBottom: 2 }}>
        <MiniSparkline data={recentPoints} width={280} height={40} />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: `1px solid ${colors.border}`, paddingTop: 6, marginTop: 2 }}>
        {meta.current_date && (
          <span style={{ fontSize: 10, color: colors.textTertiary, fontFamily: 'ui-monospace, monospace' }}>
            {formatDate(meta.current_date, 'full')}
          </span>
        )}
        <Attribution code={code} dark={theme === 'dark'} />
      </div>
    </div>
  );
}
