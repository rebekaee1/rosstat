// Рейтинг регионов прямо на странице «Регионы России»: выбранный показатель, место, значение и полоса.
// Раньше здесь были шесть ссылок без выбора и список регионов по алфавиту. Теперь по умолчанию виден
// настоящий рейтинг (место, название, полоса, значение), а «Ещё показатели» открывает поиск по всему каталогу.
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDown, ArrowUp, Search, X } from 'lucide-react';
import { SkeletonBox } from '../Skeleton';
import ApiRetryBanner from '../ApiRetryBanner';
import { useRegionsCatalog, useRegionsHeatmap } from '../../lib/regionsApi';
import { formatRegionNumber, unitLabel } from '../../lib/regionUi';
import { filterSearchOptions } from '../../lib/searchSynonyms';
import { regionIndicatorPath, regionPath, regionRatingHubPath, regionRatingPath } from '../../lib/sitePaths';
import { track, events } from '../../lib/track';
import { useLocale } from '../../i18n';
import '../../styles/regions-w4.css';
import '../../styles/w6f-pages.css';
import '../../styles/k6-country.css';

const FIRST_ROWS = 12;

/** Поле «Ещё показатели»: поиск по всему каталогу региональной статистики (сотни показателей). */
function MoreMetrics({ total, onPick }) {
  const { t } = useLocale();
  const catalog = useRegionsCatalog();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(30);
  const results = useMemo(() => {
    const all = (catalog.data?.sections || []).flatMap((s) => (s.indicators || []).map((i) => ({ ...i, section: s.name })));
    return query.trim() ? filterSearchOptions(all, query) : all;
  }, [catalog.data, query]);

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fe-chip fe-press gap-1.5 text-champagne-ink"
        data-testid="ranking-more"
      >
        <Search size={14} aria-hidden="true" />
        {total ? t('w6f.rank.more', { n: total }) : t('w6f.rank.moreNoCount')}
      </button>
    );
  }
  return (
    <div className="fe-rank-more">
      <div className="fe-rank-more__field">
        <Search size={14} aria-hidden="true" className="shrink-0 text-text-secondary" />
        <input
          type="text"
          autoFocus
          value={query}
          onChange={(e) => { setQuery(e.target.value); setLimit(30); }}
          placeholder={t('w4.rating.searchPlaceholder')}
          aria-label={t('w4.rating.searchAria')}
          className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-text-tertiary"
        />
        <button type="button" onClick={() => { setOpen(false); setQuery(''); }} aria-label={t('common.close')} className="fe-map-btn shrink-0">
          <X size={14} aria-hidden="true" />
        </button>
      </div>
      <ul className="fe-rank-more__list">
        {catalog.isLoading && <li className="px-3.5 py-3 text-sm text-text-secondary">{t('regions.home.loadingCatalog')}</li>}
        {!catalog.isLoading && results.length === 0 && (
          <li className="px-3.5 py-3 text-sm text-text-secondary">{t('regions.home.nothingFound', { query })}</li>
        )}
        {results.slice(0, limit).map((i) => (
          <li key={i.code}>
            <button
              type="button"
              className="fe-tap w-full px-3.5 py-2 text-left transition-colors hover:bg-surface-hover"
              onClick={() => { onPick(i.code); setOpen(false); setQuery(''); }}
            >
              <span className="block text-sm leading-snug text-text-primary">{i.name}</span>
              <span className="block text-xs text-text-secondary">{i.section}</span>
            </button>
          </li>
        ))}
        {results.length > limit && (
          <li>
            <button type="button" className="w-full px-3.5 py-3 text-left text-sm text-champagne-ink hover:bg-surface-hover" onClick={() => setLimit((n) => n + 30)}>
              {t('w6f.rank.showMoreResults', { shown: Math.min(limit, results.length), total: results.length })}
            </button>
          </li>
        )}
      </ul>
    </div>
  );
}

export default function RegionRanking({ metrics, initialCode }) {
  const { t, locale } = useLocale();
  const catalog = useRegionsCatalog();
  const [code, setCode] = useState(initialCode || metrics[0].code);
  const [dirState, setDirState] = useState({ code, value: null });
  const [expanded, setExpanded] = useState(false);
  const { data, isLoading, isError, refetch, isFetching } = useRegionsHeatmap(code);

  const total = useMemo(
    () => (catalog.data?.sections || []).reduce((n, s) => n + (s.indicators?.length || 0), 0),
    [catalog.data],
  );
  const serverSort = data?.default_sort === 'asc' ? 'asc' : 'desc';
  const direction = (dirState.code === code ? dirState.value : null) ?? serverSort;
  const achievement = Boolean(data?.rank_as_achievement);

  const ranked = useMemo(() => {
    if (!data?.values?.length) return [];
    const rows = [...data.values].sort((a, b) => {
      const av = a.raw ?? a.value;
      const bv = b.raw ?? b.value;
      return direction === 'asc' ? av - bv : bv - av;
    });
    return rows.map((row, i) => ({ ...row, rank: i + 1, num: Number(row.raw ?? row.value) }));
  }, [data, direction]);

  const maxAbs = useMemo(() => Math.max(1e-9, ...ranked.map((r) => Math.abs(r.num || 0))), [ranked]);
  const unit = data?.indicator?.unit || '';
  const isPreset = metrics.some((m) => m.code === code);
  const shown = expanded ? ranked : ranked.slice(0, FIRST_ROWS);

  const pick = (nextCode) => {
    setCode(nextCode);
    setExpanded(false);
    track(events.REGIONS_MAP_METRIC, { metric: `ranking:${nextCode}` });
  };

  return (
    <section className="fe-rank" aria-labelledby="regions-rankings-title" data-testid="region-ranking">
      <h2 id="regions-rankings-title" className="text-base font-semibold text-text-primary">
        <Link to={regionRatingHubPath()} className="fe-tap-inline hover:text-champagne-ink">
          {t('russia.link.ratings.title')}
        </Link>
      </h2>
      <p className="mt-1 max-w-2xl text-sm leading-relaxed text-text-secondary">{t('w6f.rank.lead')}</p>

      <div className="fe-chip-row--grid mt-3" role="group" aria-label={t('w6f.rank.metricAria')}>
        {metrics.map((m) => (
          <button
            key={m.code}
            type="button"
            aria-pressed={code === m.code}
            onClick={() => pick(m.code)}
            className={`fe-chip fe-press ${code === m.code ? 'is-active' : ''}`}
          >
            {t(m.labelKey)}
          </button>
        ))}
        <MoreMetrics total={total} onPick={pick} />
      </div>

      {isError && (
        <ApiRetryBanner onRetry={refetch} isFetching={isFetching} className="mt-3">
          {t('pgui.regions.ratingError')}
        </ApiRetryBanner>
      )}

      {isLoading && (
        <div className="mt-3 space-y-2" role="status" aria-busy="true" aria-label={t('common.loading')}>
          {Array.from({ length: 6 }).map((_, i) => <SkeletonBox key={i} className="h-10 w-full rounded-xl" />)}
        </div>
      )}

      {data && ranked.length > 0 && (
        <div className="mt-4">
          <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-2">
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold leading-snug text-text-primary" data-testid="ranking-active-name">
                {data.indicator.name}
              </div>
              <div className="text-xs text-text-secondary">
                {[t('w4.map.yearLabel', { year: data.year }), unitLabel(unit, locale) || unit].filter(Boolean).join(', ')}
                {!isPreset ? ` ${t('w6f.rank.chosenByYou')}` : ''}
              </div>
            </div>
            <button
              type="button"
              onClick={() => setDirState({ code, value: direction === 'asc' ? 'desc' : 'asc' })}
              className="fe-chip fe-press gap-1.5"
              aria-label={direction === 'asc' ? t('regions.rating.sortAsc') : t('regions.rating.sortDesc')}
            >
              {direction === 'asc' ? <ArrowUp size={14} aria-hidden="true" /> : <ArrowDown size={14} aria-hidden="true" />}
              {direction === 'asc' ? t('w6f.rank.lowFirst') : t('w6f.rank.highFirst')}
            </button>
          </div>

          <ol className="fe-rank__list">
            {shown.map((row) => (
              <li key={row.slug} className="fe-rank__row">
                <span className="fe-rank__place fe-num">
                  {achievement && row.rank <= 3
                    ? <span data-medal={row.rank} title={t('w6f.rank.topThree')}>{row.rank}</span>
                    : row.rank}
                </span>
                {/* Название ведёт на страницу региона, число — на этот показатель в регионе (раньше всё вело на показатель). */}
                <Link to={regionPath(row.slug)} className="fe-rank__name fe-rank__link fe-press">{row.name}</Link>
                <span className="fe-rank__bar" aria-hidden="true">
                  <span style={{ width: `${Math.max(3, (Math.abs(row.num) / maxAbs) * 100)}%` }} />
                </span>
                <Link
                  to={regionIndicatorPath(row.slug, code)}
                  title={t('c9e.rank.valueTitle')}
                  className="fe-rank__value fe-rank__link fe-num fe-press"
                >
                  {formatRegionNumber(row.num, unit, locale)}
                </Link>
              </li>
            ))}
          </ol>

          <div className="mt-3 flex flex-wrap items-center gap-3">
            {ranked.length > FIRST_ROWS && (
              <button type="button" className="fe-chip fe-press" onClick={() => setExpanded((v) => !v)}>
                {expanded ? t('w6f.rank.collapse') : t('w6f.rank.showAll', { n: ranked.length })}
              </button>
            )}
            <Link to={regionRatingPath(code)} className="fe-tap-inline text-sm font-medium text-champagne-ink hover:underline">
              {t('w6f.rank.openFull')}
            </Link>
          </div>
        </div>
      )}
    </section>
  );
}
