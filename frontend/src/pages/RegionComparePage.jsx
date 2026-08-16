import { Link, useParams, Navigate } from 'react-router-dom';
import { ChevronRight, GitCompare } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import useDocumentMeta from '../lib/useMeta';
import api from '../lib/api';
import { formatRegionValue, shortUnit } from '../lib/regionsApi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import {
  regionHubPath,
  regionIndicatorPath,
  regionPath,
  regionRatingPath,
} from '../lib/sitePaths';
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
    <div className="max-w-5xl mx-auto px-4 pt-24 pb-20">
      <nav className="flex items-center gap-1.5 text-xs text-text-tertiary mb-4 overflow-hidden" aria-label={t('crumb.aria')}>
        <Link to="/" className="hover:text-champagne transition-colors shrink-0">{t('common.home')}</Link>
        <ChevronRight size={12} className="shrink-0" />
        <Link to={regionHubPath()} className="hover:text-champagne transition-colors shrink-0">{t('regions.regionsLabel')}</Link>
        <ChevronRight size={12} className="shrink-0" />
        <span className="text-text-secondary truncate">
          {data ? `${data.region_a.name} vs ${data.region_b.name}` : t('regions.compareCrumb')}
        </span>
      </nav>

      {isError && <ApiRetryBanner onRetry={refetch} retrying={isFetching} />}

      {isLoading && (
        <div className="space-y-4">
          <SkeletonBox className="h-10 w-96 max-w-full" />
          <SkeletonBox className="h-48 rounded-xl" />
        </div>
      )}

      {data && (
        <>
          <p className="text-champagne text-xs font-mono uppercase tracking-widest mb-2">
            {t('regions.compareEyebrow')}
          </p>
          <h1 className="font-display text-2xl sm:text-3xl font-bold text-text-primary mb-3">
            {t('regions.compareH1', { a: data.region_a.name, b: data.region_b.name })}
          </h1>
          <p className="text-text-secondary mb-8 max-w-3xl">
            {t('regions.compareIntro')}
          </p>

          <section className="mb-8">
            <h2 className="font-display text-lg font-semibold text-text-primary mb-3">
              {t('regions.compareTableTitle')}
            </h2>
            <div className="overflow-x-auto rounded-xl border border-border-subtle">
              <table className="w-full text-sm min-w-[32rem]">
                <thead>
                  <tr className="bg-obsidian-light/50 text-left text-[11px] uppercase tracking-wide text-text-tertiary">
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
                      <td className="px-4 py-2.5 font-mono text-text-tertiary">{row.year}</td>
                      <td className={`px-4 py-2.5 font-mono ${row.leader_slug === data.region_a.slug ? 'text-champagne font-semibold' : 'text-text-primary'}`}>
                        {formatRegionValue(row.a.value)} {shortUnit(row.unit)}
                      </td>
                      <td className={`px-4 py-2.5 font-mono ${row.leader_slug === data.region_b.slug ? 'text-champagne font-semibold' : 'text-text-primary'}`}>
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
              <div className="flex flex-wrap gap-3 text-xs">
                <Link to={regionIndicatorPath(row.a.slug, row.code)} className="text-champagne hover:underline">
                  {t('regions.compareDynamics', { name: data.region_a.name })}
                </Link>
                <Link to={regionIndicatorPath(row.b.slug, row.code)} className="text-champagne hover:underline">
                  {t('regions.compareDynamics', { name: data.region_b.name })}
                </Link>
                <Link to={regionRatingPath(row.code)} className="text-champagne hover:underline">
                  {t('regions.compareAllRating')}
                </Link>
              </div>
            </section>
          ))}

          <section className="bg-surface border border-border-subtle rounded-xl p-5">
            <h2 className="font-display text-base font-semibold text-text-primary mb-2 flex items-center gap-2">
              <GitCompare size={16} className="text-champagne" /> {t('regions.compareProfiles')}
            </h2>
            <p className="text-sm text-text-secondary">
              {t('regions.compareProfilesLead')}{' '}
              <Link to={regionPath(data.region_a.slug)} className="text-champagne hover:underline">{data.region_a.name}</Link>
              {', '}
              <Link to={regionPath(data.region_b.slug)} className="text-champagne hover:underline">{data.region_b.name}</Link>.
              {' '}{t('regions.compareProfilesTail')}{' '}
              <Link to="/compare" className="text-champagne hover:underline">{t('regions.compareSection')}</Link>.
            </p>
          </section>
        </>
      )}
    </div>
  );
}
