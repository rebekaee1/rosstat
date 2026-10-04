import { TrendingUp, TrendingDown } from 'lucide-react';
import { formatValue, formatChange, unitSuffix, unitDigits, cn } from '../lib/format';
import { useT } from '../i18n';
import '../styles/ui-detail-nav-calendar.css';

/**
 * Карточка одного телеметрического значения на странице индикатора.
 *
 * Используется в IndicatorDetail для четырёх блоков:
 *   текущее значение, предыдущее, абсолютный максимум, среднее.
 *
 * Если задан `change` — показывает дельту с иконкой, цветом, единицей измерения.
 * Если задан `pctChange` — показывает процентное изменение вместо абсолютного.
 *
 * Число всегда сразу точное; рамка мягко появляется средствами CSS (`.fe-reveal`, задержка ≤ 200 мс,
 * начальное состояние задаёт CSS). При `prefers-reduced-motion` анимации нет.
 */
export default function TelemetryCard({
  label, value, unit, change, pctChange, meta, delay = 0,
  deltaSuffix,
  valueDigits,
}) {
  const t = useT();
  const resolvedDelta = deltaSuffix ?? t('indicator.telemetry.delta.prevMonth');
  const digits = valueDigits ?? unitDigits(unit);
  const changeNum = change != null ? Number(change) : null;
  const isUp = changeNum != null && changeNum > 0;
  const isDown = changeNum != null && changeNum < 0;

  return (
    <div
      style={{ '--i': Math.min(delay, 5), '--fe-delay': 'calc(var(--i) * 40ms)', '--fe-duration': '0.4s', '--fe-rise': '12px' }}
      className="fe-reveal fe-reveal--free fe-panel fe-stat-cell group relative p-3 sm:p-6 rounded-2xl sm:rounded-[2rem] bg-surface border border-border-subtle hover:border-champagne/30 transition-colors duration-500 overflow-hidden lift-hover">
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-champagne/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700" />

      <p className="text-[11px] uppercase tracking-wider sm:tracking-widest text-text-tertiary font-medium mb-2 sm:mb-4 line-clamp-2 leading-tight">
        {label}
      </p>

      <div className="flex items-baseline gap-1 sm:gap-2 mb-1 sm:mb-2 flex-wrap">
        <span className={cn(
          'font-sans font-semibold tabular-nums tracking-tight text-text-primary break-words',
          String(formatValue(value, digits)).length > 12
            ? 'text-lg sm:text-xl md:text-2xl'
            : 'text-xl sm:text-2xl md:text-3xl'
        )}>
          {formatValue(value, digits)}
        </span>
        <span className="min-w-0 text-xs font-medium leading-snug text-text-tertiary break-words line-clamp-1 sm:shrink-0 sm:line-clamp-2">
          {unitSuffix(unit)}
        </span>
      </div>

      <div className="flex flex-col gap-1 sm:gap-1.5 mt-2 sm:mt-4 pt-2 sm:pt-4 border-t border-border-subtle/50">
        {changeNum != null && (
          <div className={cn(
            'flex items-center gap-1 sm:gap-1.5 text-xs font-mono font-medium flex-wrap',
            isUp ? 'fe-delta--up' : '',
            isDown ? 'fe-delta--down' : '',
            !isUp && !isDown ? 'text-text-tertiary' : ''
          )}>
            {isUp && <TrendingUp className="w-3.5 h-3.5 shrink-0" />}
            {isDown && <TrendingDown className="w-3.5 h-3.5 shrink-0" />}
            <span>{pctChange != null ? `${formatChange(pctChange)}%` : `Δ ${formatChange(changeNum)}`}</span>
            <span className="text-text-tertiary text-[11px] uppercase tracking-wide sm:tracking-wider ml-0.5 sm:ml-1">
              {resolvedDelta}
            </span>
          </div>
        )}
        {meta && (
          <div className="text-[11px] font-mono uppercase tracking-wide sm:tracking-widest text-text-tertiary leading-snug">
            {meta}
          </div>
        )}
      </div>
    </div>
  );
}
