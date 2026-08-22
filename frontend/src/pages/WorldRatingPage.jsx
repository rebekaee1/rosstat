import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowUpDown, BarChart3, Globe2, MapPinned, SlidersHorizontal, Table2, X,
} from 'lucide-react';
import { useAuth } from '../context/authContext';
import useDocumentMeta from '../lib/useMeta';
import {
  formatWorldValue,
  pluralRu,
  useWorldCountries,
  useWorldMapSeries,
  useWorldRatingConcepts,
} from '../lib/worldApi';
import {
  conceptColorMode,
  DEFAULT_HOME_COUNTRY_CONCEPT,
  defaultSortForConcept,
  homeConceptLabel,
  resolveActiveMapYear,
  russiaDeepLinksForConcept,
  russiaNoteForConcept,
  withRussiaOnHomeMap,
  worldRankingFromYearItems,
  worldRatingTitle,
  worldYearItems,
} from '../lib/homeWorkbench';
import { formatDate } from '../lib/format';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import Breadcrumbs from '../components/Breadcrumbs';
import TelemetryCard from '../components/TelemetryCard';
import WorldConceptPicker from '../components/WorldConceptPicker';
import { useLocale, useT } from '../i18n';
import WorldMap from '../components/WorldMap';
import MapTimeline from '../components/MapTimeline';
import { worldRatingTrail } from '../lib/breadcrumbs';
import {
  countryPath,
  indicatorPath,
  worldRatingPath,
} from '../lib/sitePaths';

const RATING_EXTRA_MAX = 3;

function ButtonClass(active) {
  return [
    'rounded-xl px-3 py-2 text-xs font-medium transition-colors',
    active
      ? 'bg-champagne/15 text-champagne'
      : 'bg-obsidian-lighter text-text-secondary hover:text-champagne',
  ].join(' ');
}

function parseColsParam(searchParams) {
  const raw = searchParams.get('cols') || '';
  if (!raw) return [];
  const seen = new Set();
  const slugs = [];
  for (const part of raw.split(',')) {
    const slug = part.trim();
    if (!slug || seen.has(slug)) continue;
    seen.add(slug);
    slugs.push(slug);
  }
  return slugs;
}

function lookupExtraValue(yearItems, row) {
  if (!yearItems || !row) return null;
  const direct = yearItems[row.country_code];
  if (direct?.value != null) return direct.value;
  for (const item of Object.values(yearItems)) {
    if (!item) continue;
    if (row.country_slug && item.country_slug === row.country_slug && item.value != null) {
      return item.value;
    }
    if (row.country_code === 'RU' && item.country_code === 'RU' && item.value != null) {
      return item.value;
    }
  }
  return null;
}

function extraColumnLabel(slug, concepts, seriesData, t) {
  const fromCatalog = concepts.find((item) => item.slug === slug);
  return homeConceptLabel(
    slug,
    t,
    fromCatalog?.name || seriesData?.concept?.name || slug,
  );
}

function rowHref(item, russiaLinks) {
  if (item?.country_code === 'RU' || item?.country_slug === 'russia') {
    return russiaLinks.countryHref;
  }
  if (!item?.country_slug) return '/';
  if (item.indicator_code) {
    return indicatorPath(item.country_slug, item.indicator_code);
  }
  return countryPath(item.country_slug);
}

function pluralUnit(n, base, t, locale) {
  if (locale === 'en') {
    return n === 1 ? t(`${base}_one`) : t(`${base}_many`);
  }
  return pluralRu(n, [t(`${base}_one`), t(`${base}_few`), t(`${base}_many`)]);
}

export default function WorldRatingPage() {
  const t = useT();
  const { locale } = useLocale();
  const { isAuthed } = useAuth();
  const { conceptSlug } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const activeConcept = conceptSlug || DEFAULT_HOME_COUNTRY_CONCEPT;
  const [selectedYear, setSelectedYear] = useState(null);
  // null = пользователь ещё не трогал переключатель → берём default с сервера.
  // Нельзя писать sortDirection в useEffect от [concepts]: любой refetch каталога
  // (новый объект при том же содержимом) мгновенно откатывал бы клик.
  const [sortOverride, setSortOverride] = useState(null);
  const [addOpen, setAddOpen] = useState(false);

  const countriesQ = useWorldCountries();
  const catalogQ = useWorldRatingConcepts();
  const mapSeriesQ = useWorldMapSeries(activeConcept);

  useEffect(() => {
    if (!conceptSlug) {
      navigate(worldRatingPath(DEFAULT_HOME_COUNTRY_CONCEPT), { replace: true });
    }
  }, [conceptSlug, navigate]);

  const concepts = useMemo(
    () => (catalogQ.data?.concepts || []).map((item) => ({
      slug: item.slug,
      name: item.name,
      unit: item.unit,
      default_sort: item.default_sort,
    })),
    [catalogQ.data],
  );

  const rawExtraCols = useMemo(() => parseColsParam(searchParams), [searchParams]);
  // Гость не видит лишние колонки даже из URL — как GUEST_MAX на compare.
  const extraSlugs = useMemo(() => {
    if (!isAuthed) return [];
    const known = new Set(concepts.map((item) => item.slug));
    if (known.size === 0) return [];
    const out = [];
    const seen = new Set();
    for (const slug of rawExtraCols) {
      if (!slug || slug === activeConcept || seen.has(slug) || !known.has(slug)) continue;
      seen.add(slug);
      out.push(slug);
      if (out.length >= RATING_EXTRA_MAX) break;
    }
    return out;
  }, [isAuthed, rawExtraCols, concepts, activeConcept]);

  const extraSeries0 = useWorldMapSeries(extraSlugs[0]);
  const extraSeries1 = useWorldMapSeries(extraSlugs[1]);
  const extraSeries2 = useWorldMapSeries(extraSlugs[2]);

  const writeExtraCols = useCallback((next) => {
    const params = new URLSearchParams(searchParams);
    if (next.length) params.set('cols', next.join(','));
    else params.delete('cols');
    setSearchParams(params, { replace: true });
  }, [searchParams, setSearchParams]);

  const addExtra = useCallback((slug) => {
    if (!isAuthed || !slug || slug === activeConcept) return;
    if (extraSlugs.includes(slug)) return;
    if (extraSlugs.length >= RATING_EXTRA_MAX) return;
    writeExtraCols([...extraSlugs, slug]);
    setAddOpen(false);
  }, [isAuthed, activeConcept, extraSlugs, writeExtraCols]);

  const removeExtra = useCallback((slug) => {
    writeExtraCols(extraSlugs.filter((item) => item !== slug));
  }, [extraSlugs, writeExtraCols]);

  const addableConcepts = useMemo(
    () => concepts.filter((item) => item.slug !== activeConcept && !extraSlugs.includes(item.slug)),
    [concepts, activeConcept, extraSlugs],
  );
  const atExtraMax = extraSlugs.length >= RATING_EXTRA_MAX;

  useEffect(() => {
    setSortOverride(null);
  }, [activeConcept]);

  const sortDirection = sortOverride ?? defaultSortForConcept(activeConcept, concepts);

  const concept = useMemo(
    () => concepts.find((item) => item.slug === activeConcept)
      || mapSeriesQ.data?.concept
      || {
        slug: activeConcept,
        name: homeConceptLabel(activeConcept, t, t('world.ratingFallback')),
        unit: '',
      },
    [activeConcept, concepts, mapSeriesQ.data, t],
  );
  const knownConceptLoaded = !catalogQ.isLoading && concepts.length > 0;
  const unknownConcept = knownConceptLoaded && !concepts.some((item) => item.slug === activeConcept);
  const years = mapSeriesQ.data?.years || [];
  const activeYear = resolveActiveMapYear(years, selectedYear, mapSeriesQ.data?.values_by_year);
  const extraColumns = useMemo(() => extraSlugs.map((slug, index) => {
    const seriesData = [extraSeries0.data, extraSeries1.data, extraSeries2.data][index];
    return {
      slug,
      label: extraColumnLabel(slug, concepts, seriesData, t),
      yearItems: worldYearItems(seriesData, activeYear),
    };
  }), [extraSlugs, concepts, extraSeries0.data, extraSeries1.data, extraSeries2.data, activeYear, t]);
  const baseYearItems = useMemo(
    () => worldYearItems(mapSeriesQ.data, activeYear),
    [mapSeriesQ.data, activeYear],
  );
  const {
    countries,
    yearItems,
    russiaIndicatorCode,
  } = useMemo(
    () => withRussiaOnHomeMap({
      countries: countriesQ.data?.countries || [],
      yearItems: baseYearItems,
      mapSeries: mapSeriesQ.data,
    }),
    [countriesQ.data, baseYearItems, mapSeriesQ.data],
  );
  const russiaLinks = useMemo(
    () => russiaDeepLinksForConcept(activeConcept),
    [activeConcept],
  );
  // Messages first: API note is still RU-only while SPA locale may be EN.
  const russiaNote = russiaNoteForConcept(activeConcept, t)
    || mapSeriesQ.data?.concept?.russia?.note;
  const russiaInRanking = Boolean(yearItems.RU?.value != null);
  const valuesByCode = useMemo(
    () => new Map(Object.entries(yearItems).map(([countryCode, item]) => [countryCode, item.value])),
    [yearItems],
  );
  const detailsByCode = useMemo(
    () => new Map(Object.entries(yearItems)),
    [yearItems],
  );
  const ranked = useMemo(() => {
    const rows = worldRankingFromYearItems(
      yearItems,
      Number.MAX_SAFE_INTEGER,
      sortDirection,
    );
    return rows.map((item, index) => ({ ...item, rank: index + 1 }));
  }, [yearItems, sortDirection]);
  const withoutData = useMemo(() => {
    const withData = new Set(Object.values(yearItems).map((item) => item.country_code));
    return countries.filter((country) => !withData.has(country.code));
  }, [countries, yearItems]);

  // Единица одна на всю таблицу — уносим её в шапку колонки: иначе строка
  // повторяет «изменение за год, %» сорок один раз подряд.
  const sharedUnit = useMemo(() => {
    const units = new Set(ranked.map((item) => (item.unit || concept.unit || '').trim()));
    return units.size === 1 ? [...units][0] : null;
  }, [ranked, concept.unit]);
  const valueHeader = useMemo(() => {
    if (!sharedUnit) return t('common.value');
    if (sharedUnit.startsWith('%')) return t('world.rating.valueWithUnit', { unit: sharedUnit });
    return sharedUnit[0].toUpperCase() + sharedUnit.slice(1);
  }, [sharedUnit, t]);
  // Месячный ряд относится к месяцу целиком: «1 декабря 2025» врёт про день замера.
  const periodGranularity = useMemo(() => {
    const dates = ranked.map((item) => item.date).filter(Boolean);
    if (!dates.length) return 'day';
    if (dates.every((d) => d.endsWith('-01-01'))) return 'annual';
    if (dates.every((d) => d.slice(8) === '01')) return 'full';
    return 'day';
  }, [ranked]);

  const loading = catalogQ.isLoading || mapSeriesQ.isLoading;
  const error = catalogQ.isError || mapSeriesQ.isError;
  const retry = () => {
    countriesQ.refetch();
    catalogQ.refetch();
    mapSeriesQ.refetch();
    extraSeries0.refetch();
    extraSeries1.refetch();
    extraSeries2.refetch();
  };
  const colCount = (sharedUnit ? 4 : 5) + extraColumns.length;

  const shortName = homeConceptLabel(activeConcept, t, concept.name);
  const pageTitle = worldRatingTitle(activeConcept, concept.name || shortName, activeYear, t);
  useDocumentMeta({
    title: pageTitle,
    description: t('world.rating.metaDesc', { title: pageTitle }),
    path: worldRatingPath(activeConcept),
  });

  const openCountry = (country, detail) => {
    if (country?.code === 'RU' || country?.slug === 'russia') {
      navigate(russiaLinks.countryHref);
      return;
    }
    if (detail?.indicator_code && country?.slug) {
      navigate(indicatorPath(country.slug, detail.indicator_code));
      return;
    }
    if (country?.slug) navigate(countryPath(country.slug));
  };

  const countryWord = (n) => pluralUnit(n, 'world.unit.country', t, locale);
  const yearWord = (n) => pluralUnit(n, 'world.unit.year', t, locale);

  return (
    <div className="mx-auto w-full max-w-7xl px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs
        items={worldRatingTrail(shortName || concept.name || t('crumb.rating'), activeConcept)}
      />

      <header className="mb-4">
        <div className="mb-2 flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
          <Globe2 size={14} />
          {t('nav.worldRating')}
        </div>
        <h1 className="max-w-4xl font-display text-2xl font-bold leading-tight text-text-primary sm:text-3xl lg:text-4xl">
          {pageTitle}
        </h1>
        <p className="mt-2 max-w-3xl text-xs leading-5 text-text-secondary sm:text-sm sm:leading-6">
          {t('world.rating.intro')}
        </p>
      </header>

      {error && (
        <ApiRetryBanner onRetry={retry} retrying={countriesQ.isFetching || catalogQ.isFetching || mapSeriesQ.isFetching} className="mb-6">
          {t('world.rating.loadError')}
        </ApiRetryBanner>
      )}

      {unknownConcept && (
        <div className="mb-8 rounded-2xl border border-border-subtle bg-surface p-6">
          <h2 className="font-display text-xl font-semibold text-text-primary">{t('world.rating.notFoundTitle')}</h2>
          <p className="mt-2 text-sm text-text-secondary">
            {t('world.rating.notFoundBody')}
          </p>
          <Link to={worldRatingPath(DEFAULT_HOME_COUNTRY_CONCEPT)} className="mt-4 inline-flex rounded-xl bg-champagne px-4 py-2.5 text-sm font-semibold text-white">
            {t('world.rating.openUnemployment')}
          </Link>
        </div>
      )}

      {!unknownConcept && (
        <>
          <section className="mb-4 rounded-2xl border border-border-subtle bg-surface px-3.5 py-3 shadow-sm sm:px-4">
            <WorldConceptPicker
              concepts={concepts}
              value={activeConcept}
              mode="link"
              linkForSlug={(slug) => worldRatingPath(slug)}
              label={t('world.rating.conceptLabel')}
            />
            {loading && concepts.length === 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {[0, 1, 2].map((i) => (
                  <SkeletonBox key={i} className="h-7 w-24 rounded-xl" />
                ))}
              </div>
            )}
            <div className="mt-2.5 flex flex-wrap items-end gap-3 border-t border-border-subtle pt-2.5">
              <label className="block min-w-[8rem] flex-1 sm:max-w-[11rem]">
                <span className="mb-1 flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.16em] text-text-tertiary">
                  <SlidersHorizontal size={11} className="text-champagne" />
                  {t('common.year')}
                </span>
                <select
                  value={activeYear || ''}
                  onChange={(event) => setSelectedYear(Number(event.target.value))}
                  disabled={!years.length}
                  className="h-9 w-full rounded-xl border border-border-subtle bg-obsidian-light px-2.5 text-sm font-medium text-text-primary outline-none transition-colors focus:border-border-champagne"
                >
                  {years.map((year) => (
                    <option key={year} value={year}>{year}</option>
                  ))}
                </select>
              </label>
              <div className="min-w-0">
                <p className="mb-1 text-[10px] font-mono uppercase tracking-[0.16em] text-text-tertiary">
                  {t('world.rating.sortOrder')}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  <button type="button" className={ButtonClass(sortDirection === 'desc')} onClick={() => setSortOverride('desc')}>
                    {t('world.rating.sortDesc')}
                  </button>
                  <button type="button" className={ButtonClass(sortDirection === 'asc')} onClick={() => setSortOverride('asc')}>
                    {t('world.rating.sortAsc')}
                  </button>
                </div>
              </div>
            </div>
          </section>

          <section className="mb-5 grid gap-4 lg:grid-cols-[minmax(0,1.55fr)_minmax(min(100%,24rem),0.85fr)]">
            <div className="rounded-[1.5rem] border border-border-subtle bg-surface p-3 shadow-[0_16px_45px_rgba(35,30,16,0.05)] sm:p-5">
              {mapSeriesQ.isLoading ? (
                <SkeletonBox className="aspect-[2/1] w-full rounded-2xl" />
              ) : (
                <>
                  <WorldMap
                    countries={countries}
                    valuesByCode={valuesByCode}
                    detailsByCode={detailsByCode}
                    unit={concept.unit || mapSeriesQ.data?.concept?.unit || ''}
                    metricName={shortName}
                    periodLabel={activeYear ? String(activeYear) : ''}
                    colorMode={conceptColorMode(activeConcept)}
                    defaultScope="world"
                    onSelect={openCountry}
                  />
                  {years.length > 1 && activeYear && (
                    <MapTimeline
                      years={years}
                      year={activeYear}
                      onYearChange={setSelectedYear}
                      metric={`world-rating:${activeConcept}`}
                    />
                  )}
                </>
              )}
            </div>

            <aside className="rounded-[1.5rem] border border-border-subtle bg-surface p-5">
              <div className="mb-4 flex items-start gap-3">
                <BarChart3 size={18} className="mt-1 shrink-0 text-champagne" />
                <div>
                  <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-tertiary">{t('world.rating.summary')}</p>
                  <h2 className="mt-1 font-display text-xl font-semibold text-text-primary">
                    {shortName}{activeYear ? `, ${activeYear}` : ''}
                  </h2>
                </div>
              </div>
              <p className="text-sm leading-6 text-text-secondary">
                {t('world.rating.summaryBody', {
                  ranked: ranked.length,
                  countryWord: countryWord(ranked.length),
                  total: countries.length,
                })}
                {russiaInRanking
                  ? t('world.rating.summaryRussiaIn')
                  : t('world.rating.summaryRussiaOut')}
              </p>
              <div className="mt-4 rounded-xl bg-obsidian-light px-3.5 py-3 text-xs leading-5 text-text-secondary">
                {activeConcept === 'hicp-index' || mapSeriesQ.data?.concept?.value_mode === 'yoy'
                  ? t('world.rating.noteYoy')
                  : t('world.rating.noteDefault')}
              </div>
              {russiaNote && (
                <div className="mt-3 rounded-xl border border-border-subtle bg-white/60 px-3.5 py-3 text-xs leading-5 text-text-secondary">
                  {russiaNote}
                </div>
              )}
              <div className="mt-4 space-y-2 border-t border-border-subtle pt-4">
                <p className="text-[10px] font-mono uppercase tracking-[0.16em] text-text-tertiary">
                  {t('world.rating.russiaRegions')}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Link
                    to={russiaLinks.countryHref}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-champagne/15 px-3 py-2 text-xs font-medium text-champagne"
                  >
                    <Globe2 size={13} />
                    {russiaIndicatorCode
                      ? t('world.rating.russiaIndicator')
                      : t('world.rating.russiaSection')}
                  </Link>
                  <Link
                    to={russiaLinks.regionsHref}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-obsidian-lighter px-3 py-2 text-xs font-medium text-text-secondary hover:text-champagne"
                  >
                    <MapPinned size={13} />
                    {t('world.rating.russiaRegionsLink')}
                  </Link>
                  {russiaLinks.regionRatingHref && (
                    <Link
                      to={russiaLinks.regionRatingHref}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-obsidian-lighter px-3 py-2 text-xs font-medium text-text-secondary hover:text-champagne"
                    >
                      {t('world.rating.regionRatingLink')}
                    </Link>
                  )}
                </div>
              </div>
            </aside>
          </section>

          <section className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4 md:gap-4">
            <TelemetryCard
              label={t('world.rating.telemetry.withData')}
              value={ranked.length}
              unit={countryWord(ranked.length)}
              valueDigits={0}
              meta={activeYear ? t('world.rating.telemetry.metaYear', { year: activeYear }) : undefined}
              delay={0}
            />
            <TelemetryCard
              label={t('world.rating.telemetry.withoutData')}
              value={withoutData.length}
              unit={countryWord(withoutData.length)}
              valueDigits={0}
              meta={t('world.rating.telemetry.metaSelectedYear')}
              delay={1}
            />
            <TelemetryCard
              label={t('world.rating.telemetry.totalCountries')}
              value={countries.length}
              unit={countryWord(countries.length)}
              valueDigits={0}
              meta={t('world.rating.telemetry.metaCatalog')}
              delay={2}
            />
            <TelemetryCard
              label={t('world.rating.telemetry.yearsAvailable')}
              value={years.length}
              unit={yearWord(years.length)}
              valueDigits={0}
              meta={years.length ? `${years[0]}–${years[years.length - 1]}` : undefined}
              delay={3}
            />
          </section>

          <section className="mb-8">
            <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
                  {t('world.rating.fullTable')}
                </p>
                <h2 className="mt-1 font-display text-2xl font-bold text-text-primary">
                  {t('world.rating.allWithData', { n: ranked.length })}
                </h2>
              </div>
              <div className="flex flex-wrap items-end gap-2">
                <div className="inline-flex items-center gap-2 rounded-xl bg-obsidian-light px-3 py-2 text-xs text-text-secondary">
                  <ArrowUpDown size={14} className="text-champagne" />
                  {sortDirection === 'desc'
                    ? t('world.rating.sortDescHint')
                    : t('world.rating.sortAscHint')}
                </div>
              </div>
            </div>
            <div className="mb-3">
              <p className="mb-1.5 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
                {t('world.rating.addColumnHint')}
              </p>
              <button
                type="button"
                className={ButtonClass(addOpen)}
                onClick={() => setAddOpen((prev) => !prev)}
              >
                {t('world.rating.addColumn')}
              </button>
              {addOpen && !isAuthed && (
                <div className="mt-3 max-w-lg rounded-2xl border border-border-subtle bg-obsidian-light px-4 py-3.5">
                  <h3 className="text-sm font-semibold text-text-primary">
                    {t('world.rating.extraGuestTitle')}
                  </h3>
                  <p className="mt-1.5 text-xs leading-5 text-text-secondary">
                    {t('world.rating.extraGuestBody')}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Link
                      to="/register"
                      className="rounded-xl bg-champagne px-3 py-2 text-xs font-semibold text-white hover:bg-champagne-muted"
                    >
                      {t('world.rating.register')}
                    </Link>
                    <Link
                      to="/login"
                      className="rounded-xl border border-border-subtle px-3 py-2 text-xs font-medium text-text-primary hover:border-champagne/40"
                    >
                      {t('world.rating.login')}
                    </Link>
                  </div>
                </div>
              )}
              {addOpen && isAuthed && (
                <div className="mt-3 max-w-lg rounded-2xl border border-border-subtle bg-obsidian-light px-4 py-3.5">
                  {atExtraMax ? (
                    <p className="text-xs leading-5 text-text-secondary">
                      {t('world.rating.extraMax')}
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-1.5">
                      {addableConcepts.map((item) => (
                        <button
                          key={item.slug}
                          type="button"
                          className={ButtonClass(false)}
                          onClick={() => addExtra(item.slug)}
                        >
                          {homeConceptLabel(item.slug, t, item.name)}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="overflow-x-auto rounded-2xl border border-border-subtle bg-surface">
              <table className="w-full min-w-[52rem] text-sm">
                <thead className="sticky top-0 z-10 bg-obsidian-light/95 backdrop-blur-sm">
                  <tr className="text-left text-[11px] uppercase tracking-wide text-text-tertiary">
                    <th className="w-20 px-4 py-3 font-medium">{t('world.rating.col.rank')}</th>
                    <th className="px-4 py-3 font-medium">{t('world.rating.col.country')}</th>
                    <th className="px-4 py-3 text-right font-medium">{valueHeader}</th>
                    {extraColumns.map((col) => (
                      <th key={col.slug} className="px-4 py-3 text-right font-medium">
                        <span className="inline-flex items-center justify-end gap-1.5">
                          {col.label}
                          <button
                            type="button"
                            className="rounded-lg p-0.5 text-text-tertiary hover:text-champagne"
                            aria-label={t('world.rating.extraRemove')}
                            onClick={() => removeExtra(col.slug)}
                          >
                            <X size={12} />
                          </button>
                        </span>
                      </th>
                    ))}
                    {!sharedUnit && <th className="px-4 py-3 font-medium">{t('world.rating.col.unit')}</th>}
                    <th className="px-4 py-3 font-medium">{t('common.period')}</th>
                  </tr>
                </thead>
                <tbody>
                  {ranked.map((item) => (
                    <tr key={item.country_code} className="border-t border-border-subtle transition-colors hover:bg-surface-hover">
                      <td className="px-4 py-3 font-mono text-text-tertiary">{item.rank}</td>
                      <td className="px-4 py-3">
                        <Link to={rowHref(item, russiaLinks)} className="font-medium text-text-primary transition-colors hover:text-champagne">
                          {item.country_name}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-semibold tabular-nums text-text-primary">
                        {formatWorldValue(item.value)}
                      </td>
                      {extraColumns.map((col) => (
                        <td
                          key={col.slug}
                          className="px-4 py-3 text-right font-mono tabular-nums text-text-primary"
                        >
                          {formatWorldValue(lookupExtraValue(col.yearItems, item))}
                        </td>
                      ))}
                      {!sharedUnit && (
                        <td className="px-4 py-3 text-xs text-text-secondary">
                          {item.unit || concept.unit || t('world.rating.fallbackUnit')}
                        </td>
                      )}
                      <td className="px-4 py-3 font-mono text-xs text-text-tertiary">
                        {item.date ? formatDate(item.date, periodGranularity) : '—'}
                      </td>
                    </tr>
                  ))}
                  {!loading && ranked.length === 0 && (
                    <tr>
                      <td colSpan={colCount} className="px-4 py-8 text-center text-text-secondary">
                        {t('world.rating.emptyYear')}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-[1.5rem] border border-border-subtle bg-surface p-5">
            <div className="mb-3 flex items-center gap-2">
              <Table2 size={17} className="text-champagne" />
              <h2 className="font-display text-xl font-semibold text-text-primary">
                {t('world.rating.withoutDataTitle', {
                  year: activeYear || t('world.rating.selectedYear'),
                  n: withoutData.length,
                })}
              </h2>
            </div>
            {withoutData.length > 0 ? (
              <div className="flex max-h-48 flex-wrap gap-2 overflow-y-auto pr-1">
                {withoutData.map((country) => (
                  <Link
                    key={country.slug}
                    to={country.code === 'RU' ? russiaLinks.countryHref : countryPath(country.slug)}
                    className="rounded-xl bg-obsidian-light px-3 py-2 text-xs text-text-secondary transition-colors hover:text-champagne"
                  >
                    {country.name}
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-sm text-text-secondary">
                {t('world.rating.allHaveData')}
              </p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
