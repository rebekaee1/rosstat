import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Link, useLocation, useNavigate, useParams, useSearchParams,
} from 'react-router-dom';
import {
  ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Globe2,
  MapPinned, Plus, X,
} from 'lucide-react';
import { useAuth } from '../context/authContext';
import useDocumentMeta from '../lib/useMeta';
import { track, events } from '../lib/track';
import {
  formatWorldValue,
  localizeWorldUnit,
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
import { splitUnit, uniformDigits } from '../lib/countryFlag';
import useMatchMedia from '../lib/useMatchMedia';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import Breadcrumbs from '../components/Breadcrumbs';
import WorldConceptPicker from '../components/WorldConceptPicker';
import WorldMapConceptNote from '../components/WorldMapConceptNote';
import { useLocale, useT } from '../i18n';
import PlanetView from '../components/PlanetView';
import Button from '../components/Button';
import Chip from '../components/Chip';
import CountryFlag from '../components/CountryFlag';
import WorldCountUp from '../components/WorldCountUp';
import YearPicker from '../components/YearPicker';
import '../styles/world.css';
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
            'inline-flex min-w-0 items-center gap-1 rounded-lg transition-colors hover:text-champagne pointer-coarse:min-h-11',
            active ? 'text-champagne' : '',
          ].join(' ')}
        >
          <span className="min-w-0 truncate">{label}</span>
          <Icon size={12} aria-hidden="true" />
        </button>
        {onRemove && (
          <button
            type="button"
            className="fe-press inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-text-tertiary transition-colors hover:text-champagne pointer-coarse:h-11 pointer-coarse:w-11"
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
  const rawYear = searchParams.get('year');
  const selectedYear = /^[1-9]\d{3}$/.test(rawYear || '') ? Number(rawYear) : null;
  const setSelectedYear = (year) => {
    const next = new URLSearchParams(searchParams);
    if (year == null) next.delete('year');
    else next.set('year', String(year));
    navigate({ search: next.toString(), hash }, { replace: true });
  };
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

  // Смена концепта сбрасывает сортировку: корректируем состояние во время
  // рендера (паттерн React «adjust state on prop change»), не в эффекте.
  const [sortConcept, setSortConcept] = useState(activeConcept);
  if (sortConcept !== activeConcept) {
    setSortConcept(activeConcept);
    setSortOverride(null);
  }

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
    path: activeYear && activeYear !== resolveActiveMapYear(years, null, mapSeriesQ.data?.values_by_year)
      ? `${worldRatingPath(activeConcept)}/${activeYear}`
      : worldRatingPath(activeConcept),
  });


  const openCountry = (country, detail) => {
    const href = mapSelectHref(country, detail, {
      conceptSlug: activeConcept,
      russiaIndicatorCode,
    });
    if (href) navigate(href);
  };


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
  const [tableShiftRaw, setTableShift] = useState(0);
  const tableShift = Math.min(tableShiftRaw, maxShift);
  const tableStyle = maxShift > 0 && tableShift > 0
    ? { transform: `translateX(-${tableShift * 15}%)` }
    : undefined;

  // На телефоне вместо широкой таблицы — карточки: место, флаг, страна, значение: значение всегда на одном экране со страной.
  const narrow = useMatchMedia('(max-width: 639px)');
  const digits = useMemo(() => uniformDigits(ranked.map((item) => item.value)), [ranked]);
  const fmtValue = useCallback((value) => formatWorldValue(value, digits, locale), [digits, locale]);
  const shortUnitOf = (text) => splitUnit(text).short;
  const cardUnit = (item) => (sharedUnit
    ? shortUnitOf(sharedUnit)
    : shortUnitOf(localizeWorldUnit(item.unit || concept.unit, locale)));
  const first = ranked[0] || null;
  const last = ranked.length > 1 ? ranked[ranked.length - 1] : null;
  const factUnit = sharedUnit || localizeWorldUnit(first?.unit || concept.unit, locale);
  const barMax = useMemo(() => {
    let max = 0;
    let positive = true;
    for (const item of ranked) {
      const value = Number(item.value);
      if (!Number.isFinite(value)) continue;
      if (value < 0) positive = false;
      if (value > max) max = value;
    }
    return { max, positive };
  }, [ranked]);

  return (
    <div className="fe-data-page mx-auto w-full max-w-7xl px-4 pb-12 pt-24 sm:px-6">
      <Breadcrumbs
        items={worldRatingTrail(shortName || concept.name || t('crumb.rating'), activeConcept)}
      />

      <header className="mb-4">
        <div className="w2-kicker mb-2 flex items-center gap-2">
          <Globe2 size={14} aria-hidden="true" />
          {t('nav.worldRating')}
        </div>
        <h1 className="max-w-4xl font-display text-2xl font-bold leading-tight text-text-primary sm:text-3xl lg:text-4xl">
          {pageTitle}
        </h1>
        {/* Пояснение не стоит между заголовком и планетой: планета должна быть видна на первом экране. */}
        <details className="w2-details w2-details--tight">
          <summary>{t('x1.rating.details')}</summary>
          <p className="max-w-3xl leading-6">{t('world.rating.intro')}</p>
        </details>
      </header>

      {error && (
        <ApiRetryBanner onRetry={retry} isFetching={countriesQ.isFetching || catalogQ.isFetching || mapSeriesQ.isFetching} className="mb-6">
          {t('world.rating.loadError')}
        </ApiRetryBanner>
      )}

      {unknownConcept && (
        <div className="mb-8 rounded-3xl border border-border-subtle bg-surface p-6">
          <h2 className="font-display text-xl font-semibold text-text-primary">{t('world.rating.notFoundTitle')}</h2>
          <p className="mt-2 text-sm text-text-secondary">
            {t('world.rating.notFoundBody')}
          </p>
          <Button as={Link} to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} className="mt-4">
            {t('world.rating.openUnemployment')}
          </Button>
        </div>
      )}

      {!unknownConcept && (
        <>
          <section className="mb-4 rounded-3xl border border-border-subtle bg-surface px-3.5 py-3 shadow-sm sm:px-4">
            <WorldConceptPicker
              concepts={concepts}
              value={activeConcept}
              mode="link"
              linkForSlug={(slug) => worldRatingPath(slug)}
              label={t('world.rating.conceptLabel')}
              searchable={false}
              mobileScroll
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

          <section id="chart" className="mb-5 grid scroll-mt-24 gap-4">
            <div className="min-w-0">
              {mapSeriesQ.isLoading ? (
                <div className="w2-planet-skeleton" role="status" aria-label={t('planet.loading')}>
                  <SkeletonBox className="h-12 w-full rounded-xl" />
                  <div className="w2-planet-skeleton-orb" aria-hidden="true" />
                </div>
              ) : (
                <>
                  <PlanetView
                    initialMode="data"
                    countries={mapCountries}
                    valuesByCode={valuesByCode}
                    detailsByCode={detailsByCode}
                    unit={localizeWorldUnit(concept.unit || mapSeriesQ.data?.concept?.unit || '', locale)}
                    metricName={shortName}
                    periodLabel={activeYear ? String(activeYear) : ''}
                    colorMode={conceptColorMode(activeConcept)}
                    colorDirection={sortedColDir}
                    defaultScope="world"
                    years={years}
                    year={activeYear}
                    onYearChange={setSelectedYear}
                    conceptSlug={activeConcept}
                    rankingItems={ranked}
                    benchmark={mapSeriesQ.data?.benchmark_by_year?.[String(activeYear)]}
                    ratingHref="#rating-table"
                    hideListOnPhone
                    onSelect={openCountry}
                  />
                </>
              )}
            </div>

            {ranked.length > 0 && (
              <aside className="w2-facts fe-reveal" aria-label={t('world.rating.summary')}>
                <div className="w2-facts-grid">
                  {[
                    [first, t('w2.rating.first')],
                    [last, t('w2.rating.last')],
                  ].filter(([item]) => item).map(([item, label]) => (
                    <Link
                      key={item.country_code}
                      to={rowHref(item, { conceptSlug: activeConcept, russiaIndicatorCode })}
                      className="w2-fact fe-press"
                    >
                      <span className="w2-fact-label">{label}</span>
                      <span className="w2-fact-name">
                        <CountryFlag code={item.country_code} />
                        <span className="min-w-0">{ratingCountryName(item)}</span>
                      </span>
                      <span className="w2-fact-value">
                        <WorldCountUp value={item.value} format={fmtValue} />
                        {factUnit && <small>{factUnit}</small>}
                      </span>
                    </Link>
                  ))}
                </div>
                <details className="w2-details">
                  <summary>{t('w2.rating.howTitle')}</summary>
                  <p>
                    {activeConcept === 'hicp-index' || mapSeriesQ.data?.concept?.value_mode === 'yoy'
                      ? t('world.rating.noteYoy')
                      : t('world.rating.noteDefault')}
                  </p>
                </details>
                {locale === 'ru' && (
                  <div className="w2-facts-russia">
                    <p className="w2-facts-label">{t('world.rating.russiaRegions')}</p>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        as={Link}
                        variant="ghost"
                        size="sm"
                        to={russiaLinks.countryHref}
                        className="gap-1.5 bg-champagne/15!"
                      >
                        <Globe2 size={13} aria-hidden="true" />
                        {russiaIndicatorCode
                          ? t('world.rating.russiaIndicator')
                          : t('world.rating.russiaSection')}
                      </Button>
                      <Button
                        as={Link}
                        variant="secondary"
                        size="sm"
                        to={russiaLinks.regionsHref}
                        className="gap-1.5"
                      >
                        <MapPinned size={13} aria-hidden="true" />
                        {t('world.rating.russiaRegionsLink')}
                      </Button>
                      {russiaLinks.regionRatingHref && (
                        <Button
                          as={Link}
                          variant="secondary"
                          size="sm"
                          to={russiaLinks.regionRatingHref}
                        >
                          {t('world.rating.regionRatingLink')}
                        </Button>
                      )}
                    </div>
                  </div>
                )}
              </aside>
            )}
          </section>

          <section id="rating-table" className="mb-5 scroll-mt-24">
            <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
              <h2 className="font-display text-2xl font-bold text-text-primary">
                {t('world.rating.allWithData', { n: ranked.length })}
              </h2>
              <div className="flex min-w-0 flex-wrap items-end gap-2.5">
                <div className="block min-w-[7.5rem]">
                  <span className="mb-1 block text-xs text-text-secondary">
                    {t('common.year')}
                  </span>
                  <YearPicker
                    years={years}
                    value={activeYear || null}
                    onChange={setSelectedYear}
                    label={t('common.year')}
                    disabled={!years.length}
                    align="start"
                    className="w-32 [--fe-year-h:40px] pointer-coarse:[--fe-year-h:44px]"
                  />
                </div>
                <div className="min-w-0">
                  <p className="mb-1 text-xs text-text-secondary">
                    {t('world.rating.sortOrder')}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    <Chip
                      active={sortedColDir === 'desc'}
                      onClick={() => setSortOverride({ slug: sortedColSlug, dir: 'desc' })}
                    >
                      {t('world.rating.sortDesc')}
                    </Chip>
                    <Chip
                      active={sortedColDir === 'asc'}
                      onClick={() => setSortOverride({ slug: sortedColSlug, dir: 'asc' })}
                    >
                      {t('world.rating.sortAsc')}
                    </Chip>
                  </div>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  aria-expanded={addOpen}
                  onClick={() => setAddOpen((prev) => !prev)}
                  className="gap-1.5"
                >
                  <Plus size={14} aria-hidden="true" />
                  {t('world.rating.addColumn')}
                </Button>
              </div>
            </div>
            {addOpen && (
              <div className="mb-3 max-w-lg rounded-3xl border border-border-subtle bg-obsidian-light px-4 py-3.5">
                {!isAuthed && (
                  <>
                    <h3 className="text-sm font-semibold text-text-primary">
                      {t('world.rating.extraGuestTitle')}
                    </h3>
                    <p className="mt-1.5 text-xs leading-5 text-text-secondary">
                      {t('world.rating.matrix.guestCap')}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button as={Link} size="sm" to="/register">
                        {t('world.rating.register')}
                      </Button>
                      <Button as={Link} variant="secondary" size="sm" to="/login">
                        {t('world.rating.login')}
                      </Button>
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
                        <Chip
                          key={item.slug}
                          onClick={() => addExtra(item.slug)}
                        >
                          {homeConceptLabel(item.slug, t, item.name)}
                        </Chip>
                      ))}
                  </div>
                )}
              </div>
            )}

            {narrow ? (
              <>
                <p className="mb-2 text-xs text-text-secondary">
                  {valueHeader}
                  {activeYear ? `, ${activeYear}` : ''}
                </p>
                <ol className="w2-rank-list">
                  {displayRows.map((item) => {
                    const share = barMax.positive && barMax.max > 0 && Number.isFinite(Number(item.value))
                      ? Math.max(2, Math.min(100, (Number(item.value) / barMax.max) * 100)) : 0;
                    return (
                      <li key={item.country_code} className="w2-rank-item">
                        <Link
                          to={rowHref(item, { conceptSlug: activeConcept, russiaIndicatorCode })}
                          className="w2-rank-row fe-press"
                        >
                          <span className="w2-rank-pos">{item.rank}</span>
                          <span className="w2-rank-flag"><CountryFlag code={item.country_code} /></span>
                          <span className="w2-rank-name">{ratingCountryName(item)}</span>
                          <span className="w2-rank-value">
                            <strong>{fmtValue(item.value)}</strong>
                            {cardUnit(item) && <small>{cardUnit(item)}</small>}
                          </span>
                          {share > 0 && <span className="w2-rank-bar" style={{ '--w2-share': `${share}%` }} aria-hidden="true" />}
                        </Link>
                        {extraColumns.length > 0 && (
                          <dl className="w2-rank-extra">
                            {extraColumns.map((col) => (
                              <div key={col.slug}>
                                <dt>{col.label}</dt>
                                <dd>{formatWorldValue(lookupExtraValue(col.seriesData, activeYear, item)?.value, undefined, locale)}</dd>
                              </div>
                            ))}
                          </dl>
                        )}
                      </li>
                    );
                  })}
                  {!loading && displayRows.length === 0 && (
                    <li className="px-4 py-8 text-center text-sm text-text-secondary">
                      {t('world.rating.emptyYear')}
                    </li>
                  )}
                </ol>
              </>
            ) : (
              <div className="overflow-x-auto rounded-3xl border border-border-subtle bg-surface">
                <div style={tableStyle} className="transition-transform duration-200">
                  <table className="w-full min-w-[34rem] text-sm">
                    <thead className="sticky top-0 z-10 bg-obsidian-light/95 backdrop-blur-sm">
                      <tr className="text-left text-xs text-text-secondary">
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
                          <td className="px-4 py-3 tabular-nums text-text-tertiary">{item.rank}</td>
                          <td className="px-4 py-3">
                            <Link to={rowHref(item, { conceptSlug: activeConcept, russiaIndicatorCode })} className="inline-flex items-center gap-2.5 font-medium text-text-primary transition-colors hover:text-champagne">
                              <CountryFlag code={item.country_code} />
                              {ratingCountryName(item)}
                            </Link>
                          </td>
                          <td className="px-4 py-3 text-right font-semibold tabular-nums text-text-primary">
                            {fmtValue(item.value)}
                          </td>
                          {extraColumns.map((col) => (
                            <td
                              key={col.slug}
                              className="px-4 py-3 text-right tabular-nums text-text-primary"
                            >
                              {formatWorldValue(lookupExtraValue(col.seriesData, activeYear, item)?.value, undefined, locale)}
                            </td>
                          ))}
                          {!sharedUnit && (
                            <td className="px-4 py-3 text-xs text-text-secondary">
                              {item.unit ? localizeWorldUnit(item.unit, locale) : (concept.unit ? localizeWorldUnit(concept.unit, locale) : t('world.rating.fallbackUnit'))}
                            </td>
                          )}
                          <td className="px-4 py-3 text-xs text-text-tertiary">
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
            )}
            {!narrow && maxShift > 0 && (
              <div className="mt-2 flex items-center justify-end gap-1.5" data-testid="table-shift">
                <Button
                  variant="secondary"
                  aria-label={t('world.rating.slideLeft')}
                  disabled={tableShift <= 0}
                  onClick={() => setTableShift(Math.max(0, tableShift - 1))}
                  className="w-10 px-0! pointer-coarse:w-11"
                >
                  <ChevronLeft size={15} aria-hidden="true" />
                </Button>
                <Button
                  variant="secondary"
                  aria-label={t('world.rating.slideRight')}
                  disabled={tableShift >= maxShift}
                  onClick={() => setTableShift(Math.min(maxShift, tableShift + 1))}
                  className="w-10 px-0! pointer-coarse:w-11"
                >
                  <ChevronRight size={15} aria-hidden="true" />
                </Button>
              </div>
            )}
          </section>

          {withoutData.length > 0 && (
            <details className="w2-details w2-details--card">
              <summary>
                {t('world.rating.withoutDataTitle', {
                  year: activeYear || t('world.rating.selectedYear'),
                  n: withoutData.length,
                })}
              </summary>
              <div className="mt-3 flex max-h-48 flex-wrap gap-2 overflow-y-auto pr-1">
                {withoutData.map((country) => (
                  <Button
                    as={Link}
                    key={country.slug}
                    variant="secondary"
                    size="sm"
                    to={country.code === 'RU' ? russiaLinks.countryHref : countryPath(country.slug)}
                  >
                    <CountryFlag code={country.code} />
                    {countryPublicName(country, locale)}
                  </Button>
                ))}
              </div>
            </details>
          )}
        </>
      )}
    </div>
  );
}
