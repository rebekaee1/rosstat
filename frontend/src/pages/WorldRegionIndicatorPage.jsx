// Ряд субнационального показателя: /{country}/region/{slug}/{code}
import { useMemo, useRef } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { Download, Image as ImageIcon, Table2 } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useWorldRegionIndicator, formatSubnationalValue } from '../lib/worldSubnationalApi';
import RegionAnnualChart from '../components/RegionAnnualChart';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import { worldSubnationalIndicatorTrail } from '../lib/breadcrumbs';
import { useAuth } from '../context/authContext';
import { exportNodeToPng } from '../lib/chartImage';
import {
  RUSSIA,
  countryRegionPath,
  countryRegionsPath,
  regionIndicatorPath,
} from '../lib/sitePaths';
import { useLocale } from '../i18n';

export default function WorldRegionIndicatorPage() {
  const { countrySlug, slug, code } = useParams();
  const { t, locale } = useLocale();
  const { isAuthenticated } = useAuth();
  const chartRef = useRef(null);
  const data = useWorldRegionIndicator(countrySlug === RUSSIA ? undefined : countrySlug, slug, code);

  const countryName = data.data?.country?.name || countrySlug;
  const regionName = data.data?.region?.name || slug;
  const indName = data.data?.indicator?.name || code;
  const kindPlural = data.data?.country
    ? (data.data.kind_label_plural || data.data.kind_label)
    : t('world.regions.fallbackKindPlural');
  const nationalName = `— ${countryName}`;

  useDocumentMeta({
    title: `${indName} — ${regionName} | Forecast Economy`,
    description: t('world.regions.seriesDescription', {
      indicator: indName,
      region: regionName,
      country: countryName,
    }),
  });

  const series = useMemo(() => data.data?.series || [], [data.data]);
  const nationalSeries = useMemo(() => data.data?.national?.series || [], [data.data]);

  if (countrySlug === RUSSIA) {
    return <Navigate to={regionIndicatorPath(slug, code)} replace />;
  }

  const downloadCsv = () => {
    const rows = [['date', 'value']];
    for (const p of series) rows.push([p.date, p.value]);
    const blob = new Blob([rows.map((r) => r.join(',')).join('\n')], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${slug}-${code}.csv`;
    a.click();
  };

  return (
    <div className="mx-auto w-full max-w-7xl overflow-x-clip px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs
        items={worldSubnationalIndicatorTrail(
          countryName, countrySlug, kindPlural, regionName, slug, indName, code,
        )}
      />
      {data.isError && (
        <ApiRetryBanner onRetry={data.refetch} isFetching={data.isFetching} className="mb-6">
          {t('world.regions.loadError')}
        </ApiRetryBanner>
      )}
      {data.isLoading && (
        <div className="space-y-4">
          <SkeletonBox className="h-9 w-80" />
          <SkeletonBox className="h-72 rounded-xl" />
        </div>
      )}
      {data.data && (
        <>
          <div className="mb-2 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
            {data.data.indicator.frequency}
            {data.data.indicator.unit ? ` — ${data.data.indicator.unit}` : ''}
          </div>
          <h1 className="font-display text-[1.65rem] font-bold leading-tight text-text-primary sm:text-4xl">
            {indName}
          </h1>
          <p className="mt-2 text-sm text-text-secondary">
            {regionName}
            {data.data.rank != null
              ? ` — ${t('world.regions.rankOf', { rank: data.data.rank, total: data.data.of })}`
              : ''}
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-border-subtle bg-surface p-4">
              <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-tertiary">
                {t('world.regions.latest')}
              </div>
              <div className="mt-1 font-mono text-xl font-semibold tabular-nums">
                {formatSubnationalValue(data.data.last_value, locale)}
              </div>
              <div className="mt-1 text-xs text-text-tertiary">{data.data.last_period_label}</div>
            </div>
          </div>
          <div ref={chartRef} className="mt-6 rounded-2xl border border-border-subtle bg-surface p-3 sm:p-4">
            <RegionAnnualChart
              series={series}
              russiaSeries={nationalSeries}
              unit={data.data.indicator.unit}
              regionName={regionName}
              frequency={data.data.indicator.frequency}
              nationalLabel={nationalName}
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={downloadCsv}
              className="inline-flex items-center gap-1.5 rounded-xl bg-obsidian-lighter px-3 py-1.5 text-sm text-text-secondary hover:text-champagne"
            >
              <Download size={14} /> {t('world.regions.exportCsv')}
            </button>
            {isAuthenticated && (
              <button
                type="button"
                onClick={() => exportNodeToPng(chartRef.current, `${slug}-${code}.png`)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-obsidian-lighter px-3 py-1.5 text-sm text-text-secondary hover:text-champagne"
              >
                <ImageIcon size={14} /> {t('world.regions.exportPng')}
              </button>
            )}
          </div>
          <section className="mt-8">
            <h2 className="text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
              {t('world.regions.methodology')}
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-text-secondary">
              {data.data.indicator.description}
            </p>
            <p className="mt-3 max-w-3xl font-mono text-xs leading-5 text-text-tertiary">
              {data.data.indicator.methodology}
            </p>
            {data.data.indicator.source && (
              <p className="mt-3 text-sm text-text-secondary">
                {t('world.regions.source')}: {data.data.indicator.source}
              </p>
            )}
          </section>
          <section className="mt-8">
            <h2 className="mb-3 inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
              <Table2 size={12} /> {t('world.regions.table')}
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[20rem] text-sm">
                <thead>
                  <tr className="text-left text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
                    <th className="pb-2 pr-3">{t('world.regions.period')}</th>
                    <th className="pb-2">{regionName}</th>
                  </tr>
                </thead>
                <tbody>
                  {[...series].reverse().slice(0, 36).map((p) => (
                    <tr key={p.date} className="border-t border-border-subtle">
                      <td className="py-1.5 pr-3 font-mono text-text-tertiary">{p.label}</td>
                      <td className="py-1.5 font-mono tabular-nums">
                        {formatSubnationalValue(p.value, locale)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <p className="mt-8 flex flex-wrap gap-4 text-sm">
            <Link to={countryRegionPath(countrySlug, slug)} className="text-champagne hover:underline">
              {t('world.regions.backToProfile', { region: regionName })}
            </Link>
            <Link to={countryRegionsPath(countrySlug)} className="text-text-secondary hover:text-champagne">
              {t('world.regions.backToHub', { kind: kindPlural })}
            </Link>
          </p>
        </>
      )}
    </div>
  );
}
