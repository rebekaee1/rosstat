import { lazy, Suspense, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import {
  HOME_RATING_LIMIT,
  conceptColorMode,
  defaultSortForConcept,
  homeConceptLabel,
  homeMapConcepts,
  mapSelectHref,
  resolveActiveMapYear,
  resolveHomeConcept,
  withRussiaOnHomeMap,
  worldRankingFromYearItems,
  worldYearItems,
} from '../../lib/homeWorkbench';
import {
  formatWorldValue,
  ratingHref,
  useWorldCountries,
  useWorldMapSeries,
} from '../../lib/worldApi';
import { SkeletonBox } from '../Skeleton';
import ApiRetryBanner from '../ApiRetryBanner';
import WorldConceptPicker from '../WorldConceptPicker';
import WorldMapConceptNote from '../WorldMapConceptNote';
import { track, events } from '../../lib/track';
import { useT } from '../../i18n';

const WorldMap = lazy(() => import('../WorldMap'));
const MapTimeline = lazy(() => import('../MapTimeline'));

/**
 * Главная: карта мира и рейтинг стран по выбранному показателю.
 * Россия накладывается поверх world API (её нет в Eurostat-plane).
 */
export default function HomeWorkbench({ ratingConcepts }) {
  const t = useT();
  const navigate = useNavigate();
  const [picked, setPicked] = useState(null);
  const [mapYear, setMapYear] = useState(null);

  const countriesQ = useWorldCountries();
  const mapConcepts = useMemo(
    () => homeMapConcepts(ratingConcepts?.data?.concepts || []),
    [ratingConcepts?.data],
  );
  const concept = resolveHomeConcept(ratingConcepts?.data?.concepts || [], picked || undefined);
  const mapSeries = useWorldMapSeries(concept);
  const fullRatingHref = ratingHref(concept, ratingConcepts?.data?.concepts);

  const years = mapSeries.data?.years || [];
  const activeYear = resolveActiveMapYear(years, mapYear, mapSeries.data?.values_by_year);
  const baseYearItems = useMemo(
    () => worldYearItems(mapSeries.data, activeYear),
    [mapSeries.data, activeYear],
  );

  const { countries, yearItems, russiaIndicatorCode } = useMemo(
    () => withRussiaOnHomeMap({
      countries: countriesQ.data?.countries || [],
      yearItems: baseYearItems,
      mapSeries: mapSeries.data,
    }),
    [countriesQ.data, baseYearItems, mapSeries.data],
  );

  // Порядок берём тот же, что и полный рейтинг: у безработицы и доходностей
  // «первое место» — минимум, а не максимум.
  const sortDirection = defaultSortForConcept(concept, ratingConcepts?.data?.concepts);
  const ranking = useMemo(
    () => worldRankingFromYearItems(yearItems, HOME_RATING_LIMIT, sortDirection),
    [yearItems, sortDirection],
  );
  const conceptUnit = mapSeries.data?.concept?.unit || '';
  const conceptName = homeConceptLabel(
    concept,
    t,
    mapSeries.data?.concept?.name || t('home.map.metricFallback'),
  );
  const valuesByCode = useMemo(
    () => new Map(Object.entries(yearItems).map(([code, item]) => [code, item.value])),
    [yearItems],
  );
  const detailsByCode = useMemo(() => new Map(Object.entries(yearItems)), [yearItems]);
  const benchmark = activeYear
    ? mapSeries.data?.benchmark_by_year?.[String(activeYear)]
    : null;

  const onSelectCountry = (country, detail) => {
    track(events.HOME_COUNTRIES_MAP_SELECT, {
      code: country?.code,
      concept,
      year: activeYear,
    });
    const href = mapSelectHref(country, detail, {
      conceptSlug: concept,
      russiaIndicatorCode,
    });
    if (href) navigate(href);
  };

  return (
    <section
      data-block="home-workbench"
      className="relative z-10 mb-10 md:mb-12 lg:-mt-28 xl:-mt-32"
      aria-labelledby="home-world-map-title"
    >
      {/* Заголовок и пикер — под поиском слева; справа уходят под scope-карточку. */}
      <div className="relative z-10 mb-3 min-w-0 lg:max-w-[calc(100%-min(22rem,38%))]">
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
          {t('home.map.eyebrow')}
        </div>
        <h2 id="home-world-map-title" className="mt-1 text-base font-semibold text-text-primary sm:text-lg">
          {t('home.map.title')}
        </h2>
      </div>

      <div className="relative z-10 mb-4 min-w-0 lg:max-w-[calc(100%-min(22rem,38%))]">
        <WorldConceptPicker
          concepts={mapConcepts.length
            ? mapConcepts
            : [{ slug: concept, name: conceptName }]}
          value={concept}
          onChange={(slug) => {
            setPicked(slug);
            setMapYear(null);
            track(events.HOME_COUNTRIES_METRIC, { concept: slug });
          }}
          label={t('home.map.metricLabel')}
          searchable={false}
          trailing={<WorldMapConceptNote conceptSlug={concept} />}
          hint={fullRatingHref ? (
            <Link
              to={fullRatingHref}
              onClick={() => track(events.HOME_COUNTRIES_CTA, { target: 'rating-hint', concept })}
              className="inline-flex items-center gap-1 text-[11px] text-text-tertiary transition-colors hover:text-champagne"
            >
              {t('home.map.moreMetrics')}
              <ArrowRight size={11} />
            </Link>
          ) : null}
        />
      </div>

      {(countriesQ.isError || mapSeries.isError) && (
        <ApiRetryBanner
          className="mb-4"
          onRetry={() => {
            countriesQ.refetch();
            mapSeries.refetch();
          }}
          isFetching={countriesQ.isFetching || mapSeries.isFetching}
        >
          {t('home.map.loadError')}
        </ApiRetryBanner>
      )}

      {/* Карта задаёт высоту; рейтинг на lg абсолютен по её кромкам — без хвостов. */}
      <div className="relative">
        <div className="min-w-0 overflow-hidden rounded-2xl border border-border-subtle bg-surface p-2.5 sm:p-4 lg:ml-[calc(18rem+1.25rem)]">
          {(countriesQ.isLoading || mapSeries.isLoading) ? (
            <SkeletonBox className="h-[18rem] w-full rounded-2xl sm:h-[30rem]" />
          ) : (
            <Suspense fallback={<SkeletonBox className="h-[18rem] w-full rounded-2xl sm:h-[30rem]" />}>
              <WorldMap
                countries={countries}
                valuesByCode={valuesByCode}
                detailsByCode={detailsByCode}
                unit={conceptUnit}
                metricName={conceptName}
                periodLabel={activeYear ? String(activeYear) : ''}
                colorMode={conceptColorMode(concept)}
                colorDirection={sortDirection}
                defaultScope="world"
                onSelect={onSelectCountry}
              />
              {years.length > 1 && activeYear != null && (
                <div className="mt-3 px-0.5 sm:mt-4 sm:px-1">
                  <MapTimeline
                    years={years}
                    year={activeYear}
                    onYearChange={setMapYear}
                    metric={`home-world:${concept}`}
                  />
                </div>
              )}
            </Suspense>
          )}
        </div>

        <div className="mt-4 flex max-h-none min-h-0 min-w-0 flex-col overflow-hidden rounded-2xl border border-border-subtle bg-obsidian-light/40 px-3.5 py-3 lg:absolute lg:inset-y-0 lg:left-0 lg:mt-0 lg:w-[18rem]">
          <div className="shrink-0 text-[10px] font-mono uppercase tracking-[0.16em] text-champagne">
            {t('home.map.rating')}
          </div>
          <div className="mt-1 shrink-0 text-xs font-semibold text-text-primary">
            {conceptName}
          </div>
          <div className="mt-0.5 flex shrink-0 flex-wrap items-baseline gap-x-2 gap-y-0.5 font-mono text-[10px] text-text-tertiary">
            {activeYear != null && <span>{t('world.yearLabel', { year: activeYear })}</span>}
            {conceptUnit ? <span>{conceptUnit}</span> : null}
            <span>
              {sortDirection === 'asc'
                ? t('world.rating.sortAscHint')
                : t('world.rating.sortDescHint')}
            </span>
          </div>
          {benchmark?.value != null && (
            <div className="mt-2 shrink-0 rounded-lg bg-champagne/[0.08] px-2.5 py-1.5">
              <div className="text-[10px] text-text-tertiary">{benchmark.label}</div>
              <div className="font-mono text-sm font-semibold text-text-primary">
                {formatWorldValue(benchmark.value)}
              </div>
            </div>
          )}
          <ol className="mt-2 min-h-0 flex-1 space-y-0.5 overflow-y-auto overscroll-contain">
            {ranking.length === 0 && (
              <li className="text-[11px] text-text-tertiary">{t('home.map.noDataYear')}</li>
            )}
            {ranking.map((item, idx) => (
              <li key={item.country_code || item.country_slug || idx}>
                <button
                  type="button"
                  onClick={() => onSelectCountry(
                    {
                      code: item.country_code,
                      slug: item.country_slug,
                      name: item.country_name,
                    },
                    item,
                  )}
                  className="grid w-full grid-cols-[1.15rem_minmax(0,1fr)_auto] items-baseline gap-1 rounded-lg px-0.5 py-0.5 text-left hover:bg-champagne/10"
                >
                  <span className="font-mono text-[11px] text-text-tertiary">{idx + 1}.</span>
                  <span className="min-w-0 truncate text-[11px] leading-snug text-text-secondary">
                    {item.country_name}
                  </span>
                  <span className="font-mono text-[11px] font-semibold tabular-nums text-text-primary">
                    {formatWorldValue(item.value)}
                  </span>
                </button>
              </li>
            ))}
          </ol>
          {fullRatingHref && (
            <Link
              to={fullRatingHref}
              onClick={() => track(events.HOME_COUNTRIES_CTA, { target: 'rating', concept })}
              className="mt-3 inline-flex shrink-0 items-center gap-1 text-[11px] font-medium text-champagne hover:underline"
            >
              {t('home.map.fullRating')}
              <ArrowRight size={12} />
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}
