import { Link } from 'react-router-dom';
import { russiaIndicatorYearPath } from '../lib/sitePaths';
import { useT } from '../i18n';

/** Data-backed year pages remain visible after React replaces the SSR body. */
export default function IndicatorYearLinks({ code, years }) {
  const t = useT();
  if (!years?.length) return null;

  return (
    <section data-block="indicator-years" className="mt-10">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-text-secondary">
        {t('indicator.byYear')}
      </h2>
      <div className="flex flex-wrap gap-2">
        {years.map((year) => (
          <Link
            key={year}
            to={russiaIndicatorYearPath(code, year)}
            className="rounded-full border border-border-subtle px-3 py-1 text-xs text-text-secondary hover:border-border-champagne hover:text-champagne"
          >
            {year}
          </Link>
        ))}
      </div>
    </section>
  );
}
