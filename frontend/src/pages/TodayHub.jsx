import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useIndicator, useIndicatorData } from '../lib/hooks';
import { TODAY_CODES, TODAY_SPECS } from '../lib/todaySpecs';
import { formatValue, formatDate, formatChange } from '../lib/format';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import { todayTrail } from '../lib/breadcrumbs';
import {
  calendarPath,
  regionHubPath,
  todayPath,
} from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';

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
  const { data: rows, isLoading, isError } = useIndicatorData(seriesCode, { limit: 2 });
  const query = todayLabel(code, t);

  const last = rows?.data?.[rows.data.length - 1];
  const prev = rows?.data?.length > 1 ? rows.data[rows.data.length - 2] : null;
  const change = last && prev ? last.value - prev.value : null;

  return (
    <Link
      to={todayPath(code)}
      className="group bg-surface border border-border-subtle rounded-xl p-4 hover:border-border-champagne hover:shadow-sm transition-all flex flex-col gap-2"
    >
      <div className="text-[11px] text-text-tertiary uppercase tracking-wide font-mono">
        {t('today.cardToday', { query })}
      </div>
      {isLoading ? (
        <SkeletonBox className="h-8 w-32" />
      ) : isError || !last ? (
        <span className="text-sm text-text-tertiary">{t('common.noData')}</span>
      ) : (
        <>
          <div className="font-mono text-2xl font-bold text-text-primary leading-none">
            {formatValue(last.value)}
            <span className="ml-1.5 text-sm font-normal text-text-secondary">
              {indicator?.unit || ''}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-text-tertiary">
            {change != null && Math.abs(change) >= 1e-12 && (
              <span className={change > 0 ? 'text-positive' : 'text-negative'}>
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
      <span className="text-xs text-champagne group-hover:underline mt-auto inline-flex items-center gap-1">
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
    <div className="max-w-5xl mx-auto px-4 pt-24 pb-20">
      <Breadcrumbs items={todayTrail()} />

      <p className="text-champagne text-xs font-mono uppercase tracking-widest mb-2">
        {t('today.eyebrow', { date: today })}
      </p>
      <h1 className="font-display text-3xl sm:text-4xl font-bold text-text-primary mb-3">
        {t('today.h1')}
      </h1>
      <p className="text-text-secondary max-w-2xl mb-8">
        {t('today.intro')}
      </p>

      <section className="mb-10">
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
          <Link to="/" className="text-champagne hover:underline">{t('today.moreBody.home')}</Link>
          {t('today.moreBody.beforeRegions')}
          <Link to={regionHubPath()} className="text-champagne hover:underline">
            {t('today.moreBody.regions')}
          </Link>
          {t('today.moreBody.beforeCalendar')}
          <Link to={calendarPath()} className="text-champagne hover:underline">
            {t('today.moreBody.calendar')}
          </Link>
          {t('today.moreBody.after')}
        </p>
      </section>
    </div>
  );
}
