import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import {
  HOME_TODAY_CODES,
  HOME_TODAY_LABELS,
  HOME_TODAY_UNIT_SHORT,
  displayPulseValue,
  pickIndicatorsByCodes,
} from '../../lib/homeWorkbench';
import { formatChange, formatDate, formatValue, resolveDateFormat } from '../../lib/format';
import { SkeletonBox } from '../Skeleton';
import { track, events } from '../../lib/track';
import IndicatorSearch from '../IndicatorSearch';

function PulseCard({ indicator }) {
  const pulse = displayPulseValue(indicator);
  const label = HOME_TODAY_LABELS[indicator.code] || indicator.name;
  const unitShort = HOME_TODAY_UNIT_SHORT[indicator.code]
    || (pulse?.unit ? String(pulse.unit).replace(/\s+/g, '\u00A0') : '');
  const dateFmt = resolveDateFormat({ frequency: indicator.frequency });

  return (
    <Link
      to={`/indicator/${indicator.code}`}
      onClick={() => track(events.HOME_TODAY_CLICK, { indicator: indicator.code })}
      className="group flex min-h-[4.75rem] flex-col justify-between rounded-xl border border-border-subtle bg-surface px-3 py-2.5 transition-all hover:border-border-champagne hover:shadow-sm"
    >
      <div className="truncate text-[10px] font-medium uppercase tracking-wide text-text-tertiary">
        {label}
      </div>
      {pulse ? (
        <>
          <div className="mt-1.5 flex min-w-0 items-baseline gap-1">
            <span className="font-mono text-lg font-semibold tabular-nums leading-none text-text-primary">
              {formatValue(pulse.value)}
            </span>
            {unitShort ? (
              <span className="shrink-0 whitespace-nowrap text-[10px] font-medium leading-none text-text-tertiary">
                {unitShort}
              </span>
            ) : null}
          </div>
          <div className="mt-1.5 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-text-tertiary">
            {pulse.change != null && Math.abs(pulse.change) >= 1e-12 && (
              <span className={pulse.change > 0 ? 'text-positive' : 'text-negative'}>
                {formatChange(pulse.change)}
              </span>
            )}
            {indicator.current_date && (
              <span className="truncate">{formatDate(indicator.current_date, dateFmt)}</span>
            )}
          </div>
        </>
      ) : (
        <span className="mt-2 text-sm text-text-tertiary">Нет данных</span>
      )}
    </Link>
  );
}

function RussiaTodayPanel({ indicators, isLoading }) {
  const cards = pickIndicatorsByCodes(indicators, HOME_TODAY_CODES);

  return (
    <aside
      data-block="home-russia-today-panel"
      className="rounded-2xl border border-border-subtle bg-champagne/[0.06] p-4 md:p-5"
      aria-labelledby="home-russia-today-title"
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
            Оперативный срез
          </div>
          <h2 id="home-russia-today-title" className="mt-1 text-base font-semibold text-text-primary">
            Россия сегодня
          </h2>
        </div>
        <Link
          to="/today"
          className="mt-0.5 inline-flex shrink-0 items-center gap-1 text-[11px] text-champagne hover:underline"
        >
          Все на сегодня
          <ArrowRight size={12} />
        </Link>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {HOME_TODAY_CODES.map((code) => (
            <SkeletonBox key={code} className="h-[4.75rem] rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {cards.map((ind) => (
            <PulseCard key={ind.code} indicator={ind} />
          ))}
        </div>
      )}
    </aside>
  );
}

export default function HomeHero({ indicators, isLoading }) {
  return (
    <header data-block="home-hero" className="mb-10 md:mb-12">
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(18rem,0.85fr)] lg:gap-8">
        <div className="min-w-0">
          <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.28em] text-champagne">
            Бесплатная аналитическая платформа экономических данных
          </p>
          <h1 className="max-w-3xl text-2xl font-semibold leading-[1.2] tracking-tight text-text-primary md:text-3xl lg:text-[2rem]">
            Официальная статистика России и мира — в одной рабочей среде
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-text-secondary md:text-[15px]">
            Макроэкономика Российской Федерации, субъекты и зарубежные страны по данным
            национальных статистических ведомств и Евростата. Актуальные значения,
            сравнения и переход к полной карточке показателя.
          </p>
          <div className="mt-6">
            <IndicatorSearch
              variant="inline"
              inlinePlaceholder="Найти показатель — инфляция, ВВП, ставка, безработица…"
            />
          </div>
        </div>

        <RussiaTodayPanel indicators={indicators} isLoading={isLoading} />
      </div>
    </header>
  );
}
