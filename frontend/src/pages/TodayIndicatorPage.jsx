import { useMemo } from 'react';
import { Link, useParams, Navigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useIndicator, useIndicatorData } from '../lib/hooks';
import { getTodaySpec, todaySeriesCode } from '../lib/todaySpecs';
import {
  buildTodayIndicatorMeta,
  formatTodayNumber,
  formatTodayRuDate,
} from '../lib/todayFormat';
import { unitSuffix } from '../lib/format';
import { indicatorPolarity } from '../lib/deltaTone';
import { formatDeltaWithUnit } from '../lib/deltaText';
import DeltaBadge from '../components/DeltaBadge';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Breadcrumbs from '../components/Breadcrumbs';
import IndicatorChart from '../components/IndicatorChart';
import { SkeletonBox } from '../components/Skeleton';
import { todayIndicatorTrail } from '../lib/breadcrumbs';
import {
  russiaIndicatorPath,
  todayPath,
} from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import SourceLink from '../components/SourceLink';
import Button from '../components/Button';
import '../styles/platform-pages.css';
import '../styles/indicator-russia.css';

function ruDateShort(iso) {
  if (!iso) return '';
  const [y, m, day] = iso.split('-');
  return `${day}.${m}.${y}`;
}

function rangePreset(frequency) {
  if (frequency === 'daily') return 'daily';
  if (frequency === 'weekly') return 'weekly';
  if (frequency === 'quarterly') return 'quarterly';
  if (frequency === 'annual') return 'annual';
  return 'default';
}

export default function TodayIndicatorPage() {
  const t = useT();
  const { locale } = useLocale();
  const { code } = useParams();
  const spec = getTodaySpec(code);
  const seriesCode = todaySeriesCode(code);

  const { data: indicator, isLoading: loadingMeta, isError: metaError, refetch: refetchMeta, isFetching: fetchingMeta } = useIndicator(seriesCode);
  const { data: rowsResp, isLoading: loadingData, isError: dataError, refetch: refetchData, isFetching: fetchingData } = useIndicatorData(seriesCode, { limit: 60 });

  const points = useMemo(() => rowsResp?.data || [], [rowsResp]);
  const last = points[points.length - 1];
  const prev = points.length > 1 ? points[points.length - 2] : null;

  const chartPoints = useMemo(
    () => points.map((p) => ({ date: p.date, value: p.value })),
    [points],
  );

  const stats = useMemo(() => {
    if (!points.length) return null;
    const values = points.map((p) => p.value);
    return {
      min: Math.min(...values),
      max: Math.max(...values),
      change: prev ? last.value - prev.value : null,
    };
  }, [points, last, prev]);

  const freq = indicator?.frequency || 'monthly';
  const isCbrRate = ['usd-rub', 'eur-rub', 'cny-rub'].includes(code);
  const polarity = indicatorPolarity(spec?.query, indicator?.name, indicator?.code);
  const deltaInfo = stats?.change != null ? formatDeltaWithUnit(stats.change, indicator?.unit, { locale, plain: true }) : null;

  // Мета только после полного набора данных — иначе «Источник — undefined»
  // и мигание title (ADR-0003: CSR не должен перетирать SSR промежуточным).
  const todayMeta = useMemo(() => {
    if (!spec || !last || !prev || !indicator?.source) return null;
    return buildTodayIndicatorMeta({
      query: spec.query,
      value: last.value,
      prevValue: prev.value,
      unit: indicator.unit,
      lastDate: last.date,
      frequency: indicator.frequency,
      source: indicator.source,
    });
  }, [spec, last, prev, indicator]);

  useDocumentMeta(todayMeta ? {
    title: todayMeta.title,
    description: todayMeta.description,
    path: todayPath(code),
  } : null);

  if (!spec) return <Navigate to={todayPath()} replace />;

  const isError = metaError || dataError;
  const isLoading = loadingMeta || loadingData;
  const refetch = () => { refetchMeta(); refetchData(); };
  const isFetching = fetchingMeta || fetchingData;

  return (
    <div className="fe-data-page max-w-5xl mx-auto px-4 pt-24 pb-20">
      <Breadcrumbs items={todayIndicatorTrail(spec.query, code)} />

      {isError && (
        <ApiRetryBanner onRetry={refetch} isFetching={isFetching} className="mb-6">
          {t('pgui.today.loadError')}
        </ApiRetryBanner>
      )}

      {isLoading && (
        <div role="status" aria-busy="true" aria-label={t('common.loading')}>
          <SkeletonBox className="mb-2 mt-6 h-4 w-32" />
          <SkeletonBox className="mb-4 h-8 w-80 max-w-full sm:h-9" />
          <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <SkeletonBox className="col-span-2 h-[102px] rounded-xl lg:col-span-1" />
            <SkeletonBox className="h-[102px] rounded-xl" />
            <SkeletonBox className="h-[102px] rounded-xl" />
            <SkeletonBox className="h-[102px] rounded-xl" />
          </div>
          <SkeletonBox className="mb-6 h-[26rem] rounded-xl sm:h-[30rem]" />
        </div>
      )}

      {!isLoading && !isError && !(last && indicator) && (
        <div className="rounded-2xl border border-border-subtle bg-surface p-6 text-center text-sm text-text-secondary">
          {t('pgui.today.noData')}
          <div className="mt-4 flex justify-center">
            <Button as={Link} to={todayPath()} variant="secondary" size="sm">{t('today.sectionTitle')}</Button>
          </div>
        </div>
      )}

      {!isLoading && last && indicator && (
        <>
          <p className="fe-today-eyebrow">
            {t('today.page.eyebrow')}
          </p>
          <h1 className="font-display text-2xl sm:text-3xl font-bold text-text-primary mb-4">
            {t('today.page.h1', { query: locale === 'en' ? (t(`today.spec.${code}`) || spec.query) : spec.query })}
          </h1>

          <div className="fe-today-stats">
            <div className="fe-today-stat fe-today-stat--main">
              <p className="fe-today-stat__label">{t('today.page.now')}</p>
              <p className="fe-today-stat__num fe-today-stat__num--main">
                {formatTodayNumber(last.value)}
                {unitSuffix(indicator.unit) ? <span className="fe-today-stat__unit">{unitSuffix(indicator.unit)}</span> : null}
              </p>
              <p className="fe-today-stat__meta">
                {isCbrRate ? t('w3.today.cbrRate', { date: formatTodayRuDate(last.date) }) : formatTodayRuDate(last.date)}
              </p>
              {deltaInfo && (
                <p className="fe-today-stat__delta">
                  {deltaInfo.flat ? (
                    <DeltaBadge delta={0}>{t('w3.tele.noChange')}</DeltaBadge>
                  ) : (
                    <>
                      <DeltaBadge delta={stats.change} polarity={polarity}>{deltaInfo.text}</DeltaBadge>
                      <span className="fe-today-stat__vs">{t('pgui.today.vsPrev')}</span>
                    </>
                  )}
                </p>
              )}
            </div>
            {prev && (
              <div className="fe-today-stat">
                <p className="fe-today-stat__label">{t('today.page.prev')}</p>
                <p className="fe-today-stat__num">{formatTodayNumber(prev.value)}</p>
              </div>
            )}
            {stats && (
              <>
                <div className="fe-today-stat">
                  <p className="fe-today-stat__label">{t('today.page.min')}</p>
                  <p className="fe-today-stat__num">{formatTodayNumber(stats.min)}</p>
                </div>
                <div className="fe-today-stat">
                  <p className="fe-today-stat__label">{t('today.page.max')}</p>
                  <p className="fe-today-stat__num">{formatTodayNumber(stats.max)}</p>
                </div>
              </>
            )}
          </div>

          <div className="fe-today-chart">
            <IndicatorChart
              mode="cpi"
              cpiData={chartPoints}
              showForecast={false}
              unit={indicator.unit || ''}
              rangePreset={rangePreset(freq)}
              chartMode="level"
              indicatorCode={seriesCode}
              indicatorCategory={indicator.category}
              defaultChartType="area"
              cpiChartTitle={t('today.page.dynamics', {
                query: locale === 'en' ? (t(`today.spec.${code}`) || spec.query) : spec.query,
              })}
            />
            <p className="mt-2 text-sm text-text-secondary">
              {t('today.page.source', { source: '' }).replace(/\s*$/, '')}{' '}
              <SourceLink
                href={indicator.source_url}
                className="text-champagne-ink underline-offset-2 hover:underline"
                textClassName=""
              >
                {indicator.source}
              </SourceLink>
            </p>
          </div>

          <Button as={Link} to={russiaIndicatorPath(spec.code)} variant="secondary" className="mb-8">
            {t('today.page.openCard')}
            <ArrowRight size={16} />
          </Button>

          <section className="mb-8">
            <h2 className="font-display text-lg font-semibold text-text-primary mb-3">{t('today.page.recent')}</h2>
            <div className="overflow-x-auto rounded-[1.5rem] border border-border-subtle bg-surface">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-obsidian-light/50 text-left text-[13px] text-text-secondary">
                    <th className="px-4 py-2.5 font-semibold">{t('today.page.colDate')}</th>
                    <th className="px-4 py-2.5 font-semibold">{indicator.unit || t('today.page.colValue')}</th>
                  </tr>
                </thead>
                <tbody>
                  {[...points].reverse().slice(0, 15).map((row) => (
                    <tr key={row.date} className="border-t border-border-subtle tabular-nums">
                      <td className="px-4 py-2 text-text-secondary">{ruDateShort(row.date)}</td>
                      <td className="px-4 py-2 text-text-primary">{formatTodayNumber(row.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="bg-surface border border-border-subtle rounded-[1.5rem] p-5">
            <h2 className="font-display text-base font-semibold text-text-primary mb-2">{t('today.page.fullHistoryTitle')}</h2>
            <p className="text-sm text-text-secondary">
              {t('today.page.fullHistoryBody')}
              {' '}
              <Link to={russiaIndicatorPath(spec.code)} className="text-champagne-ink hover:underline">
                {locale === 'en' && indicator.name_en ? indicator.name_en : indicator.name}
              </Link>
              .
            </p>
          </section>
        </>
      )}
    </div>
  );
}
