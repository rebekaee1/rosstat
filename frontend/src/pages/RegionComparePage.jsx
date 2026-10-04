import { Link, useParams, Navigate } from 'react-router-dom';
import { GitCompare } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import useDocumentMeta from '../lib/useMeta';
import api from '../lib/api';
import { formatRegionValue, shortUnit } from '../lib/regionsApi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import '../styles/platform-pages.css';
import {
  regionHubPath,
  regionIndicatorPath,
  regionPath,
  regionRatingPath,
  regionVsPath,
} from '../lib/sitePaths';
import Breadcrumbs from '../components/Breadcrumbs';
import { regionVsTrail } from '../lib/breadcrumbs';
import { useLocale } from '../i18n';
import { resolveBrowserLocale } from '../i18n/locale';

function parsePair(raw) {
  if (!raw) return null;
  const idx = raw.lastIndexOf('-vs-');
  if (idx <= 0) return null;
  return [raw.slice(0, idx), raw.slice(idx + 4)];
}

function useRegionCompare(slugA, slugB) {
  return useQuery({
    queryKey: ['region-compare', slugA, slugB, resolveBrowserLocale()],
    queryFn: ({ signal }) =>
      api.get(`/regions/vs/${slugA}/${slugB}`, { signal }).then((r) => r.data),
    enabled: !!slugA && !!slugB,
    staleTime: 10 * 60 * 1000,
  });
}

export default function RegionComparePage() {
  const { t } = useLocale();
  const { pair } = useParams();
  const parsed = parsePair(pair);
  const [slugA, slugB] = parsed || [null, null];
  const { data, isLoading, isError, refetch, isFetching } = useRegionCompare(slugA, slugB);

  useDocumentMeta(data ? {
    title: t('regions.compareTitle', { a: data.region_a.name, b: data.region_b.name }),
    description: t('regions.compareMetaDesc', {
      a: data.region_a.name,
      b: data.region_b.name,
      bits: (data.summary_bits || []).slice(0, 3).join('; '),
    }),
    path: data.canonical_path,
  } : null);

  if (!parsed) return <Navigate to={regionHubPath()} replace />;

  if (!isLoading && !data && !isError) {
    return <Navigate to={regionHubPath()} replace />;
  }

  return (
    <div className="fe-data-page max-w-5xl mx-auto px-4 pt-24 pb-20">
      <Breadcrumbs
        items={regionVsTrail(
          data ? `${data.region_a.name} — ${data.region_b.name}` : t('regions.compareCrumb'),
          regionVsPath(slugA, slugB),
        )}
        className="mb-4"
      />

      {isError && (
        <ApiRetryBanner onRetry={refetch} isFetching={isFetching} className="mb-6">
          {t('pgui.regions.compareError')}
        </ApiRetryBanner>
      )}

      {isLoading && (
        <div role="status" aria-busy="true" aria-label={t('common.loading')}>
          <SkeletonBox className="mb-2 h-4 w-40" />
          <SkeletonBox className="mb-3 h-9 w-full max-w-xl sm:h-10" />
          <SkeletonBox className="mb-8 h-6 w-full max-w-3xl" />
          <SkeletonBox className="mb-3 h-7 w-56" />
          <SkeletonBox className="h-[26rem] rounded-xl" />
        </div>
      )}

      {data && (
        <>
          <p className="text-champagne-ink text-xs font-mono uppercase tracking-widest mb-2">
            {t('regions.compareEyebrow')}
          </p>
          <h1 className="font-display text-2xl sm:text-3xl font-bold text-text-primary mb-3">
            {t('regions.compareH1', { a: data.region_a.name, b: data.region_b.name })}
          </h1>
          <p className="text-text-secondary mb-8 max-w-3xl">
            {t('regions.compareIntro')}
          </p>

          {data.rows.length === 0 && (
            <div className="mb-8 rounded-2xl border border-border-subtle bg-surface p-5 text-center text-sm text-text-secondary">
              {t('pgui.regions.compareNoRows')}
            </div>
          )}

          <section className="mb-8">
            <h2 className="font-display text-lg font-semibold text-text-primary mb-3">
              {t('regions.compareTableTitle')}
            </h2>
            <div className="overflow-x-auto rounded-xl border border-border-subtle">
              <table className="w-full text-sm min-w-[32rem]">
                <thead>
                  <tr className="bg-obsidian-light/50 text-left text-[11px] uppercase tracking-wide text-text-secondary">
                    <th className="px-4 py-2.5 font-medium">{t('regions.compareColIndicator')}</th>
                    <th className="px-4 py-2.5 font-medium">{t('common.year')}</th>
                    <th className="px-4 py-2.5 font-medium">{data.region_a.name}</th>
                    <th className="px-4 py-2.5 font-medium">{data.region_b.name}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((row) => (
                    <tr key={row.code} className="border-t border-border-subtle">
                      <td className="px-4 py-2.5 text-text-primary">{row.name}</td>
                      <td className="px-4 py-2.5 font-mono text-text-secondary">{row.year}</td>
                      <td className={`px-4 py-2.5 font-mono ${row.leader_slug === data.region_a.slug ? 'text-champagne-ink font-semibold' : 'text-text-primary'}`}>
                        {formatRegionValue(row.a.value)} {shortUnit(row.unit)}
                      </td>
                      <td className={`px-4 py-2.5 font-mono ${row.leader_slug === data.region_b.slug ? 'text-champagne-ink font-semibold' : 'text-text-primary'}`}>
                        {formatRegionValue(row.b.value)} {shortUnit(row.unit)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {data.rows.map((row) => (
            <section key={row.code} className="mb-6 bg-surface border border-border-subtle rounded-xl p-4">
              <h2 className="font-display text-base font-semibold text-text-primary mb-2">
                {row.name} ({row.year})
              </h2>
              <p className="text-sm text-text-secondary mb-3">
                {data.region_a.name}: <strong className="font-mono text-text-primary">{formatRegionValue(row.a.value)} {shortUnit(row.unit)}</strong>
                {'; '}
                {data.region_b.name}: <strong className="font-mono text-text-primary">{formatRegionValue(row.b.value)} {shortUnit(row.unit)}</strong>.
                {' '}{t('regions.compareVerdict', { verdict: row.verdict })}
              </p>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                <Link to={regionIndicatorPath(row.a.slug, row.code)} className="fe-tap-inline text-champagne-ink hover:underline">
                  {t('regions.compareDynamics', { name: data.region_a.name })}
                </Link>
                <Link to={regionIndicatorPath(row.b.slug, row.code)} className="fe-tap-inline text-champagne-ink hover:underline">
                  {t('regions.compareDynamics', { name: data.region_b.name })}
                </Link>
                <Link to={regionRatingPath(row.code)} className="fe-tap-inline text-champagne-ink hover:underline">
                  {t('regions.compareAllRating')}
                </Link>
              </div>
            </section>
          ))}

          <section className="bg-surface border border-border-subtle rounded-xl p-5">
            <h2 className="font-display text-base font-semibold text-text-primary mb-2 flex items-center gap-2">
              <GitCompare size={16} className="text-champagne-ink" /> {t('regions.compareProfiles')}
            </h2>
            <p className="text-sm text-text-secondary">
              {t('regions.compareProfilesLead')}{' '}
              <Link to={regionPath(data.region_a.slug)} className="text-champagne-ink hover:underline">{data.region_a.name}</Link>
              {', '}
              <Link to={regionPath(data.region_b.slug)} className="text-champagne-ink hover:underline">{data.region_b.name}</Link>.
              {' '}{t('regions.compareProfilesTail')}{' '}
              <Link to="/compare" className="text-champagne-ink hover:underline">{t('regions.compareSection')}</Link>.
            </p>
          </section>
        </>
      )}
    </div>
  );
}
