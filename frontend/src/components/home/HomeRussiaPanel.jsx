import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import {
  HOME_RUSSIA_FLAGSHIP_CODES,
  HOME_SPARKLINE_BY_CODE,
  displayPulseValue,
  pickIndicatorsByCodes,
} from '../../lib/homeWorkbench';
import { formatChange, formatDate, formatValue, resolveDateFormat } from '../../lib/format';
import { useDashboardSparklines } from '../../lib/hooks';
import Sparkline, { SparklineSkeleton } from '../Sparkline';
import { SkeletonBox } from '../Skeleton';
import { track, events } from '../../lib/track';
import {
  russiaIndicatorPath,
} from '../../lib/sitePaths';

function FlagshipRow({ indicator, spark }) {
  const pulse = displayPulseValue(indicator);
  const dateFmt = resolveDateFormat({ frequency: indicator.frequency });

  return (
    <Link
      to={russiaIndicatorPath(indicator.code)}
      onClick={() => track(events.HOME_INDICATOR_CLICK, {
        indicator: indicator.code,
        indicatorCategory: indicator.category,
        surface: 'home-russia',
      })}
      className="group grid grid-cols-[1fr_auto] items-center gap-3 rounded-xl border border-border-subtle bg-surface px-3.5 py-3 transition-colors hover:border-border-champagne sm:grid-cols-[1.4fr_minmax(96px,0.7fr)_auto] sm:gap-4"
    >
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-text-primary group-hover:text-champagne">
          {indicator.name}
        </div>
        <div className="mt-0.5 text-[11px] text-text-tertiary">
          {indicator.current_date
            ? formatDate(indicator.current_date, dateFmt)
            : (spark?.last_date ? formatDate(spark.last_date, dateFmt) : '—')}
        </div>
      </div>
      <div className="hidden sm:block">
        {spark?.points?.length >= 2 ? (
          <Sparkline
            points={spark.points}
            height={36}
            trend={spark.trend}
            sentiment={spark.sentiment}
          />
        ) : spark ? (
          <SparklineSkeleton height={36} />
        ) : (
          <div className="h-9" />
        )}
      </div>
      <div className="text-right">
        {pulse ? (
          <>
            <div className="font-mono text-base font-semibold tabular-nums text-text-primary">
              {formatValue(pulse.value)}
              {pulse.unit ? (
                <span className="ml-1 text-[11px] font-normal text-text-secondary">{pulse.unit}</span>
              ) : null}
            </div>
            {pulse.change != null && Math.abs(pulse.change) >= 1e-12 && (
              <div className={`text-[11px] font-mono ${pulse.change > 0 ? 'text-positive' : 'text-negative'}`}>
                {formatChange(pulse.change)}
              </div>
            )}
          </>
        ) : (
          <span className="text-sm text-text-tertiary">—</span>
        )}
      </div>
    </Link>
  );
}

export default function HomeRussiaPanel({ indicators, isLoading }) {
  const sparklines = useDashboardSparklines();
  const rows = pickIndicatorsByCodes(indicators, HOME_RUSSIA_FLAGSHIP_CODES);

  return (
    <div data-block="home-workbench-russia">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-text-primary">Флагманские показатели</h3>
          <p className="mt-1 max-w-xl text-xs leading-5 text-text-secondary">
            Национальный срез без карты: уровень и короткая динамика. Полная история — в карточке.
          </p>
        </div>
        <Link to="/compare" className="inline-flex items-center gap-1 text-xs text-champagne hover:underline">
          Сравнить показатели
          <ArrowRight size={12} />
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonBox key={i} className="h-16 rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {rows.map((ind) => {
            const sparkKey = HOME_SPARKLINE_BY_CODE[ind.code];
            const spark = sparkKey ? sparklines.data?.[sparkKey] : null;
            return <FlagshipRow key={ind.code} indicator={ind} spark={spark} />;
          })}
        </div>
      )}
    </div>
  );
}
