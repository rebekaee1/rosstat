import { useMemo, useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { ArrowDown, ArrowUp, Trophy, BarChart3 } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useRegionsHeatmap } from '../lib/regionsApi';
import { formatRegionNumber, formatRegionWithUnit, unitLabel } from '../lib/regionUi';
import RegionsMap from '../components/RegionsMap';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import { regionRatingTrail } from '../lib/breadcrumbs';
import {
  regionIndicatorPath,
  regionRatingHubPath,
  regionRatingPath,
} from '../lib/sitePaths';
import Chip from '../components/Chip';
import { useT, useLocale } from '../i18n';
import '../styles/platform-pages.css';
import '../styles/regions-w4.css';

export default function RegionRatingPage() {
  const t = useT();
  const { locale } = useLocale();
  const { code } = useParams();
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch, isFetching } = useRegionsHeatmap(code);
  const achievement = Boolean(data?.rank_as_achievement);
  const serverSort = data?.default_sort === 'asc' ? 'asc' : 'desc';
  // null = ещё не трогали переключатель → берём направление с сервера.
  // Выбор привязан к коду показателя, поэтому при смене показателя сбрасывается сам.
  const [sortState, setSortState] = useState({ code, value: null });
  const sortOverride = sortState.code === code ? sortState.value : null;
  const setSortOverride = (value) => setSortState({ code, value });
  const sortDirection = sortOverride ?? serverSort;

  const ranked = useMemo(() => {
    if (!data?.values?.length) return [];
    const rows = [...data.values].sort((a, b) => {
      const av = a.raw ?? a.value;
      const bv = b.raw ?? b.value;
      return sortDirection === 'asc' ? av - bv : bv - av;
    });
    return rows.map((row, i) => ({ ...row, rank: i + 1 }));
  }, [data, sortDirection]);

  const top = ranked[0];
  const bottom = ranked[ranked.length - 1];
  const mapValues = useMemo(() => {
    if (!data?.values) return null;
    return new Map(data.values.map((v) => [v.slug, v.raw ?? v.value]));
  }, [data]);
  const nameBySlug = useMemo(() => {
    if (!data?.values) return {};
    return Object.fromEntries(data.values.map((v) => [v.slug, v.name]));
  }, [data]);

  const bestLabel = achievement ? t('regions.rating.best') : t('regions.rating.highest');
  const worstLabel = achievement ? t('regions.rating.worst') : t('regions.rating.lowest');
  const listTitle = achievement
    ? t('regions.rating.listAchievement', { n: ranked.length })
    : t('regions.rating.listNeutral', { n: ranked.length });
  const tableCol = achievement ? t('regions.rating.place') : '№';

  useDocumentMeta(data ? {
    title: achievement
      ? t('regions.rating.titleAchievement', { name: data.indicator.name, year: data.year })
      : t('regions.rating.titleNeutral', { name: data.indicator.name, year: data.year }),
    description:
      `${data.indicator.name} (${data.year}): `
      + `${ranked.length}.`
      + (top ? ` ${bestLabel} — ${top.name}.` : ''),
    path: regionRatingPath(code),
  } : null);

  return (
    <div className="fe-data-page max-w-5xl mx-auto px-4 pt-24 pb-12 sm:pb-16">
      <Breadcrumbs
        items={regionRatingTrail(
          achievement ? t('w4.rating.crumb', { name: data?.indicator?.name || '…' }) : (data?.indicator?.name || '…'),
          code,
        )}
      />

      {isError && (
        <ApiRetryBanner onRetry={refetch} isFetching={isFetching} className="mb-6">
          {t('pgui.regions.ratingError')}
        </ApiRetryBanner>
      )}

      {isLoading && (
        <div role="status" aria-busy="true" aria-label={t('common.loading')}>
          <SkeletonBox className="mb-2 mt-6 h-4 w-48" />
          <SkeletonBox className="mb-3 h-8 w-full max-w-xl sm:h-9" />
          <SkeletonBox className="mb-4 h-12 w-full max-w-3xl" />
          <SkeletonBox className="mb-6 h-9 w-72 max-w-full" />
          <div className="mb-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <SkeletonBox className="h-[92px] rounded-xl" />
            <SkeletonBox className="h-[92px] rounded-xl" />
            <SkeletonBox className="h-[92px] rounded-xl" />
          </div>
          <SkeletonBox className="mb-8 aspect-[1000/538] w-full rounded-xl" />
          <SkeletonBox className="h-[32rem] rounded-xl" />
        </div>
      )}

      {data && ranked.length >= 10 && (
        <>
          <p className="mb-2 text-sm font-medium text-champagne-ink">
            {achievement ? t('regions.rating.eyebrowAchievement') : t('regions.rating.eyebrowNeutral')}
            {' — '}
            {data.year}
            {' '}
            {t('common.year').toLowerCase()}
          </p>
          <h1 className="font-display text-2xl sm:text-3xl font-bold text-text-primary mb-3">
            {data.indicator.name}
            :
            {' '}
            {achievement ? t('regions.rating.h1Achievement') : t('regions.rating.h1Neutral')}
          </h1>
          <p className="mb-5 max-w-3xl text-[15px] leading-relaxed text-text-secondary">
            {t('w4.rating.lead', {
              n: ranked.length,
              name: data.indicator.name,
              year: data.year,
              best: bestLabel,
              region: top.name,
              value: formatRegionWithUnit(top.raw ?? top.value, data.indicator.unit, locale),
            })}
          </p>

          <div className="mb-6 flex flex-wrap items-center gap-2">
            <span className="mr-1 text-sm text-text-secondary">
              {t('regions.rating.sort')}
            </span>
            <Chip active={sortDirection === 'desc'} onClick={() => setSortOverride('desc')}>
              {t('regions.rating.sortDesc')}
            </Chip>
            <Chip active={sortDirection === 'asc'} onClick={() => setSortOverride('asc')}>
              {t('regions.rating.sortAsc')}
            </Chip>
          </div>

          <div className="mb-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-border-subtle bg-surface p-4">
              <div className="flex items-center gap-1 text-xs font-medium text-text-secondary">
                {achievement && <Trophy size={13} className="text-champagne-ink" aria-hidden="true" />}
                {bestLabel}
              </div>
              <div className="mt-1 font-semibold text-text-primary">{top.name}</div>
              <div className="fe-num text-sm text-text-secondary">
                {formatRegionWithUnit(top.raw ?? top.value, data.indicator.unit, locale)}
              </div>
            </div>
            <div className="rounded-2xl border border-border-subtle bg-surface p-4">
              <div className="text-xs font-medium text-text-secondary">{worstLabel}</div>
              <div className="mt-1 font-semibold text-text-primary">{bottom.name}</div>
              <div className="fe-num text-sm text-text-secondary">
                {formatRegionWithUnit(bottom.raw ?? bottom.value, data.indicator.unit, locale)}
              </div>
            </div>
            <div className="rounded-2xl border border-border-subtle bg-surface p-4">
              <div className="text-xs font-medium text-text-secondary">{t('regions.rating.dataFor')}</div>
              <div className="fe-num mt-1 font-semibold text-text-primary">{t('w4.map.yearLabel', { year: data.year })}</div>
            </div>
          </div>

          <div className="mb-8 rounded-3xl border border-border-subtle bg-surface p-3 sm:p-5">
            <RegionsMap
              valuesBySlug={mapValues}
              unit={data.indicator.unit}
              nameBySlug={nameBySlug}
              colorDirection={sortDirection}
              onSelect={(slug) => navigate(regionIndicatorPath(slug, code))}
            />
          </div>

          <section id="chart" className="mb-8 scroll-mt-28">
            <h2 className="mb-3 font-display text-xl font-bold text-text-primary">
              {listTitle}
            </h2>
            <div className="max-h-[32rem] overflow-auto rounded-2xl border border-border-subtle bg-surface">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-obsidian-light/95 backdrop-blur-sm z-10">
                  <tr className="text-left text-xs font-medium text-text-secondary">
                    <th className="px-4 py-2.5 font-medium w-16">{tableCol}</th>
                    <th className="px-4 py-2.5 font-medium">{t('regions.rating.colRegion')}</th>
                    <th
                      aria-sort={sortDirection === 'asc' ? 'ascending' : 'descending'}
                      className="px-4 py-2.5 font-medium text-right"
                    >
                      <button
                        type="button"
                        onClick={() => setSortOverride(sortDirection === 'asc' ? 'desc' : 'asc')}
                        title={sortDirection === 'asc'
                          ? t('regions.rating.sortAsc')
                          : t('regions.rating.sortDesc')}
                        className="fe-tap-inline gap-1 rounded-lg transition-colors hover:text-champagne-ink"
                      >
                        {unitLabel(data.indicator.unit, locale) || t('regions.rating.colValue')}
                        {sortDirection === 'asc'
                          ? <ArrowUp size={12} aria-hidden="true" />
                          : <ArrowDown size={12} aria-hidden="true" />}
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {ranked.map((row) => (
                    <tr key={row.slug} className="fe-row-link border-t border-border-subtle">
                      <td className="fe-num px-4 py-2 text-text-secondary">{row.rank}</td>
                      <td className="px-4 py-2">
                        <Link
                          to={regionIndicatorPath(row.slug, code)}
                          className="fe-row-link__a text-text-primary hover:text-champagne-ink transition-colors"
                        >
                          {row.name}
                        </Link>
                      </td>
                      <td className="fe-num whitespace-nowrap px-4 py-2 text-right text-text-primary">
                        {formatRegionNumber(row.raw ?? row.value, data.indicator.unit, locale)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-3xl border border-border-subtle bg-surface p-5">
            <h2 className="mb-2 font-display text-base font-semibold text-text-primary">{t('regions.rating.sourceHeading')}</h2>
            <p className="text-sm leading-relaxed text-text-secondary">
              {t('w4.rating.source', { year: data.year })}
            </p>
          </section>
        </>
      )}

      {!isLoading && !isError && (!data || ranked.length < 10) && (
        <div role="status" className="rounded-3xl border border-border-subtle bg-surface p-6 text-center text-sm text-text-secondary">
          <BarChart3 size={24} className="mx-auto mb-2 text-champagne-ink" aria-hidden="true" />
          <p>{t('regions.rating.empty')}</p>
          <Link to={regionRatingHubPath()} className="fe-tap-inline mt-2 text-champagne-ink hover:underline">
            {t('w4.rating.backToAll')}
          </Link>
        </div>
      )}
    </div>
  );
}
