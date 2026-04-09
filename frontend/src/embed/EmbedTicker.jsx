import { useMemo } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import { formatValueWithUnit, formatChange, isCpiIndex } from '../lib/format';
import { useEmbedParams, useEmbedImpression, THEME_COLORS } from './useEmbedParams';

const SPEED_MAP = { slow: 40, normal: 25, fast: 14 };

function TickerItem({ ind, colors }) {
  const displayVal = isCpiIndex(ind.code) && ind.current_value != null
    ? +(ind.current_value - 100).toFixed(2) : ind.current_value;
  const change = ind.change;
  const isUp = change > 0;
  const isDown = change < 0;

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0 20px', whiteSpace: 'nowrap' }}>
      <span style={{ fontSize: 11, fontWeight: 500, color: colors.textSecondary }}>
        {ind.name}
      </span>
      <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'ui-monospace, monospace', color: colors.text }}>
        {formatValueWithUnit(displayVal, ind.unit)}
      </span>
      {change != null && (
        <span style={{
          fontSize: 10, fontWeight: 600, fontFamily: 'ui-monospace, monospace',
          display: 'inline-flex', alignItems: 'center', gap: 2,
          color: isUp ? '#16a34a' : isDown ? '#dc2626' : colors.textTertiary,
        }}>
          {isUp ? <TrendingUp size={10} /> : isDown ? <TrendingDown size={10} /> : null}
          {formatChange(change)}
        </span>
      )}
      <span style={{ color: colors.border, padding: '0 4px' }}>│</span>
    </span>
  );
}

export default function EmbedTicker() {
  const { theme, codes, speed } = useEmbedParams();
  const colors = THEME_COLORS[theme];
  const dur = SPEED_MAP[speed] || SPEED_MAP.normal;

  useEmbedImpression(codes.join(','), 'ticker');

  const { data: allIndicators } = useIndicators();

  const items = useMemo(() => {
    if (!allIndicators?.length) return [];
    if (codes.length) {
      return codes.map(c => allIndicators.find(i => i.code === c)).filter(Boolean);
    }
    return allIndicators
      .filter(i => i.current_value != null)
      .sort((a, b) => (b.current_value || 0) - (a.current_value || 0))
      .slice(0, 8);
  }, [allIndicators, codes]);

  if (!items.length) {
    return (
      <div style={{ background: colors.bg, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.textTertiary, fontSize: 12, fontFamily: 'system-ui' }}>
        Загрузка…
      </div>
    );
  }

  return (
    <div style={{
      background: colors.bg, borderTop: `1px solid ${colors.border}`, borderBottom: `1px solid ${colors.border}`,
      height: 40, overflow: 'hidden', position: 'relative',
      fontFamily: 'system-ui, -apple-system, sans-serif',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', height: '100%', animation: `ticker-scroll ${dur}s linear infinite`, whiteSpace: 'nowrap' }}>
        {items.map(ind => <TickerItem key={ind.code} ind={ind} colors={colors} />)}
        {items.map(ind => <TickerItem key={`dup-${ind.code}`} ind={ind} colors={colors} />)}
        <a href="https://forecasteconomy.com" target="_blank" rel="noopener"
          style={{ fontSize: 9, color: colors.textTertiary, padding: '0 16px', textDecoration: 'none' }}>
          forecasteconomy.com
        </a>
      </div>

      <style>{`
        @keyframes ticker-scroll {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
      `}</style>
    </div>
  );
}
