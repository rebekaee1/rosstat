import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useIndicator, useIndicatorData } from '../lib/hooks';
import { TODAY_CODES, TODAY_SPECS } from '../lib/todaySpecs';
import { formatValue, formatDate, formatChange } from '../lib/format';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import Button from '../components/Button';
import { todayTrail } from '../lib/breadcrumbs';
import {
  calendarPath,
  regionHubPath,
  todayPath,
} from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import '../styles/platform-pages.css';

function todayLabel(code, t) {
  const key = `today.spec.${code}`;
  const translated = t(key);
  if (translated && translated !== key) return translated;
  return TODAY_SPECS[code]?.query || code;
}

function formatTodayDate(d, locale) {
  try {
    return new Intl.DateTimeFormat(locale === 'en' ? 'en-GB' : 'ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    }).format(d);
  } catch {
    return d.toISOString().slice(0, 10);
  }
}

function TodayCard({ code }) {
  const t = useT();
  const { locale } = useLocale();
  const spec = TODAY_SPECS[code];
  const seriesCode = spec.series || code;
  const { data: indicator } = useIndicator(seriesCode);
  const {
    data: rows, isLoading, isError, refetch, isFetching,
  } = useIndicatorData(seriesCode, { limit: 2 });
  const query = todayLabel(code, t);

  const last = rows?.data?.[rows.data.length - 1];
  const prev = rows?.data?.length > 1 ? rows.data[rows.data.length - 2] : null;
  const change = last && prev ? last.value - prev.value : null;

  if (isError && !last) {
    return (
      <div className="flex flex-col gap-2 rounded-xl border border-border-subtle bg-surface p-4" role="alert">
        <div className="font-mono text-[11px] uppercase tracking-wide text-text-secondary">
          {t('today.cardToday', { query })}
        </div>
        <span className="text-sm text-text-secondary">{t('pgui.today.cardError')}</span>
        <Button variant="secondary" size="sm" className="mt-auto self-start" loading={isFetching} onClick={() => refetch()}>
          {t('common.retry')}
        </Button>
      </div>
    );
  }

  return (
    <Link
      to={todayPath(code)}
      className="fe-press group bg-surface border border-border-subtle rounded-xl p-4 hover:border-border-champagne hover:shadow-sm transition-all flex flex-col gap-2 min-h-[148px]"
    >
      <div className="text-[11px] text-text-secondary uppercase tracking-wide font-mono">
        {t('today.cardToday', { query })}
      </div>
      {isLoading ? (
        <>
          <SkeletonBox className="h-6 w-32" />
          <SkeletonBox className="h-4 w-24" />
        </>
      ) : !last ? (
        <span className="text-sm text-text-secondary">{t('common.noData')}</span>
      ) : (
        <>
          <div className="font-mono text-2xl font-bold text-text-primary leading-none">
            {formatValue(last.value)}
            <span className="ml-1.5 text-sm font-normal text-text-secondary">
              {indicator?.unit || ''}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-text-secondary">
            {change != null && Math.abs(change) >= 1e-12 && (
              <span className={change > 0 ? 'fe-ink-pos' : 'fe-ink-neg'}>
                {formatChange(change, indicator?.unit)}
              </span>
            )}
            <span>
              {formatDate(
                last.date,
                indicator?.frequency === 'daily' ? 'full' : 'monthly',
                locale,
              )}
            </span>
          </div>
        </>
      )}
      <span className="fe-tap-inline text-xs text-champagne-ink group-hover:underline mt-auto gap-1">
        {t('common.more')} <ArrowRight size={12} />
      </span>
    </Link>
  );
}

export default function TodayHub() {
  const t = useT();
  const { locale } = useLocale();
  const today = formatTodayDate(new Date(), locale);
  useDocumentMeta({
    title: t('today.metaTitle', { date: today }),
    description: t('today.metaDesc'),
    path: todayPath(),
  });

  return (
    <div className="fe-data-page max-w-5xl mx-auto px-4 pt-24 pb-20">
      <Breadcrumbs items={todayTrail()} />

      <p className="text-champagne-ink text-xs font-mono uppercase tracking-widest mb-2">
        {t('today.eyebrow', { date: today })}
      </p>
      <h1 className="font-display text-3xl sm:text-4xl font-bold text-text-primary mb-3">
        {t('today.h1')}
      </h1>
      <p className="text-text-secondary max-w-2xl mb-8">
        {t('today.intro')}
      </p>

      <section id="chart" className="mb-10 scroll-mt-28">
        <h2 className="font-display text-lg font-semibold text-text-primary mb-4">
          {t('today.sectionTitle')}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {TODAY_CODES.map((code) => (
            <TodayCard key={code} code={code} />
          ))}
        </div>
      </section>

      <section className="bg-surface border border-border-subtle rounded-xl p-5">
        <h2 className="font-display text-base font-semibold text-text-primary mb-2">
          {t('today.moreTitle')}
        </h2>
        <p className="text-sm text-text-secondary">
          {t('today.moreBody.beforeHome')}
          <Link to="/" className="text-champagne-ink hover:underline">{t('today.moreBody.home')}</Link>
          {t('today.moreBody.beforeRegions')}
          <Link to={regionHubPath()} className="text-champagne-ink hover:underline">
            {t('today.moreBody.regions')}
          </Link>
          {t('today.moreBody.beforeCalendar')}
          <Link to={calendarPath()} className="text-champagne-ink hover:underline">
            {t('today.moreBody.calendar')}
          </Link>
          {t('today.moreBody.after')}
        </p>
      </section>
    </div>
  );
}
