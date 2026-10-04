import { Link, useParams, Navigate } from 'react-router-dom';
import { GitCompare, Trophy, ChevronRight } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import useDocumentMeta from '../lib/useMeta';
import api from '../lib/api';
import { formatRegionWithUnit } from '../lib/regionUi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import '../styles/platform-pages.css';
import '../styles/regions-w4.css';
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
  const { t, locale } = useLocale();
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
    <div className="fe-data-page max-w-5xl mx-auto px-4 pt-24 pb-12 sm:pb-16">
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
          <p className="mb-2 text-sm font-medium text-champagne-ink">
            {t('regions.compareEyebrow')}
          </p>
          <h1 className="font-display text-2xl sm:text-3xl font-bold text-text-primary mb-3">
            {t('regions.compareH1', { a: data.region_a.name, b: data.region_b.name })}
          </h1>
          <p className="mb-6 max-w-3xl text-[15px] leading-relaxed text-text-secondary">
            {t('regions.compareIntro')}
          </p>

          {data.rows.length === 0 && (
            <div className="mb-8 rounded-3xl border border-border-subtle bg-surface p-6 text-center text-sm text-text-secondary">
              <GitCompare size={22} className="mx-auto mb-2 text-champagne-ink" aria-hidden="true" />
              {t('pgui.regions.compareNoRows')}
            </div>
          )}

          <div className="mb-8 grid gap-3 md:grid-cols-2">
            {data.rows.map((row, index) => {
              const side = (region, point) => {
                const leader = row.leader_slug === region.slug;
                return (
                  <Link
                    to={regionIndicatorPath(region.slug, row.code)}
                    className={`fe-press min-w-0 rounded-2xl border p-3 transition-colors ${
                      leader
                        ? 'border-border-champagne bg-champagne/[0.07]'
                        : 'border-border-subtle bg-obsidian-light hover:border-border-champagne'
                    }`}
                  >
                    <span className="flex items-center gap-1 text-[13px] leading-snug text-text-secondary">
                      {leader && <Trophy size={13} className="shrink-0 text-champagne-ink" aria-hidden="true" />}
                      <span className="min-w-0">{region.name}</span>
                    </span>
                    <span className={`fe-num mt-1 block whitespace-nowrap text-lg font-semibold ${leader ? 'text-champagne-ink' : 'text-text-primary'}`}>
                      {formatRegionWithUnit(point.value, row.unit, locale)}
                    </span>
                  </Link>
                );
              };
              return (
                <section
                  key={row.code}
                  className="fe-panel fe-reveal rounded-3xl p-4"
                  style={{ '--fe-delay': `${Math.min(index, 5) * 0.04}s`, '--fe-rise': '8px' }}
                >
                  <h2 className="font-display text-base font-semibold leading-snug text-text-primary">
                    {row.name}
                    <span className="font-normal text-text-secondary">{` (${row.year})`}</span>
                  </h2>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    {side(data.region_a, row.a)}
                    {side(data.region_b, row.b)}
                  </div>
                  {row.verdict && (
                    <p className="mt-3 text-sm text-text-secondary">{t('regions.compareVerdict', { verdict: row.verdict })}</p>
                  )}
                  <Link to={regionRatingPath(row.code)} className="fe-tap-inline mt-1 gap-1 text-sm text-champagne-ink hover:underline">
                    {t('regions.compareAllRating')}
                    <ChevronRight size={14} aria-hidden="true" />
                  </Link>
                </section>
              );
            })}
          </div>

          <section className="rounded-3xl border border-border-subtle bg-surface p-5">
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
