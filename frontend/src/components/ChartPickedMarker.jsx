import { CHART_THEME } from '../lib/chartTheme';
import { pointLabelWidth } from '../lib/chartPointLabel';

/**
 * Точка, выбранная нажатием (18.11.2026; общий для графиков с 19.11.2026): тонкая вертикаль, точка на линии
 * и плашка «дата значение». Остаётся, когда указатель ушёл с графика или палец отпущен; повторное нажатие
 * на ту же точку снимает выбор (см. `useChartPick`). Плашка — стекло без обводки (класс k4-lastpoint__tag).
 */
export default function ChartPickedMarker({
  cx, cy, top, bottom, date, value, color, anchorEnd, below: belowWanted, showTag = true,
}) {
  if (!Number.isFinite(cx) || !Number.isFinite(cy)) return null;
  const text = `${date}  ${value}`;
  const width = pointLabelWidth(text) + 4;
  const height = 24;
  const below = belowWanted ? cy + 14 + height + 4 <= bottom : cy - 14 - height < top;
  const x = anchorEnd ? cx - width + 12 : cx - 12;
  const y = below ? cy + 14 : cy - 14 - height;
  return (
    <g pointerEvents="none" className="k4-picked">
      {Number.isFinite(top) && Number.isFinite(bottom) && (
        <line x1={cx} x2={cx} y1={top} y2={bottom} stroke={CHART_THEME.cursor} strokeWidth={1} />
      )}
      <circle cx={cx} cy={cy} r={5.5} fill={color} stroke="#FFFFFF" strokeWidth={2} />
      {showTag && (
        <>
          <rect className="k4-lastpoint__tag" x={x} y={y} width={width} height={height} rx={12} fill="#FFFFFF" fillOpacity={0.94} />
          <rect x={x + 6} y={y + 1} width={Math.max(0, width - 12)} height={1.2} rx={0.6} fill="#FFFFFF" />
          <text x={x + width / 2} y={y + height / 2 + 4.2} textAnchor="middle" fontFamily={CHART_THEME.font} fontSize={12}>
            <tspan fill={CHART_THEME.axis}>{date}</tspan>
            <tspan dx={6} fill={CHART_THEME.ink} fontWeight={700}>{value}</tspan>
          </text>
        </>
      )}
    </g>
  );
}
