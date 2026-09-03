import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Link, useLocation, useNavigate, useParams, useSearchParams,
} from 'react-router-dom';
import {
  ArrowDown, ArrowUp, ArrowUpDown, BarChart3, ChevronLeft, ChevronRight, Globe2,
  MapPinned, SlidersHorizontal, Table2, X,
} from 'lucide-react';
import { useAuth } from '../context/authContext';
import useDocumentMeta from '../lib/useMeta';
import { track, events } from '../lib/track';
import {
  formatWorldValue,
  localizeWorldUnit,
  pluralRu,
  useWorldCountries,
  useWorldMapSeries,
  useWorldRatingConcepts,
} from '../lib/worldApi';
import {
  conceptColorMode,
  countryPublicName,
  defaultSortForConcept,
  homeConceptLabel,
  mapSelectHref,
  resolveActiveMapYear,
  russiaDeepLinksForConcept,
  withRussiaOnHomeMap,
  worldRankingFromYearItems,
  worldRatingTitle,
  worldYearItems,
} from '../lib/homeWorkbench';
import { formatDate } from '../lib/format';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import Breadcrumbs from '../components/Breadcrumbs';
import WorldConceptPicker from '../components/WorldConceptPicker';
import WorldMapConceptNote from '../components/WorldMapConceptNote';
import { useLocale, useT } from '../i18n';
import WorldMap from '../components/WorldMap';
import MapTimeline from '../components/MapTimeline';
import { worldRatingTrail } from '../lib/breadcrumbs';
import {
  countryPath,
  WORLD_RATING_DEFAULT_CONCEPT,
  worldRatingPath,
} from '../lib/sitePaths';

const RATING_EXTRA_MAX_AUTH = 4;
// Гость может открыть один доп. показатель из URL (2 колонки всего);
// полный набор до 5 показателей — после регистрации (правка 22.1).
const RATING_EXTRA_MAX_GUEST = 1;

/** Спец-код базовой колонки «Значение» в сортировке по заголовкам. */
const SORT_BASE_COLUMN = '__base__';

function ButtonClass(active) {
  return [
    'rounded-xl px-3 py-2 text-xs font-medium transition-colors',
    active
      ? 'bg-champagne/15 text-champagne'
      : 'bg-obsidian-lighter text-text-secondary hover:text-champagne',
  ].join(' ');
}

/**
 * Шапка сортируемой колонки: подпись со стрелкой направления.
 * Нейтральное состояние (↕) означает «применён смысловой порядок показателя»;
 * первый клик фиксирует этот порядок, второй разворачивает.
 */
function SortableTh({
  label, active, dir, onClick, onRemove = null, right = true, minWidth = false,
}) {
  const Icon = active ? (dir === 'asc' ? ArrowUp : ArrowDown) : ArrowUpDown;
  const ariaSort = active ? (dir === 'asc' ? 'ascending' : 'descending') : undefined;
  return (
    <th
      aria-sort={ariaSort}
      className={[
        'px-4 py-3 font-medium',
        right ? 'text-right' : '',
        minWidth ? 'min-w-[12rem]' : '',
      ].join(' ')}
    >
      <span className="inline-flex max-w-full items-center justify-end gap-1">
        <button
          type="button"
          onClick={onClick}
          aria-label={typeof label === 'string' ? label : undefined}
          className={[
            'inline-flex min-w-0 items-center gap-1 rounded-lg transition-colors hover:text-champagne',
            active ? 'text-champagne' : '',
          ].join(' ')}
        >
          <span className="min-w-0 truncate">{label}</span>
          <Icon size={12} aria-hidden="true" />
        </button>
        {onRemove && (
          <button
            type="button"
            className="shrink-0 rounded-lg p-0.5 text-text-tertiary transition-colors hover:text-champagne"
            aria-label={onRemove.label}
            onClick={onRemove.onClick}
          >
            <X size={12} aria-hidden="true" />
          </button>
        )}
      </span>
    </th>
  );
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

function rowHref(item, { conceptSlug, russiaIndicatorCode } = {}) {
  return mapSelectHref(
    {
      code: item?.country_code,
      slug: item?.country_slug,
    },
    { indicator_code: item?.indicator_code },
    { conceptSlug, russiaIndicatorCode },
  ) || '/';
}

function pluralUnit(n, base, t, locale) {
  if (locale === 'en') {
    return n === 1 ? t(`${base}_one`) : t(`${base}_many`);
  }
  return pluralRu(n, [t(`${base}_one`), t(`${base}_few`), t(`${base}_many`)]);
}

/** Горизонтальный сдвиг шкалы карты при 5+ колонках: колонки 0-4 — без сдвига. */
const TABLE_SHIFT_BY_COLUMN_COUNT = [0, 0, 0, 1, 1, 2];

export default function WorldRatingPage() {
  const t = useT();
  const { locale } = useLocale();
  const { isAuthed } = useAuth();
  const { conceptSlug } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { hash, search } = useLocation();
  const activeConcept = conceptSlug || WORLD_RATING_DEFAULT_CONCEPT;
  const [selectedYear, setSelectedYear] = useState(null);
  // Активная колонка сортировки: { slug, dir } | null. null = пользователь ещё
  // не трогал переключатель → применяется смысловой порядок (лучшие сверху).
  // Любой refetch каталога не должен откатывать клик, поэтому запись идёт
  // только из обработчика клика и сброса при смене концепта.
  const [sortOverride, setSortOverride] = useState(null);

  const countriesQ = useWorldCountries();
  const catalogQ = useWorldRatingConcepts();
  const mapSeriesQ = useWorldMapSeries(activeConcept);

  useEffect(() => {
    if (!conceptSlug) {
      navigate(
        { pathname: worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT), search, hash },
        { replace: true },
      );
    }
  }, [conceptSlug, navigate, search, hash]);

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

  useEffect(() => {
    setSortOverride(null);
  }, [activeConcept]);

  // Смысловые направления («лучшие сверху») — из дефолта рейтинга концепта.
  const baseDirection = useMemo(
    () => defaultSortForConcept(activeConcept, concepts),
    [activeConcept, concepts],
  );
  const semanticDirectionFor = useCallback((slug) => (
    slug === SORT_BASE_COLUMN
      ? baseDirection
      : defaultSortForConcept(slug, concepts)
  ), [baseDirection, concepts]);

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
      unit: concepts.find((item) => item.slug === slug)?.unit || seriesData?.concept?.unit || '',
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
  const valuesByCode = useMemo(
    () => new Map(Object.entries(yearItems).map(([countryCode, item]) => [countryCode, item.value])),
    [yearItems],
  );
  const detailsByCode = useMemo(
    () => new Map(Object.entries(yearItems)),
    [yearItems],
  );
  // Полный рейтинг с местами считается по смысловому направлению концепта
  // (лучшие сверху) и НЕ зависит от кликов по стрелкам: место страны в
  // таблице остаётся честным независимо от текущего порядка колонок.
  const ranked = useMemo(() => {
    const rows = worldRankingFromYearItems(
      yearItems,
      Number.MAX_SAFE_INTEGER,
      baseDirection,
    );
    return rows.map((item, index) => ({ ...item, rank: index + 1 }));
  }, [yearItems, baseDirection]);
  const withoutData = useMemo(() => {
    const withData = new Set(Object.values(yearItems).map((item) => item.country_code));
    return countries.filter((country) => !withData.has(country.code));
  }, [countries, yearItems]);
  const catalogByKey = useMemo(() => {
    const map = new Map();
    for (const country of countries) {
      if (country?.code) map.set(country.code, country);
      if (country?.slug) map.set(country.slug, country);
    }
    return map;
  }, [countries]);
  const mapCountries = useMemo(
    () => countries.map((country) => ({
      ...country,
      name: countryPublicName(country, locale),
    })),
    [countries, locale],
  );
  const ratingCountryName = (item) => {
    const catalog = catalogByKey.get(item.country_code) || catalogByKey.get(item.country_slug);
    return countryPublicName({
      name: item.country_name || catalog?.name,
      name_en: catalog?.name_en || item.country_name_en,
      name_ru: catalog?.name_ru,
      country_name: item.country_name,
    }, locale);
  };

  // Единица одна на всю таблицу — уносим её в шапку колонки: иначе строка
  // повторяет «изменение за год, %» сорок один раз подряд.
  const sharedUnit = useMemo(() => {
    const units = new Set(ranked.map((item) => (item.unit || concept.unit || '').trim()));
    const raw = units.size === 1 ? [...units][0] : null;
    return localizeWorldUnit(raw, locale) || raw;
  }, [ranked, concept.unit, locale]);
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

  // Доскролл к карте/графику из OG/SEO-ссылок вида …#chart — как на карточке
  // индикатора; ждём появления блока после загрузки данных.
  useEffect(() => {
    if (hash !== '#chart') return;
    const node = document.getElementById('chart');
    if (!node) return;
    node.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [hash, loading]);

  const openCountry = (country, detail) => {
    const href = mapSelectHref(country, detail, {
      conceptSlug: activeConcept,
      russiaIndicatorCode,
    });
    if (href) navigate(href);
  };

  const countryWord = (n) => pluralUnit(n, 'world.unit.country', t, locale);

  // Сортировка по заголовкам. Кликом управляется одна колонка; направление
  // первого клика — смысловое («лучшие сверху»), второго — обратное.
  const sortedColSlug = sortOverride
    && (sortOverride.slug === SORT_BASE_COLUMN
      || extraColumns.some((col) => col.slug === sortOverride.slug))
    ? sortOverride.slug
    : SORT_BASE_COLUMN;
  const sortedColDir = sortOverride?.slug === sortedColSlug
    ? sortOverride.dir
    : semanticDirectionFor(sortedColSlug);

  const handleSortClick = useCallback((slug) => {
    setSortOverride((prev) => {
      if (prev && prev.slug === slug) {
        return { slug, dir: prev.dir === 'asc' ? 'desc' : 'asc' };
      }
      return { slug, dir: slug === SORT_BASE_COLUMN ? baseDirection : defaultSortForConcept(slug, concepts) };
    });
  }, [baseDirection, concepts]);

  // Доп-колонки: добавление через селектор, снятие крестиком в шапке колонки.
  const [addOpen, setAddOpen] = useState(false);
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
    if (sortedColSlug === slug) setSortOverride(null);
    writeExtraCols(extraSlugs.filter((item) => item !== slug));
  }, [extraSlugs, writeExtraCols, sortedColSlug]);

  const addableConcepts = useMemo(
    () => concepts.filter((item) => item.slug !== activeConcept && !extraSlugs.includes(item.slug)),
    [concepts, activeConcept, extraSlugs],
  );
  const atExtraMax = extraSlugs.length >= extraMax;

  // Порядок строк таблицы: колонка сортируется той же функцией, которой
  // рисуется ячейка (базовая — значение года, доп — lookupExtraValue).
  // Пустые значения всегда внизу независимо от направления.
  const displayRows = useMemo(() => {
    const valueOf = (item) => {
      if (sortedColSlug === SORT_BASE_COLUMN) return item.value ?? null;
      const col = extraColumns.find((candidate) => candidate.slug === sortedColSlug);
      return lookupExtraValue(col?.seriesData, activeYear, item)?.value ?? null;
    };
    const withValue = [];
    const withoutValue = [];
    for (const item of ranked) {
      if (valueOf(item) == null) withoutValue.push(item);
      else withValue.push(item);
    }
    withValue.sort((a, b) => (sortedColDir === 'asc'
      ? valueOf(a) - valueOf(b)
      : valueOf(b) - valueOf(a)));
    return [...withValue, ...withoutValue];
  }, [ranked, sortedColSlug, sortedColDir, extraColumns, activeYear]);

  const extraHeaderLabel = (col) => {
    const unit = localizeWorldUnit(col.unit, locale);
    if (!unit) return col.label;
    return t('world.rating.columnWithUnit', {
      label: col.label,
      unit: unit[0].toUpperCase() + unit.slice(1),
    });
  };

  // Слайдер колонок (правка 16): при 3+ показателях таблица шире контейнера —
  // разрешаем фиксированные сдвиги вправо, чтобы дотянуться до дальних колонок
  // без горизонтального скролла всей страницы.
  const columnCount = 1 + extraColumns.length;
  const maxShift = TABLE_SHIFT_BY_COLUMN_COUNT[
    Math.min(columnCount, TABLE_SHIFT_BY_COLUMN_COUNT.length - 1)
  ] || 0;
  const [tableShift, setTableShift] = useState(0);
  useEffect(() => {
    setTableShift((current) => Math.min(current, maxShift));
  }, [maxShift]);
  const tableStyle = maxShift > 0 && tableShift > 0
    ? { transform: `translateX(-${tableShift * 15}%)` }
    : undefined;

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
          <Link to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} className="mt-4 inline-flex rounded-xl bg-champagne px-4 py-2.5 text-sm font-semibold text-white">
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
              searchable={false}
              trailing={<WorldMapConceptNote conceptSlug={activeConcept} />}
            />
            {loading && concepts.length === 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {[0, 1, 2].map((i) => (
                  <SkeletonBox key={i} className="h-7 w-24 rounded-xl" />
                ))}
              </div>
            )}
          </section>

          <section id="chart" className="mb-5 grid scroll-mt-24 gap-4 lg:grid-cols-[minmax(0,1.55fr)_minmax(min(100%,24rem),0.85fr)]">
            <div className="rounded-[1.5rem] border border-border-subtle bg-surface p-3 shadow-[0_16px_45px_rgba(35,30,16,0.05)] sm:p-5">
              {mapSeriesQ.isLoading ? (
                <SkeletonBox className="aspect-[2/1] w-full rounded-2xl" />
              ) : (
                <>
                  <WorldMap
                    countries={mapCountries}
                    valuesByCode={valuesByCode}
                    detailsByCode={detailsByCode}
                    unit={localizeWorldUnit(concept.unit || mapSeriesQ.data?.concept?.unit || '', locale)}
                    metricName={shortName}
                    periodLabel={activeYear ? String(activeYear) : ''}
                    colorMode={conceptColorMode(activeConcept)}
                    colorDirection={sortedColDir}
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
              </p>
              <div className="mt-4 rounded-xl bg-obsidian-light px-3.5 py-3 text-xs leading-5 text-text-secondary">
                {activeConcept === 'hicp-index' || mapSeriesQ.data?.concept?.value_mode === 'yoy'
                  ? t('world.rating.noteYoy')
                  : t('world.rating.noteDefault')}
              </div>
              {locale === 'ru' && (
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
              )}
            </aside>
          </section>

          <section id="rating-table" className="mb-5 scroll-mt-24">
            <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
                  {t('world.rating.fullTable')}
                </p>
                <h2 className="mt-1 font-display text-2xl font-bold text-text-primary">
                  {t('world.rating.allWithData', { n: ranked.length })}
                </h2>
              </div>
              <div className="flex min-w-0 flex-wrap items-end gap-2.5">
                <label className="block min-w-[7.5rem]">
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
                    <button
                      type="button"
                      className={ButtonClass(sortedColDir === 'desc')}
                      onClick={() => setSortOverride({ slug: sortedColSlug, dir: 'desc' })}
                    >
                      {t('world.rating.sortDesc')}
                    </button>
                    <button
                      type="button"
                      className={ButtonClass(sortedColDir === 'asc')}
                      onClick={() => setSortOverride({ slug: sortedColSlug, dir: 'asc' })}
                    >
                      {t('world.rating.sortAsc')}
                    </button>
                  </div>
                </div>
                <button
                  type="button"
                  className={`${ButtonClass(addOpen)} h-9`}
                  onClick={() => setAddOpen((prev) => !prev)}
                >
                  {t('world.rating.addColumn')}
                </button>
              </div>
            </div>
            {addOpen && (
              <div className="mb-3 max-w-lg rounded-2xl border border-border-subtle bg-obsidian-light px-4 py-3.5">
                {!isAuthed && (
                  <>
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
                  </>
                )}
                {isAuthed && atExtraMax && (
                  <p className="text-xs leading-5 text-text-secondary">
                    {t('world.rating.extraMax')}
                  </p>
                )}
                {addableConcepts.length > 0 && !(isAuthed && atExtraMax) && (
                  <div className={`flex flex-wrap ${isAuthed ? '' : 'mt-3'} gap-1.5`}>
                    {addableConcepts
                      .slice(0, isAuthed ? undefined : extraMax)
                      .map((item) => (
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
            <div className="overflow-x-auto rounded-2xl border border-border-subtle bg-surface">
              <div style={tableStyle} className="transition-transform duration-200">
                <table className="w-full min-w-[52rem] text-sm">
                <thead className="sticky top-0 z-10 bg-obsidian-light/95 backdrop-blur-sm">
                  <tr className="text-left text-[11px] uppercase tracking-wide text-text-tertiary">
                    <th className="w-20 px-4 py-3 font-medium">{t('world.rating.col.rank')}</th>
                    <th className="px-4 py-3 font-medium">{t('world.rating.col.country')}</th>
                    <SortableTh
                      label={valueHeader}
                      active={sortedColSlug === SORT_BASE_COLUMN}
                      dir={sortedColDir}
                      onClick={() => handleSortClick(SORT_BASE_COLUMN)}
                    />
                    {extraColumns.map((col) => (
                      <SortableTh
                        key={col.slug}
                        minWidth
                        label={extraHeaderLabel(col)}
                        active={sortedColSlug === col.slug}
                        dir={sortedColDir}
                        onClick={() => handleSortClick(col.slug)}
                        onRemove={{
                          label: t('world.rating.extraRemove'),
                          onClick: () => removeExtra(col.slug),
                        }}
                      />
                    ))}
                    {!sharedUnit && <th className="px-4 py-3 font-medium">{t('world.rating.col.unit')}</th>}
                    <th className="px-4 py-3 font-medium">{t('common.period')}</th>
                  </tr>
                </thead>
                <tbody>
                  {displayRows.map((item) => (
                    <tr key={item.country_code} className="border-t border-border-subtle transition-colors hover:bg-surface-hover">
                      <td className="px-4 py-3 font-mono text-text-tertiary">{item.rank}</td>
                      <td className="px-4 py-3">
                        <Link to={rowHref(item, { conceptSlug: activeConcept, russiaIndicatorCode })} className="font-medium text-text-primary transition-colors hover:text-champagne">
                          {ratingCountryName(item)}
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
                          {item.unit ? localizeWorldUnit(item.unit, locale) : (concept.unit ? localizeWorldUnit(concept.unit, locale) : t('world.rating.fallbackUnit'))}
                        </td>
                      )}
                      <td className="px-4 py-3 font-mono text-xs text-text-tertiary">
                        {item.date ? formatDate(item.date, periodGranularity, locale) : '—'}
                      </td>
                    </tr>
                  ))}
                  {!loading && displayRows.length === 0 && (
                    <tr>
                      <td colSpan={colCount} className="px-4 py-8 text-center text-text-secondary">
                        {t('world.rating.emptyYear')}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
              </div>
            </div>
            {maxShift > 0 && (
              <div className="mt-2 flex items-center justify-end gap-1.5" data-testid="table-shift">
                <button
                  type="button"
                  aria-label={t('world.rating.slideLeft')}
                  disabled={tableShift <= 0}
                  onClick={() => setTableShift((current) => Math.max(0, current - 1))}
                  className="flex h-8 w-8 items-center justify-center rounded-lg border border-border-subtle bg-obsidian-light text-text-secondary transition-colors hover:text-champagne disabled:opacity-35"
                >
                  <ChevronLeft size={15} />
                </button>
                <button
                  type="button"
                  aria-label={t('world.rating.slideRight')}
                  disabled={tableShift >= maxShift}
                  onClick={() => setTableShift((current) => Math.min(maxShift, current + 1))}
                  className="flex h-8 w-8 items-center justify-center rounded-lg border border-border-subtle bg-obsidian-light text-text-secondary transition-colors hover:text-champagne disabled:opacity-35"
                >
                  <ChevronRight size={15} />
                </button>
              </div>
            )}
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
                    {countryPublicName(country, locale)}
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
