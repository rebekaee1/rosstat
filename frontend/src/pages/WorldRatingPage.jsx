import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowUpDown, BarChart3, Globe2, MapPinned, SlidersHorizontal, Table2, X,
} from 'lucide-react';
import { useAuth } from '../context/authContext';
import useDocumentMeta from '../lib/useMeta';
import { track, events } from '../lib/track';
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

const RATING_EXTRA_MAX_AUTH = 4;
// Гость может добавить один доп. показатель к базовому (2 колонки всего);
// полный набор до 5 показателей — после регистрации (правка 22.1).
const RATING_EXTRA_MAX_GUEST = 1;

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

function parseCountriesParam(searchParams) {
  const raw = searchParams.get('c') || '';
  if (!raw) return [];
  const seen = new Set();
  const codes = [];
  for (const part of raw.split(',')) {
    const code = part.trim().toUpperCase();
    if (!code || seen.has(code)) continue;
    seen.add(code);
    codes.push(code);
  }
  return codes;
}

function lookupExtraValue(seriesData, activeYear, row) {
  if (!seriesData || !row) return null;
  const byYear = seriesData.values_by_year || {};
  // Точный год базового показателя; если у доп. показателя этот год ещё не
  // публиковался (население — до 2025, база — 2026), берём ближайший год
  // с данными по стране, а не рисуем «—».
  const candidates = [String(activeYear), ...Object.keys(byYear).sort((a, b) => Math.abs(Number(b) - Number(activeYear)) - Math.abs(Number(a) - Number(activeYear)))];
  for (const year of candidates) {
    const yearItems = byYear[year];
    if (!yearItems) continue;
    const direct = yearItems[row.country_code];
    if (direct?.value != null) return { value: direct.value, date: direct.date };
    for (const item of Object.values(yearItems)) {
      if (!item) continue;
      if (row.country_slug && item.country_slug === row.country_slug && item.value != null) {
        return { value: item.value, date: item.date };
      }
      if (row.country_code === 'RU' && item.country_code === 'RU' && item.value != null) {
        return { value: item.value, date: item.date };
      }
    }
    break;
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

/**
 * Поиск страны внутри рейтинга: подсказки по значениям базового показателя,
 * выбор добавляет страну в фильтр/матрицу. Один компонент на фильтр-бар
 * и матрицу «Страны рядом».
 */
function CountrySuggest({ ranked, excludeCodes, onPick, placeholder }) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const q = query.trim().toLowerCase();
  const matches = ranked
    .filter((item) => !excludeCodes.has(item.country_code))
    .filter((item) => {
      if (!q) return true;
      return `${item.country_name} ${item.country_slug || ''}`.toLowerCase().includes(q);
    })
    .slice(0, 8);

  return (
    <div ref={rootRef} className="relative min-w-0">
      <label className="block">
        <span className="sr-only">{placeholder}</span>
        <input
          type="search"
          value={query}
          onChange={(event) => { setQuery(event.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          placeholder={placeholder}
          className="h-9 w-full max-w-[13rem] rounded-xl border border-border-subtle bg-obsidian-light px-3 text-xs text-text-primary outline-none transition-colors focus:border-border-champagne"
        />
      </label>
      {open && matches.length > 0 && (
        <div
          role="listbox"
          className="absolute left-0 z-30 mt-1.5 max-h-64 w-64 overflow-y-auto rounded-xl border border-border-subtle bg-surface p-1.5 shadow-lg"
        >
          {matches.map((item) => (
            <button
              key={item.country_code}
              type="button"
              role="option"
              aria-selected={false}
              onClick={() => { onPick(item); setQuery(''); setOpen(false); }}
              className="flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left text-sm text-text-primary transition-colors hover:bg-surface-hover hover:text-champagne"
            >
              <span className="min-w-0 truncate">{item.country_name}</span>
              <span className="shrink-0 font-mono text-xs tabular-nums text-text-tertiary">
                {formatWorldValue(item.value)}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
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
  const extraMax = isAuthed ? RATING_EXTRA_MAX_AUTH : RATING_EXTRA_MAX_GUEST;
  // Гость видит максимум один доп. показатель даже из URL — как GUEST_MAX на compare.
  const extraSlugs = useMemo(() => {
    const known = new Set(concepts.map((item) => item.slug));
    if (known.size === 0) return [];
    const out = [];
    const seen = new Set();
    for (const slug of rawExtraCols) {
      if (!slug || slug === activeConcept || seen.has(slug) || !known.has(slug)) continue;
      seen.add(slug);
      out.push(slug);
      if (out.length >= extraMax) break;
    }
    return out;
  }, [rawExtraCols, concepts, activeConcept, extraMax]);

  const extraSeries0 = useWorldMapSeries(extraSlugs[0]);
  const extraSeries1 = useWorldMapSeries(extraSlugs[1]);
  const extraSeries2 = useWorldMapSeries(extraSlugs[2]);
  const extraSeries3 = useWorldMapSeries(extraSlugs[3]);

  const writeExtraCols = useCallback((next) => {
    const params = new URLSearchParams(searchParams);
    if (next.length) params.set('cols', next.join(','));
    else params.delete('cols');
    setSearchParams(params, { replace: true });
  }, [searchParams, setSearchParams]);

  const addExtra = useCallback((slug) => {
    if (!slug || slug === activeConcept) return;
    if (extraSlugs.includes(slug)) return;
    if (extraSlugs.length >= extraMax) return;
    writeExtraCols([...extraSlugs, slug]);
    track(events.WORLD_RATING_COMPARE_ADD, { concept: activeConcept, added: slug, total: extraSlugs.length + 1 });
    setAddOpen(false);
  }, [activeConcept, extraSlugs, extraMax, writeExtraCols]);

  const removeExtra = useCallback((slug) => {
    writeExtraCols(extraSlugs.filter((item) => item !== slug));
  }, [extraSlugs, writeExtraCols]);

  const addableConcepts = useMemo(
    () => concepts.filter((item) => item.slug !== activeConcept && !extraSlugs.includes(item.slug)),
    [concepts, activeConcept, extraSlugs],
  );
  const atExtraMax = extraSlugs.length >= extraMax;

  // Фильтр стран (правка 22): кликабельные чипы стран в таблице рейтинга.
  const rawCountryFilter = useMemo(() => parseCountriesParam(searchParams), [searchParams]);
  const countryFilter = useMemo(
    () => rawCountryFilter.filter((code) => countriesQ.data?.countries?.some((c) => c.code === code) || code === 'RU'),
    [rawCountryFilter, countriesQ.data],
  );

  const toggleCountryFilter = useCallback((code) => {
    if (!code) return;
    const next = countryFilter.includes(code)
      ? countryFilter.filter((item) => item !== code)
      : [...countryFilter, code];
    const params = new URLSearchParams(searchParams);
    if (next.length) params.set('c', next.join(','));
    else params.delete('c');
    setSearchParams(params, { replace: true });
    track(events.WORLD_RATING_FILTER, { concept: activeConcept, action: next.includes(code) ? 'add' : 'remove', n: next.length });
  }, [countryFilter, searchParams, setSearchParams, activeConcept]);

  const clearCountryFilter = useCallback(() => {
    const params = new URLSearchParams(searchParams);
    params.delete('c');
    setSearchParams(params, { replace: true });
    track(events.WORLD_RATING_FILTER, { concept: activeConcept, action: 'clear', n: 0 });
  }, [searchParams, setSearchParams, activeConcept]);

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
    const seriesData = [extraSeries0.data, extraSeries1.data, extraSeries2.data, extraSeries3.data][index];
    return {
      slug,
      label: extraColumnLabel(slug, concepts, seriesData, t),
      seriesData,
    };
  }), [extraSlugs, concepts, extraSeries0.data, extraSeries1.data, extraSeries2.data, extraSeries3.data, t]);
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
  // Фильтр стран применяется к отображению таблицы, но не к номерам мест:
  // страна в фильтре сохраняет своё место в полном рейтинге.
  const visibleRows = useMemo(() => {
    if (!countryFilter.length) return ranked;
    const wanted = new Set(countryFilter);
    return ranked.filter((item) => wanted.has(item.country_code));
  }, [ranked, countryFilter]);
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
    extraSeries3.refetch();
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

  // Матрица «Страны рядом» (правка 22.1): строки — показатели (базовый + до
  // четырёх доп.), колонки — страны из фильтра; лучшее значение строки
  // выделено. Гость может добавить один доп. показатель, полный набор —
  // после регистрации.
  const matrixCountries = useMemo(() => {
    const wanted = new Set(countryFilter);
    if (wanted.size) return ranked.filter((item) => wanted.has(item.country_code));
    // Без явного фильтра показываем топ-4 + Россию, если она в рейтинге.
    const top = ranked.slice(0, 4);
    if (!top.some((item) => item.country_code === 'RU')) {
      const ru = ranked.find((item) => item.country_code === 'RU');
      if (ru) top.push(ru);
    }
    return top;
  }, [ranked, countryFilter]);

  const matrixRows = useMemo(() => {
    const base = {
      slug: activeConcept,
      label: shortName,
      series: mapSeriesQ.data,
      unit: concept.unit || mapSeriesQ.data?.concept?.unit || '',
    };
    const extras = extraColumns.map((col) => ({
      slug: col.slug,
      label: col.label,
      series: col.seriesData,
      unit: concepts.find((item) => item.slug === col.slug)?.unit || '',
    }));
    return [base, ...extras];
  }, [activeConcept, shortName, mapSeriesQ.data, concept.unit, extraColumns, concepts]);

  const matrixValueFor = useCallback((row, countryCode) => {
    if (!row.series) return null;
    if (row.slug === activeConcept) {
      return yearItems[countryCode]?.value ?? null;
    }
    return lookupExtraValue(row.series, activeYear, { country_code: countryCode, country_slug: countryCode.toLowerCase() })?.value ?? null;
  }, [activeConcept, activeYear, yearItems]);

  // bestByRow: код страны с «лучшим» значением строки (по направлению сортировки
  // базового концепта; для доп-строк направление то же — визуальная согласованность).
  const bestByRow = useMemo(() => {
    const out = new Map();
    for (const row of matrixRows) {
      let bestCode = null;
      let bestVal = null;
      for (const col of matrixCountries) {
        const v = matrixValueFor(row, col.country_code);
        if (v == null) continue;
        if (
          bestVal == null
          || (sortDirection === 'asc' ? v < bestVal : v > bestVal)
        ) {
          bestVal = v;
          bestCode = col.country_code;
        }
      }
      if (bestCode != null && matrixCountries.length > 1) out.set(row.slug, bestCode);
    }
    return out;
  }, [matrixRows, matrixCountries, matrixValueFor, sortDirection]);

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

          <section className="mb-5">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
                  {t('world.rating.filtersLabel')}
                </p>
                <h2 className="mt-1 font-display text-xl font-bold text-text-primary sm:text-2xl">
                  {t('world.rating.compareTitle')}
                  {activeYear ? <span className="text-text-tertiary">, {activeYear}</span> : null}
                </h2>
                <p className="mt-1 max-w-2xl text-xs leading-5 text-text-secondary">
                  {t('world.rating.compareHint')}
                </p>
              </div>
              <CountrySuggest
                ranked={ranked}
                excludeCodes={new Set(countryFilter)}
                placeholder={t('world.rating.filterSearch')}
                onPick={(item) => toggleCountryFilter(item.country_code)}
              />
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              {(countryFilter.length ? matrixCountries : ranked.slice(0, 12)).map((item) => {
                const active = countryFilter.includes(item.country_code);
                return (
                  <button
                    key={item.country_code}
                    type="button"
                    onClick={() => toggleCountryFilter(item.country_code)}
                    aria-pressed={active}
                    className={ButtonClass(active || countryFilter.includes(item.country_code))}
                    title={`${item.country_name}: ${formatWorldValue(item.value)}`}
                  >
                    {item.country_name}
                  </button>
                );
              })}
              {!countryFilter.length && (
                <span className="px-1 font-mono text-[11px] text-text-tertiary">
                  {ranked.length > 12 ? t('world.rating.matrix.more', { n: ranked.length - 12 }) : ''}
                </span>
              )}
              {countryFilter.length > 0 && (
                <button
                  type="button"
                  onClick={clearCountryFilter}
                  className="ml-1 inline-flex items-center gap-1 rounded-xl px-2.5 py-2 text-xs text-text-tertiary transition-colors hover:text-champagne"
                >
                  <X size={12} />
                  {t('world.rating.filterClear')}
                </button>
              )}
            </div>

            <div id="compare-matrix" className="mt-4 overflow-x-auto rounded-2xl border border-border-subtle bg-surface">
              <table className="w-full min-w-[40rem] text-sm">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-wide text-text-tertiary">
                    <th className="w-[16rem] px-4 py-3 font-medium">{t('world.rating.matrix.rowHeader')}</th>
                    {matrixCountries.map((col) => (
                      <th key={col.country_code} className="px-4 py-3 text-right font-medium">
                        <button
                          type="button"
                          onClick={() => openCountry(col, col)}
                          className="transition-colors hover:text-champagne"
                          title={t('world.rating.col.country')}
                        >
                          {col.country_name}
                          <span className="ml-1.5 font-mono text-[10px] normal-case text-text-tertiary">#{col.rank}</span>
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matrixRows.map((row) => (
                    <tr key={row.slug} className="border-t border-border-subtle">
                      <td className="max-w-[16rem] truncate px-4 py-3">
                        <Link
                          to={
                            row.slug === activeConcept
                              ? '#rating-table'
                              : worldRatingPath(row.slug)
                          }
                          onClick={(event) => {
                            if (row.slug === activeConcept) event.preventDefault();
                          }}
                          className="font-medium text-text-primary transition-colors hover:text-champagne"
                          title={row.label}
                        >
                          {row.label}
                        </Link>
                        {row.unit ? (
                          <span className="ml-1.5 font-mono text-[10px] text-text-tertiary">{row.unit}</span>
                        ) : null}
                      </td>
                      {matrixCountries.map((col) => {
                        const v = matrixValueFor(row, col.country_code);
                        const isBest = bestByRow.get(row.slug) === col.country_code;
                        return (
                          <td
                            key={col.country_code}
                            className={`px-4 py-3 text-right font-mono tabular-nums ${isBest ? 'font-semibold text-champagne' : 'text-text-primary'}`}
                          >
                            {v != null ? formatWorldValue(v) : '—'}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                  <tr className="border-t border-border-subtle">
                    <td className="px-4 py-2.5 text-[11px] uppercase tracking-wide text-text-tertiary">
                      {t('world.rating.matrix.periodRow')}
                    </td>
                    {matrixCountries.map((col) => (
                      <td key={col.country_code} className="px-4 py-2.5 text-right font-mono text-[11px] text-text-tertiary">
                        {yearItems[col.country_code]?.date
                          ? formatDate(yearItems[col.country_code].date, periodGranularity)
                          : '—'}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
            {!isAuthed && (
              <div className="mt-3 rounded-2xl border border-border-subtle bg-obsidian-light px-4 py-3.5">
                <p className="text-xs leading-5 text-text-secondary">{t('world.rating.matrix.guestCap')}</p>
                <div className="mt-2.5 flex flex-wrap gap-2">
                  <Link to="/register" className="rounded-xl bg-champagne px-3 py-2 text-xs font-semibold text-white hover:bg-champagne-muted">
                    {t('world.rating.register')}
                  </Link>
                  <Link to="/login" className="rounded-xl border border-border-subtle px-3 py-2 text-xs font-medium text-text-primary hover:border-champagne/40">
                    {t('world.rating.login')}
                  </Link>
                </div>
              </div>
            )}
          </section>

          <section id="rating-table" className="scroll-mt-24">
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
                {countryFilter.length > 0 && (
                  <div className="inline-flex items-center gap-2 rounded-xl bg-champagne/10 px-3 py-2 text-xs text-champagne">
                    {t('world.rating.filterShown', {
                      shown: visibleRows.length,
                      total: ranked.length,
                    })}
                  </div>
                )}
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
                    {t('world.rating.matrix.guestCap')}
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
                  {addableConcepts.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {addableConcepts.slice(0, RATING_EXTRA_MAX_GUEST).map((item) => (
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
                  {visibleRows.map((item) => (
                    <tr key={item.country_code} className="border-t border-border-subtle transition-colors hover:bg-surface-hover">
                      <td className="px-4 py-3 font-mono text-text-tertiary">{item.rank}</td>
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          onClick={() => toggleCountryFilter(item.country_code)}
                          aria-pressed={countryFilter.includes(item.country_code)}
                          title={t('world.rating.filtersLabel')}
                          className={`mr-2 hidden h-5 w-5 shrink-0 items-center justify-center rounded-md border align-middle transition-colors sm:inline-flex ${
                            countryFilter.includes(item.country_code)
                              ? 'border-champagne/60 bg-champagne/20 text-champagne'
                              : 'border-border-subtle text-text-tertiary hover:border-border-champagne hover:text-champagne'
                          }`}
                        >
                          {countryFilter.includes(item.country_code) ? '−' : '+'}
                        </button>
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
                          {formatWorldValue(lookupExtraValue(col.seriesData, activeYear, item)?.value)}
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
                  {!loading && visibleRows.length === 0 && (
                    <tr>
                      <td colSpan={colCount} className="px-4 py-8 text-center text-text-secondary">
                        {countryFilter.length
                          ? t('world.rating.filterEmpty')
                          : t('world.rating.emptyYear')}
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
