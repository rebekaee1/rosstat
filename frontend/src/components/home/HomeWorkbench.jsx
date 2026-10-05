import {
  lazy, startTransition, Suspense, useEffect, useMemo, useState,
} from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import {
  conceptColorMode,
  countryPublicName,
  defaultSortForConcept,
  homeConceptLabel,
  homeMapConcepts,
  mapSelectHref,
  resolveActiveMapYear,
  resolveHomeConcept,
  resolveHomeMapSeries,
  withRussiaOnHomeMap,
  worldRankingFromYearItems,
  worldYearItems,
} from '../../lib/homeWorkbench';
import {
  localizeWorldUnit,
  ratingHref,
  useWorldCountries,
  useWorldCompareSnapshot,
  useWorldMapSeries,
} from '../../lib/worldApi';
import { SkeletonBox } from '../Skeleton';
import ApiRetryBanner from '../ApiRetryBanner';
import ErrorBoundary from '../ErrorBoundary';
import WorldConceptPicker from '../WorldConceptPicker';
import WorldMapConceptNote from '../WorldMapConceptNote';
import HomeHero from './HomeHero';
import { track, events } from '../../lib/track';
import { useLocale, useT } from '../../i18n';
import '../../styles/world.css';
import '../../styles/shell.css';

const loadPlanetView = () => import('../PlanetView');
const PlanetView = lazy(loadPlanetView);

/**
 * true после первого кадра: планета монтируется
 * низкоприоритетным transition уже после первой отрисовки hero/поиска,
 * чтобы не удлинять первую длинную задачу. Чанк интерфейса начинает
 * качаться сразу; плейсхолдер резервирует место под сцену и карточку.
 */
function useAfterFirstPaint() {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    loadPlanetView().catch(() => {});
    let timer = null;
    const raf = typeof window.requestAnimationFrame === 'function'
      ? window.requestAnimationFrame(() => {
        timer = window.setTimeout(() => startTransition(() => setReady(true)), 0);
      })
      : null;
    if (raf == null) timer = window.setTimeout(() => startTransition(() => setReady(true)), 0);
    return () => {
      if (raf != null && typeof window.cancelAnimationFrame === 'function') window.cancelAnimationFrame(raf);
      if (timer != null) window.clearTimeout(timer);
    };
  }, []);
  return ready;
}

/**
 * Главная: intro и scope сверху; ниже выбор показателя и единая планета
 * с поиском, годом, списком стран и карточкой выбранного наблюдения.
 */
export default function HomeWorkbench({ ratingConcepts }) {
  const t = useT();
  const { locale } = useLocale();
  const navigate = useNavigate();
  const [picked, setPicked] = useState(null);
  const [mapYear, setMapYear] = useState(null);
  const mapMounted = useAfterFirstPaint();

  const countriesQ = useWorldCountries();
  const mapConcepts = useMemo(
    () => homeMapConcepts(ratingConcepts?.data?.concepts || []),
    [ratingConcepts?.data],
  );
  const concept = resolveHomeConcept(ratingConcepts?.data?.concepts || [], picked || undefined);
  const snapshot = useWorldCompareSnapshot(concept);
  const mapSeries = useWorldMapSeries(concept);
  const seriesPayload = resolveHomeMapSeries(mapSeries.data, snapshot.data);
  const mapDataPending = !seriesPayload
    && (mapSeries.isLoading || snapshot.isLoading)
    && !(mapSeries.isError && snapshot.isError);
  const fullRatingHref = ratingHref(concept, ratingConcepts?.data?.concepts);

  const years = seriesPayload?.years || [];
  const activeYear = resolveActiveMapYear(years, mapYear, seriesPayload?.values_by_year);
  const baseYearItems = useMemo(
    () => worldYearItems(seriesPayload, activeYear),
    [seriesPayload, activeYear],
  );

  const { countries, yearItems, russiaIndicatorCode } = useMemo(
    () => withRussiaOnHomeMap({
      countries: countriesQ.data?.countries || [],
      yearItems: baseYearItems,
      mapSeries: seriesPayload,
    }),
    [countriesQ.data, baseYearItems, seriesPayload],
  );

  const mapCountries = useMemo(
    () => countries.map((country) => ({
      ...country,
      name: countryPublicName(country, locale),
    })),
    [countries, locale],
  );
  const sortDirection = defaultSortForConcept(concept, ratingConcepts?.data?.concepts);
  const ranking = useMemo(
    () => worldRankingFromYearItems(yearItems, Number.MAX_SAFE_INTEGER, sortDirection),
    [yearItems, sortDirection],
  );
  const conceptUnit = localizeWorldUnit(
    seriesPayload?.concept?.unit || '',
    locale,
  );
  const conceptName = homeConceptLabel(
    concept,
    t,
    seriesPayload?.concept?.name || t('home.map.metricFallback'),
  );
  const valuesByCode = useMemo(
    () => new Map(Object.entries(yearItems).map(([code, item]) => [code, item.value])),
    [yearItems],
  );
  const detailsByCode = useMemo(() => new Map(Object.entries(yearItems)), [yearItems]);
  const benchmark = activeYear
    ? seriesPayload?.benchmark_by_year?.[String(activeYear)]
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
    <>
      <HomeHero />

      <section
        data-block="home-workbench"
        className="relative z-10 mb-10 md:mb-12"
        aria-labelledby="home-world-map-title"
      >
        <div
          data-block="home-map-controls"
          className="mb-3 min-w-0"
        >
          <h2 id="home-world-map-title" className="text-base font-semibold text-text-primary">
            {t('home.map.title')}
          </h2>
          <div className="mt-2 min-w-0">
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
              mobileScroll
              trailing={<WorldMapConceptNote conceptSlug={concept} />}
              hint={fullRatingHref ? (
                <Link
                  to={fullRatingHref}
                  onClick={() => track(events.HOME_COUNTRIES_CTA, { target: 'rating-hint', concept })}
                  className="inline-flex min-h-8 items-center gap-1 text-xs text-text-secondary transition-colors hover:text-champagne-ink pointer-coarse:-my-1.5 pointer-coarse:min-h-11"
                >
                  {t('home.map.moreMetrics')}
                  <ArrowRight size={12} aria-hidden="true" />
                </Link>
              ) : null}
            />
          </div>
        </div>

        {(mapSeries.isError && snapshot.isError) && (
          <ApiRetryBanner
            className="mb-4"
            onRetry={() => {
              countriesQ.refetch();
              snapshot.refetch();
              mapSeries.refetch();
            }}
            isFetching={countriesQ.isFetching || snapshot.isFetching || mapSeries.isFetching}
          >
            {t('home.map.loadError')}
          </ApiRetryBanner>
        )}

        <div className="relative min-w-0">
            {!mapMounted || mapDataPending ? (
              <SkeletonBox className="h-[58rem] w-full rounded-2xl sm:h-[39rem]" />
            ) : (
              <ErrorBoundary fallback={(
                <div className="flex h-[22rem] w-full flex-col items-center justify-center gap-3 rounded-2xl border border-border-subtle bg-surface-hover px-6 text-center text-sm text-text-secondary" role="alert">
                  <p>{t('home.map.loadError')}</p>
                  <button type="button" onClick={() => window.location.reload()} className="min-h-11 rounded-lg border border-border-subtle bg-surface px-4 text-text-primary">{t('common.retry')}</button>
                </div>
              )}
              >
              <Suspense fallback={<SkeletonBox className="h-[58rem] w-full rounded-2xl sm:h-[39rem]" />}>
                <PlanetView
                  countries={mapCountries}
                  valuesByCode={valuesByCode}
                  detailsByCode={detailsByCode}
                  unit={conceptUnit}
                  metricName={conceptName}
                  periodLabel={activeYear ? String(activeYear) : ''}
                  colorMode={conceptColorMode(concept)}
                  colorDirection={sortDirection}
                  defaultScope="world"
                  years={years}
                  year={activeYear}
                  onYearChange={setMapYear}
                  conceptSlug={concept}
                  rankingItems={ranking}
                  benchmark={benchmark}
                  ratingHref={fullRatingHref && activeYear ? `${fullRatingHref}?year=${activeYear}` : fullRatingHref}
                  onSelect={onSelectCountry}
                />
              </Suspense>
              </ErrorBoundary>
            )}
        </div>
      </section>
    </>
  );
}
