import {
  lazy, startTransition, Suspense, useEffect, useMemo, useState,
} from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import {
  HOME_PICKER_PLACEHOLDER,
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
import PlanetPlaceholder from '../PlanetPlaceholder';
import ApiRetryBanner from '../ApiRetryBanner';
import ErrorBoundary from '../ErrorBoundary';
import WorldConceptPicker from '../WorldConceptPicker';
import WorldMapConceptNote from '../WorldMapConceptNote';
import HomeHero from './HomeHero';
import { track, events } from '../../lib/track';
import { useLocale, useT } from '../../i18n';
import { readPlanetViewPreference } from '../../lib/planetViewPreference';
import '../../styles/world.css';
import '../../styles/shell.css';

// Стартовый поворот шара (если выбран шар): Евразия на русском сайте, США на английском (а не пустая Атлантика).
const HOME_START_FOCUS_RU = [52, 38];
const HOME_START_FOCUS_EN = [-96, 36];

const loadPlanetView = () => import('../PlanetView');
const PlanetView = lazy(loadPlanetView);

/**
 * Заранее качается то, что человек увидит первым. По умолчанию это плоская карта (лёгкий чанк без three): шар, его сцена и текстуры
 * не грузятся и не стартуют, пока человек сам не выбрал шар. Если выбор шара сохранён с прошлого визита, тянем сцену и дневную текстуру.
 */
function warmPlanet() {
  try {
    // Экономия трафика: ничего заранее, нужное загрузится, когда его попросят.
    if (navigator.connection?.saveData) return;
    if (readPlanetViewPreference() === 'globe') {
      import('../PlanetScene').catch(() => {});
      new Image().src = '/planet/earth_day_2048.webp';
    } else {
      import('../WorldMap').catch(() => {});
    }
  } catch { /* предзагрузка необязательна */ }
}

/** Ссылка «Поделиться видом»: ?planet=показатель:год:страна. Читается один раз при открытии страницы. */
function readSharedView() {
  try {
    const raw = new URLSearchParams(window.location.search).get('planet');
    if (!raw) return null;
    const [concept, year, country] = raw.split(':');
    return {
      concept: /^[a-z0-9-]{1,60}$/.test(concept || '') ? concept : null,
      year: /^\d{4}$/.test(year || '') ? Number(year) : null,
      country: /^[A-Za-z]{2}$/.test(country || '') ? country.toUpperCase() : '',
    };
  } catch { return null; }
}

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
    warmPlanet();
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
  const [shared] = useState(readSharedView);
  const [picked, setPicked] = useState(shared?.concept || null);
  const [mapYear, setMapYear] = useState(shared?.year || null);
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

  const benchmarkSeries = useMemo(() => (seriesPayload?.years || [])
    .map((year) => ({ year, value: seriesPayload?.benchmark_by_year?.[String(year)]?.value }))
    .filter((point) => point.value != null && Number.isFinite(Number(point.value))), [seriesPayload]);

  // Быстрая смена показателя прямо на шаре: первые показатели набора с короткими человеческими названиями.
  const quickConcepts = useMemo(() => mapConcepts.slice(0, 5).map((item) => ({
    slug: item.slug,
    label: homeConceptLabel(item.slug, t, item.name),
  })), [mapConcepts, t]);

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

  const skeleton = <PlanetPlaceholder />;
  const workbench = (
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
                : HOME_PICKER_PLACEHOLDER}
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
              skeleton
            ) : (
              <ErrorBoundary fallback={(
                <div className="flex h-[22rem] w-full flex-col items-center justify-center gap-3 rounded-2xl px-6 text-center text-sm text-text-secondary fe-glass-lite" role="alert">
                  <p>{t('home.map.loadError')}</p>
                  <button type="button" onClick={() => window.location.reload()} className="min-h-11 rounded-lg px-4 text-text-primary fe-glass-2">{t('common.retry')}</button>
                </div>
              )}
              >
              <Suspense fallback={skeleton}>
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
                  quickConcepts={quickConcepts}
                  onConceptChange={(slug) => {
                    setPicked(slug);
                    setMapYear(null);
                    track(events.HOME_COUNTRIES_METRIC, { concept: slug });
                  }}
                  shareable
                  benchmarkSeries={benchmarkSeries}
                  initialCountry={shared?.country || ''}
                  startFocus={locale === 'en' ? HOME_START_FOCUS_EN : HOME_START_FOCUS_RU}
                />
              </Suspense>
              </ErrorBoundary>
            )}
        </div>
    </section>
  );

  return <HomeHero planet={workbench} />;
}
