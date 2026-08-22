import { Link } from 'react-router-dom';
import {
  ArrowRight, BarChart3, CalendarRange, Database, Globe2, MapPinned,
} from 'lucide-react';
import { useCoverage } from '../../lib/hooks';
import { formatValue } from '../../lib/format';
import { comparePath } from '../../lib/sitePaths';
import { SkeletonBox } from '../Skeleton';
import { track, events } from '../../lib/track';
import { useT } from '../../i18n';

function Stat({ icon: Icon, value, label }) {
  return (
    <div className="min-w-0 rounded-xl border border-border-subtle bg-surface px-3.5 py-3">
      <Icon size={14} className="mb-2 text-champagne" />
      <div className="font-mono text-base font-semibold tabular-nums text-text-primary">
        {value}
      </div>
      <div className="mt-0.5 text-[10px] leading-tight text-text-tertiary">{label}</div>
    </div>
  );
}

/**
 * Сколько данных на платформе плюс вход в сравнение показателей.
 * Числа приходят с сервера — на витрине их руками не задаём.
 */
export default function HomeCoverage() {
  const t = useT();
  const { data, isLoading } = useCoverage();
  const period = data?.year_from && data?.year_to
    ? `${data.year_from}\u2013${data.year_to}`
    : '\u2014';

  return (
    <section
      data-block="home-coverage"
      className="mb-10 rounded-2xl border border-border-subtle bg-champagne/[0.05] p-4 md:mb-12 md:p-5"
      aria-labelledby="home-coverage-title"
    >
      <div className="grid items-center gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:gap-6">
        <div className="min-w-0">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
            {t('home.coverage.eyebrow')}
          </div>
          <h2 id="home-coverage-title" className="mt-1 text-base font-semibold text-text-primary sm:text-lg">
            {t('home.coverage.title')}
          </h2>
          {isLoading ? (
            <div className="mt-3 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
              {[0, 1, 2, 3].map((i) => <SkeletonBox key={i} className="h-[5.25rem] rounded-xl" />)}
            </div>
          ) : (
            <div className="mt-3 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
              <Stat
                icon={Globe2}
                value={formatValue(data?.countries ?? 0, 0)}
                label={t('home.coverage.countries')}
              />
              <Stat
                icon={Database}
                value={formatValue(data?.series ?? 0, 0)}
                label={t('home.coverage.series')}
              />
              <Stat
                icon={MapPinned}
                value={formatValue(data?.regions ?? 0, 0)}
                label={t('home.coverage.regions')}
              />
              <Stat icon={CalendarRange} value={period} label={t('home.coverage.period')} />
            </div>
          )}
        </div>

        <Link
          to={comparePath()}
          onClick={() => track(events.HOME_COUNTRIES_CTA, { target: 'compare' })}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-champagne px-4 py-3 text-sm font-semibold text-white shadow-sm transition-opacity hover:opacity-90"
        >
          <BarChart3 size={15} />
          {t('nav.compare')}
          <ArrowRight size={15} />
        </Link>
      </div>
    </section>
  );
}
