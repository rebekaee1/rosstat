import { useMemo } from 'react';
import { Link, useParams, Navigate } from 'react-router-dom';
import { ArrowRight, TrendingUp, TrendingDown } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useIndicator, useIndicatorData } from '../lib/hooks';
import { getTodaySpec, todaySeriesCode } from '../lib/todaySpecs';
import {
  buildTodayIndicatorMeta,
  formatTodayNumber,
  formatTodayRuDate,
} from '../lib/todayFormat';
import { formatChange, unitSuffix } from '../lib/format';
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
    <div className="max-w-5xl mx-auto px-4 pt-24 pb-20">
      <Breadcrumbs items={todayIndicatorTrail(spec.query, code)} />

      {isError && <ApiRetryBanner onRetry={refetch} retrying={isFetching} />}

      {isLoading && (
        <div className="space-y-4">
          <SkeletonBox className="h-10 w-80 max-w-full" />
          <SkeletonBox className="h-72 rounded-xl" />
        </div>
      )}

      {!isLoading && last && indicator && (
        <>
          <p className="text-champagne text-xs font-mono uppercase tracking-widest mb-2">
            {t('today.page.eyebrow')}
          </p>
          <h1 className="font-display text-2xl sm:text-3xl font-bold text-text-primary mb-4">
            {t('today.page.h1', { query: locale === 'en' ? (t(`today.spec.${code}`) || spec.query) : spec.query })}
          </h1>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <div className="bg-surface border border-border-subtle rounded-xl p-3.5 col-span-2 lg:col-span-1">
              <div className="text-[11px] text-text-tertiary uppercase tracking-wide">{t('today.page.now')}</div>
              <div className="mt-1 font-mono text-2xl font-bold text-text-primary">
                {formatTodayNumber(last.value)}
                <span className="ml-1 text-sm font-normal text-text-secondary">{unitSuffix(indicator.unit)}</span>
              </div>
              <div className="mt-1 text-[11px] text-text-tertiary">{formatTodayRuDate(last.date)}</div>
            </div>
            {prev && (
              <div className="bg-surface border border-border-subtle rounded-xl p-3.5">
                <div className="text-[11px] text-text-tertiary uppercase tracking-wide">{t('today.page.prev')}</div>
                <div className="mt-1 font-mono font-semibold text-text-primary">{formatTodayNumber(prev.value)}</div>
              </div>
            )}
            {stats && (
              <>
                <div className="bg-surface border border-border-subtle rounded-xl p-3.5">
                  <div className="text-[11px] text-text-tertiary uppercase tracking-wide">{t('today.page.min')}</div>
                  <div className="mt-1 font-mono font-semibold text-text-primary">{formatTodayNumber(stats.min)}</div>
                </div>
                <div className="bg-surface border border-border-subtle rounded-xl p-3.5">
                  <div className="text-[11px] text-text-tertiary uppercase tracking-wide">{t('today.page.max')}</div>
                  <div className="mt-1 font-mono font-semibold text-text-primary">{formatTodayNumber(stats.max)}</div>
                </div>
              </>
            )}
          </div>

          {stats?.change != null && Math.abs(stats.change) >= 1e-12 && (
            <div className={`inline-flex items-center gap-1.5 text-sm font-mono mb-4 ${stats.change > 0 ? 'text-positive' : 'text-negative'}`}>
              {stats.change > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
              {formatChange(stats.change, indicator.unit)} к предыдущему значению
            </div>
          )}

          <div className="bg-surface border border-border-subtle rounded-xl p-4 mb-6">
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
            <p className="mt-2 text-[11px] text-text-tertiary font-mono">
              {t('today.page.source', { source: indicator.source })}
            </p>
          </div>

          <Link
            to={russiaIndicatorPath(spec.code)}
            className="inline-flex items-center gap-2 mb-8 px-4 py-2.5 rounded-xl bg-champagne/10 text-champagne font-medium hover:bg-champagne/20 transition-colors"
          >
            {t('today.page.openCard')}
            <ArrowRight size={16} />
          </Link>

          <section className="mb-8">
            <h2 className="font-display text-lg font-semibold text-text-primary mb-3">{t('today.page.recent')}</h2>
            <div className="overflow-x-auto rounded-xl border border-border-subtle">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-obsidian-light/50 text-left text-[11px] uppercase tracking-wide text-text-tertiary">
                    <th className="px-4 py-2.5 font-medium">{t('today.page.colDate')}</th>
                    <th className="px-4 py-2.5 font-medium">{indicator.unit || t('today.page.colValue')}</th>
                  </tr>
                </thead>
                <tbody>
                  {[...points].reverse().slice(0, 15).map((row) => (
                    <tr key={row.date} className="border-t border-border-subtle font-mono">
                      <td className="px-4 py-2 text-text-secondary">{ruDateShort(row.date)}</td>
                      <td className="px-4 py-2 text-text-primary">{formatTodayNumber(row.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="bg-surface border border-border-subtle rounded-xl p-5">
            <h2 className="font-display text-base font-semibold text-text-primary mb-2">{t('today.page.fullHistoryTitle')}</h2>
            <p className="text-sm text-text-secondary">
              {t('today.page.fullHistoryBody')}
              {' '}
              <Link to={russiaIndicatorPath(spec.code)} className="text-champagne hover:underline">
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
