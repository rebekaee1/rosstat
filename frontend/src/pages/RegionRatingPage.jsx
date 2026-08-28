import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { ArrowDown, ArrowUp, Trophy } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useRegionsHeatmap, formatRegionValue, shortUnit } from '../lib/regionsApi';
import RegionsMap from '../components/RegionsMap';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import { regionRatingTrail } from '../lib/breadcrumbs';
import {
  regionIndicatorPath,
  regionRatingPath,
} from '../lib/sitePaths';
import { useT } from '../i18n';

function ButtonClass(active) {
  return [
    'rounded-xl px-3 py-2 text-xs font-medium transition-colors',
    active
      ? 'bg-champagne/15 text-champagne'
      : 'bg-obsidian-lighter text-text-secondary hover:text-champagne',
  ].join(' ');
}

export default function RegionRatingPage() {
  const t = useT();
  const { code } = useParams();
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch, isFetching } = useRegionsHeatmap(code);
  const achievement = Boolean(data?.rank_as_achievement);
  const serverSort = data?.default_sort === 'asc' ? 'asc' : 'desc';
  // null = ещё не трогали переключатель → берём направление с сервера.
  const [sortOverride, setSortOverride] = useState(null);
  const sortDirection = sortOverride ?? serverSort;

  useEffect(() => {
    setSortOverride(null);
  }, [code]);

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
    <div className="max-w-5xl mx-auto px-4 pt-24 pb-20">
      <Breadcrumbs
        items={regionRatingTrail(
          achievement ? `Рейтинг: ${data?.indicator?.name || '…'}` : (data?.indicator?.name || '…'),
          code,
        )}
      />

      {isError && <ApiRetryBanner onRetry={refetch} retrying={isFetching} />}

      {isLoading && (
        <div className="space-y-4">
          <SkeletonBox className="h-10 w-96 max-w-full" />
          <SkeletonBox className="h-64 rounded-xl" />
        </div>
      )}

      {data && ranked.length >= 10 && (
        <>
          <p className="text-champagne text-xs font-mono uppercase tracking-widest mb-2">
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
          <p className="text-text-secondary mb-4 max-w-3xl">
            {achievement ? t('regions.rating.eyebrowAchievement') : t('regions.rating.eyebrowNeutral')}
            {' '}
            {ranked.length}
            {' '}
            {t('regions.rating.subjectsOf', { name: data.indicator.name, year: data.year })}
            {' '}
            {bestLabel}
            {' '}
            {t('regions.rating.atRegion')}
            {' '}
            {top.name}
            {' — '}
            {formatRegionValue(top.raw ?? top.value)}
            {' '}
            {shortUnit(data.indicator.unit)}.
          </p>

          <div className="mb-6 flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary mr-1">
              {t('regions.rating.sort')}
            </span>
            <button type="button" className={ButtonClass(sortDirection === 'desc')} onClick={() => setSortOverride('desc')}>
              {t('regions.rating.sortDesc')}
            </button>
            <button type="button" className={ButtonClass(sortDirection === 'asc')} onClick={() => setSortOverride('asc')}>
              {t('regions.rating.sortAsc')}
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-8">
            <div className="bg-surface border border-border-subtle rounded-xl p-3.5">
              <div className="text-[11px] text-text-tertiary uppercase tracking-wide flex items-center gap-1">
                {achievement && <Trophy size={12} className="text-champagne" />}
                {bestLabel}
              </div>
              <div className="mt-1 font-semibold text-text-primary">{top.name}</div>
              <div className="font-mono text-sm text-text-secondary">
                {formatRegionValue(top.raw ?? top.value)}
                {' '}
                {shortUnit(data.indicator.unit)}
              </div>
            </div>
            <div className="bg-surface border border-border-subtle rounded-xl p-3.5">
              <div className="text-[11px] text-text-tertiary uppercase tracking-wide">{worstLabel}</div>
              <div className="mt-1 font-semibold text-text-primary">{bottom.name}</div>
              <div className="font-mono text-sm text-text-secondary">
                {formatRegionValue(bottom.raw ?? bottom.value)}
                {' '}
                {shortUnit(data.indicator.unit)}
              </div>
            </div>
            <div className="bg-surface border border-border-subtle rounded-xl p-3.5">
              <div className="text-[11px] text-text-tertiary uppercase tracking-wide">{t('regions.rating.dataFor')}</div>
              <div className="mt-1 font-mono font-semibold text-text-primary">
                {data.year}
                {' '}
                год
              </div>
            </div>
          </div>

          <div className="bg-surface border border-border-subtle rounded-xl p-4 mb-8">
            <RegionsMap
              valuesBySlug={mapValues}
              unit={data.indicator.unit}
              nameBySlug={nameBySlug}
              colorDirection={sortDirection}
              onSelect={(slug) => navigate(regionIndicatorPath(slug, code))}
            />
          </div>

          <section className="mb-8">
            <h2 className="font-display text-lg font-semibold text-text-primary mb-3">
              {listTitle}
            </h2>
            <div className="overflow-x-auto rounded-xl border border-border-subtle max-h-[32rem]">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-obsidian-light/95 backdrop-blur-sm z-10">
                  <tr className="text-left text-[11px] uppercase tracking-wide text-text-tertiary">
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
                        className="inline-flex items-center gap-1 rounded-lg transition-colors hover:text-champagne"
                      >
                        {data.indicator.unit || t('regions.rating.colValue')}
                        {sortDirection === 'asc'
                          ? <ArrowUp size={12} aria-hidden="true" />
                          : <ArrowDown size={12} aria-hidden="true" />}
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {ranked.map((row) => (
                    <tr key={row.slug} className="border-t border-border-subtle hover:bg-surface-hover">
                      <td className="px-4 py-2 font-mono text-text-tertiary">{row.rank}</td>
                      <td className="px-4 py-2">
                        <Link
                          to={regionIndicatorPath(row.slug, code)}
                          className="text-text-primary hover:text-champagne transition-colors"
                        >
                          {row.name}
                        </Link>
                      </td>
                      <td className="px-4 py-2 text-right font-mono text-text-primary">
                        {formatRegionValue(row.raw ?? row.value)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="bg-surface border border-border-subtle rounded-xl p-5">
            <h2 className="font-display text-base font-semibold text-text-primary mb-2">{t('regions.rating.sourceHeading')}</h2>
            <p className="text-sm text-text-secondary">
              Сборник Росстата «Регионы России. Социально-экономические показатели».
              Значения за
              {' '}
              {data.year}
              {' '}
              год. По каждому региону — страница с полной динамикой с 1990 года.
            </p>
          </section>
        </>
      )}

      {!isLoading && !isError && data && ranked.length < 10 && (
        <p className="text-text-secondary">{t('regions.rating.empty')}</p>
      )}
    </div>
  );
}
