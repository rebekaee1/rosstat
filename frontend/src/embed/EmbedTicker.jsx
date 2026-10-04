import { useT } from '../i18n';
import { useMemo } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import { formatValueWithUnit, formatChange, isCpiIndex } from '../lib/format';
import { useEmbedParams, useEmbedImpression, embedChangeColor, THEME_COLORS } from './useEmbedParams';
import EmbedSpinner from './EmbedSpinner';

const SPEED_MAP = { slow: 40, normal: 25, fast: 14 };

function TickerItem({ ind, colors, theme }) {
  const displayVal = isCpiIndex(ind.code) && ind.current_value != null
    ? +(ind.current_value - 100).toFixed(2) : ind.current_value;
  const change = ind.change;
  const isUp = change > 0;
  const isDown = change < 0;

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0 20px', whiteSpace: 'nowrap' }}>
      <span style={{ fontSize: 12, fontWeight: 500, color: colors.textSecondary }}>
        {ind.name}
      </span>
      <span style={{ fontSize: 13, fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: colors.text }}>
        {formatValueWithUnit(displayVal, ind.unit)}
      </span>
      {change != null && (
        <span style={{
          fontSize: 12, fontWeight: 600, fontVariantNumeric: 'tabular-nums',
          display: 'inline-flex', alignItems: 'center', gap: 2,
          color: embedChangeColor(change, theme, colors, ind.name, ind.code),
        }}>
          {isUp ? <TrendingUp size={10} /> : isDown ? <TrendingDown size={10} /> : null}
          {formatChange(change)}
        </span>
      )}
      <span style={{ color: colors.border, padding: '0 4px' }}>│</span>
    </span>
  );
}

// В-33: без `codes` дефолт — curated-набор ключевых показателей, а не
// сортировка по raw value среди несопоставимых единиц (иначе «топ-8» —
// случайная смесь самых больших чисел: ВВП в млрд рядом с индексами).
// Только listed-коды: useIndicators() отдаёт каталог без derived-siblings.
const DEFAULT_CODES = [
  'key-rate', 'cpi', 'usd-rub', 'eur-rub',
  'brent', 'unemployment', 'imoex', 'gold-price',
];

export default function EmbedTicker() {
  const t = useT();
  const { theme, codes, speed } = useEmbedParams();
  const colors = THEME_COLORS[theme];
  const dur = SPEED_MAP[speed] || SPEED_MAP.normal;

  useEmbedImpression(codes.join(','), 'ticker');

  const { data: allIndicators, isLoading, isError } = useIndicators();

  const items = useMemo(() => {
    const wanted = codes.length ? codes : DEFAULT_CODES;
    if (!allIndicators?.length) return [];
    return wanted
      .map(c => allIndicators.find(i => i.code === c))
      .filter(i => i && i.current_value != null);
  }, [allIndicators, codes]);

  const statusStyle = { background: colors.bg, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.textTertiary, fontSize: 12, fontFamily: 'system-ui' };

  if (isLoading) return <div style={{ ...statusStyle, gap: 8 }} role="status"><EmbedSpinner colors={colors} size={14} />{t('embed.loading')}</div>;
  if (isError) return <div style={statusStyle}>{t('embed.tickerLoadError')}</div>;
  if (!items.length) return <div style={statusStyle}>{t('embed.noData')}</div>;

  return (
    <div style={{
      background: colors.bg, borderTop: `1px solid ${colors.border}`, borderBottom: `1px solid ${colors.border}`,
      height: 40, overflow: 'hidden', position: 'relative',
      fontFamily: 'Manrope, system-ui, sans-serif',
    }}>
      <div className="ticker-track" style={{ display: 'flex', alignItems: 'center', height: '100%', whiteSpace: 'nowrap' }}>
        {items.map(ind => <TickerItem key={ind.code} ind={ind} colors={colors} theme={theme} />)}
        {items.map(ind => <TickerItem key={`dup-${ind.code}`} ind={ind} colors={colors} theme={theme} />)}
        <a href="https://forecasteconomy.com" target="_blank" rel="noopener"
          style={{ fontSize: 12, color: colors.textTertiary, padding: '0 16px', textDecoration: 'none' }}>
          forecasteconomy.com
        </a>
      </div>

      <style>{`
        @keyframes ticker-scroll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
        .ticker-track{animation:ticker-scroll ${dur}s linear infinite}
        .ticker-track:hover{animation-play-state:paused}
        @media(prefers-reduced-motion:reduce){.ticker-track{animation:none;overflow-x:auto}}
      `}</style>
    </div>
  );
}
