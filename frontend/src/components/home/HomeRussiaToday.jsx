import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import {
  HOME_TODAY_CODES,
  HOME_TODAY_LABELS,
  displayPulseValue,
  pickIndicatorsByCodes,
} from '../../lib/homeWorkbench';
import { formatChange, formatDate, formatValue, resolveDateFormat } from '../../lib/format';
import { SkeletonBox } from '../Skeleton';
import { track, events } from '../../lib/track';

function PulseCard({ indicator }) {
  const pulse = displayPulseValue(indicator);
  const label = HOME_TODAY_LABELS[indicator.code] || indicator.name;
  const dateFmt = resolveDateFormat({ frequency: indicator.frequency });

  return (
    <Link
      to={`/indicator/${indicator.code}`}
      onClick={() => track(events.HOME_TODAY_CLICK, { indicator: indicator.code })}
      className="group flex min-h-[5.5rem] flex-col justify-between rounded-xl border border-border-subtle bg-surface px-3.5 py-3 transition-all hover:border-border-champagne hover:shadow-sm"
    >
      <div className="text-[11px] font-medium uppercase tracking-wide text-text-tertiary">
        {label}
      </div>
      {pulse ? (
        <>
          <div className="mt-1.5 font-mono text-xl font-semibold tabular-nums leading-none text-text-primary">
            {formatValue(pulse.value)}
            {pulse.unit ? (
              <span className="ml-1 text-xs font-normal text-text-secondary">{pulse.unit}</span>
            ) : null}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-text-tertiary">
            {pulse.change != null && Math.abs(pulse.change) >= 1e-12 && (
              <span className={pulse.change > 0 ? 'text-positive' : 'text-negative'}>
                {formatChange(pulse.change)}
              </span>
            )}
            {indicator.current_date && (
              <span>{formatDate(indicator.current_date, dateFmt)}</span>
            )}
          </div>
        </>
      ) : (
        <span className="mt-2 text-sm text-text-tertiary">Нет данных</span>
      )}
    </Link>
  );
}

export default function HomeRussiaToday({ indicators, isLoading }) {
  const cards = pickIndicatorsByCodes(indicators, HOME_TODAY_CODES);

  return (
    <section data-block="home-russia-today" className="mb-8 md:mb-10" aria-labelledby="home-russia-today-title">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
            Оперативный срез
          </div>
          <h2 id="home-russia-today-title" className="mt-1 text-lg font-semibold text-text-primary">
            Россия сегодня
          </h2>
        </div>
        <Link
          to="/today"
          className="inline-flex items-center gap-1 text-xs text-champagne hover:underline"
        >
          Все показатели на сегодня
          <ArrowRight size={12} />
        </Link>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
          {HOME_TODAY_CODES.map((code) => (
            <SkeletonBox key={code} className="h-[5.5rem] rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
          {cards.map((ind) => (
            <PulseCard key={ind.code} indicator={ind} />
          ))}
        </div>
      )}
    </section>
  );
}
