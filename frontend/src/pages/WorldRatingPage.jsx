import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Link, useLocation, useNavigate, useParams, useSearchParams,
} from 'react-router-dom';
import {
  ArrowDown, ArrowUp, ArrowUpDown, ChevronDown, ChevronLeft, ChevronRight, Globe2,
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
import LoadingNote from '../components/LoadingNote';
import { SkeletonBox } from '../components/Skeleton';
import Breadcrumbs from '../components/Breadcrumbs';
import RatingMetricPicker from '../components/RatingMetricPicker';
import { OtherYears, RankShifts, RatingDelta, RatingSpark } from '../components/RatingExtras';
import WorldMapConceptNote from '../components/WorldMapConceptNote';
import { useLocale, useT } from '../i18n';
import { localizeSource } from '../i18n/viewModeLabels';
import PlanetView from '../components/PlanetView';
import Button from '../components/Button';
import Chip from '../components/Chip';
import ChipGroup from '../components/ChipGroup';
import CountryFlag from '../components/CountryFlag';
import WorldCountUp from '../components/WorldCountUp';
import YearPicker from '../components/YearPicker';
import '../styles/world.css';
import '../styles/w6d.css';
import '../styles/z6-rating.css';
import { indicatorPolarity } from '../lib/deltaTone';
import { ratingHeading } from '../lib/ratingConcepts';
import {
  countrySeries, rankShifts, shareOf, yearOverYear,
} from '../lib/ratingInsights';
import { worldRatingTrail } from '../lib/breadcrumbs';
import {
  countryPath,
  WORLD_RATING_DEFAULT_CONCEPT,
  worldRatingPath,
  worldRatingYearPath,
} from '../lib/sitePaths';

const RATING_EXTRA_MAX_AUTH = 4;
// Гость может открыть один доп. показатель из URL (2 колонки всего);
// полный набор до 5 показателей — после регистрации (правка 22.1).
const RATING_EXTRA_MAX_GUEST = 1;

/** Спец-код базовой колонки «Значение» в сортировке по заголовкам. */
const SORT_BASE_COLUMN = '__base__';
/** Служебные колонки сортировки: название страны и изменение к прошлому году. */
const SORT_NAME_COLUMN = '__name__';
const SORT_DELTA_COLUMN = '__delta__';
/** Сколько строк видно, пока человек не нажал «Показать все страны». */
const TABLE_COMPACT_ROWS = 12;

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
  const { conceptSlug, year: pathYear } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { hash, search } = useLocation();
  const activeConcept = conceptSlug || WORLD_RATING_DEFAULT_CONCEPT;
  // Год живёт в адресе: `/world/rating/{показатель}/{год}`; старый `?year=` читается как запасной вариант.
  const rawYear = pathYear || searchParams.get('year');
  const selectedYear = /^[1-9]\d{3}$/.test(rawYear || '') ? Number(rawYear) : null;
  // Ссылки и переходы между показателями сохраняют выбранные колонки (`cols`), но не старый `?year=`.
  const keepSearch = useMemo(() => {
    const next = new URLSearchParams(searchParams);
    next.delete('year');
    const text = next.toString();
    return text ? `?${text}` : '';
  }, [searchParams]);
  // Активная колонка сортировки: { slug, dir } | null. null = пользователь ещё
  // не трогал переключатель → применяется смысловой порядок (лучшие сверху).
  // Любой refetch каталога не должен откатывать клик, поэтому запись идёт
  // только из обработчика клика и сброса при смене концепта.
  const [sortOverride, setSortOverride] = useState(null);

  const countriesQ = useWorldCountries();
  const catalogQ = useWorldRatingConcepts();
  // Срез прежнего показателя остаётся на экране, пока приходит новый: выбранные год и страна не теряются.
  const mapSeriesQ = useWorldMapSeries(activeConcept, { keepPrevious: true });
  const dataSlug = mapSeriesQ.data?.concept?.slug;
  const switching = Boolean(mapSeriesQ.isPlaceholderData && dataSlug && dataSlug !== activeConcept);
  // Всё, что рисуется из данных (шар, таблица, цвет, направление), относится к показателю этих данных.
  const viewSlug = switching ? dataSlug : activeConcept;

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
    () => defaultSortForConcept(viewSlug, concepts),
    [viewSlug, concepts],
  );
  const semanticDirectionFor = useCallback((slug) => {
    if (slug === SORT_BASE_COLUMN) return baseDirection;
    if (slug === SORT_NAME_COLUMN) return 'asc';
    if (slug === SORT_DELTA_COLUMN) return 'desc';
    return defaultSortForConcept(slug, concepts);
  }, [baseDirection, concepts]);

  const concept = useMemo(
    () => concepts.find((item) => item.slug === viewSlug)
      || mapSeriesQ.data?.concept
      || {
        slug: viewSlug,
        name: homeConceptLabel(viewSlug, t, t('world.ratingFallback')),
        unit: '',
      },
    [viewSlug, concepts, mapSeriesQ.data, t],
  );
  // Показатель из адреса (не данных): заголовок и подпись меняются сразу после нажатия.
  const targetConcept = useMemo(
    () => concepts.find((item) => item.slug === activeConcept)
      || (switching ? null : mapSeriesQ.data?.concept)
      || { slug: activeConcept, name: homeConceptLabel(activeConcept, t, t('world.ratingFallback')), unit: '' },
    [activeConcept, concepts, mapSeriesQ.data, switching, t],
  );
  const knownConceptLoaded = !catalogQ.isLoading && concepts.length > 0;
  const unknownConcept = knownConceptLoaded && !concepts.some((item) => item.slug === activeConcept);
  const years = useMemo(() => mapSeriesQ.data?.years || [], [mapSeriesQ.data]);
  const defaultYear = resolveActiveMapYear(years, null, mapSeriesQ.data?.values_by_year);
  const activeYear = resolveActiveMapYear(years, selectedYear, mapSeriesQ.data?.values_by_year);
  // Год — постоянный адрес. Год по умолчанию живёт на базовом адресе показателя (так же отвечает сервер).
  const ratingTarget = useCallback((slug, year) => ({
    pathname: year != null && year !== defaultYear ? worldRatingYearPath(slug, year) : worldRatingPath(slug),
    search: keepSearch,
    hash,
  }), [defaultYear, keepSearch, hash]);
  const setSelectedYear = (year) => {
    navigate(ratingTarget(activeConcept, year), { replace: true });
  };
  // Адрес с годом, которого у показателя нет (или совпадающим с годом по умолчанию), приводим к постоянному.
  useEffect(() => {
    if (switching || !years.length || !rawYear || mapSeriesQ.isFetching) return;
    if (selectedYear == null || !years.includes(selectedYear) || (selectedYear === defaultYear && pathYear)) {
      navigate(ratingTarget(activeConcept, null), { replace: true });
    }
  }, [switching, years, rawYear, selectedYear, defaultYear, pathYear, mapSeriesQ.isFetching, navigate, ratingTarget, activeConcept]);
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
    () => russiaDeepLinksForConcept(viewSlug),
    [viewSlug],
  );
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
  // Название страны берём из каталога на языке страницы: срез показателя мог прийти с английской подписью.
  const ratingCountryName = useCallback((item) => {
    const catalog = catalogByKey.get(item.country_code) || catalogByKey.get(item.country_slug);
    if (catalog) {
      const fromCatalog = countryPublicName({
        name: catalog.name_ru || catalog.name,
        name_en: catalog.name_en,
        name_ru: catalog.name_ru,
      }, locale);
      if (fromCatalog) return fromCatalog;
    }
    return countryPublicName({
      name: item.country_name,
      name_en: item.country_name_en,
      country_name: item.country_name,
    }, locale);
  }, [catalogByKey, locale]);
  const valuesByCode = useMemo(
    () => new Map(Object.entries(yearItems).map(([countryCode, item]) => [countryCode, item.value])),
    [yearItems],
  );
  // Подписи страны и источника — на языке страницы, чтобы шар и карточка не показывали английские названия по-русски.
  const detailsByCode = useMemo(
    () => new Map(Object.entries(yearItems).map(([code, item]) => [code, {
      ...item,
      country_name: ratingCountryName(item) || item.country_name,
      ...(item.source ? { source: localizeSource(item.source, locale) } : {}),
    }])),
    [yearItems, ratingCountryName, locale],
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

  // Колонки «Период» нет: общий период — одной строкой под заголовком таблицы, дата страны — в подсказке к значению.
  const periodNote = useMemo(() => {
    const dates = ranked.map((item) => item.date).filter(Boolean).sort();
    if (!dates.length) return '';
    const from = formatDate(dates[0], periodGranularity, locale);
    const to = formatDate(dates[dates.length - 1], periodGranularity, locale);
    return from === to
      ? t('z6.rating.periodNote', { period: from })
      : t('z6.rating.periodRange', { from, to });
  }, [ranked, periodGranularity, locale, t]);

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
  const colCount = (sharedUnit ? 6 : 7) + extraColumns.length;

  const shortName = homeConceptLabel(viewSlug, t, concept.name);
  const targetName = homeConceptLabel(activeConcept, t, targetConcept.name);
  const pageTitle = worldRatingTitle(activeConcept, targetConcept.name || targetName, activeYear, t);
  // Видимый заголовок короткий («ВВП стран мира, 2025»), полная формулировка остаётся в title страницы.
  const heading = ratingHeading(activeConcept, {
    t,
    name: targetConcept.name,
    unit: localizeWorldUnit(targetConcept.unit, locale),
    year: activeYear,
  });
  useDocumentMeta({
    title: pageTitle,
    description: t('world.rating.metaDesc', { title: pageTitle }),
    path: activeYear && activeYear !== defaultYear
      ? worldRatingYearPath(activeConcept, activeYear)
      : worldRatingPath(activeConcept),
  });


  const openCountry = (country, detail) => {
    const href = mapSelectHref(country, detail, {
      conceptSlug: viewSlug,
      russiaIndicatorCode,
    });
    if (href) navigate(href);
  };


  // Сортировка по заголовкам. Кликом управляется одна колонка; направление
  // первого клика — смысловое («лучшие сверху»), второго — обратное.
  const sortedColSlug = sortOverride
    && (sortOverride.slug === SORT_BASE_COLUMN
      || sortOverride.slug === SORT_NAME_COLUMN
      || sortOverride.slug === SORT_DELTA_COLUMN
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
      return { slug, dir: semanticDirectionFor(slug) };
    });
  }, [semanticDirectionFor]);

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

  // Изменение к прошлому году и мини-график считаются из уже загруженных лет: сервер ничего не досчитывает.
  const valuesByYear = mapSeriesQ.data?.values_by_year;
  const polarity = useMemo(() => indicatorPolarity(concept.name, shortName), [concept.name, shortName]);
  const percentUnit = Boolean(sharedUnit) && sharedUnit.startsWith('%');
  const changeByCode = useMemo(() => {
    const map = new Map();
    for (const item of ranked) map.set(item.country_code, yearOverYear(valuesByYear, years, activeYear, item.country_code));
    return map;
  }, [ranked, valuesByYear, years, activeYear]);
  const sparkByCode = useMemo(() => {
    const map = new Map();
    for (const item of ranked) map.set(item.country_code, countrySeries(valuesByYear, years, activeYear, item.country_code));
    return map;
  }, [ranked, valuesByYear, years, activeYear]);

  // Порядок строк таблицы: колонка сортируется той же функцией, которой
  // рисуется ячейка (базовая — значение года, доп — lookupExtraValue).
  // Пустые значения всегда внизу независимо от направления.
  const displayRows = useMemo(() => {
    if (sortedColSlug === SORT_NAME_COLUMN) {
      const sign = sortedColDir === 'asc' ? 1 : -1;
      return [...ranked].sort((a, b) => sign * ratingCountryName(a).localeCompare(ratingCountryName(b), locale));
    }
    const valueOf = (item) => {
      if (sortedColSlug === SORT_BASE_COLUMN) return item.value ?? null;
      if (sortedColSlug === SORT_DELTA_COLUMN) {
        const change = changeByCode.get(item.country_code);
        if (!change) return null;
        return percentUnit || change.pct == null ? change.abs : change.pct;
      }
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
  }, [ranked, sortedColSlug, sortedColDir, extraColumns, activeYear, changeByCode, percentUnit, ratingCountryName, locale]);

  const [showAllRows, setShowAllRows] = useState(false);
  const compactRows = !showAllRows && displayRows.length > TABLE_COMPACT_ROWS + 3;
  const visibleRows = compactRows ? displayRows.slice(0, TABLE_COMPACT_ROWS) : displayRows;
  const shifts = useMemo(
    () => rankShifts(valuesByYear, years, activeYear, baseDirection),
    [valuesByYear, years, activeYear, baseDirection],
  );

  // Медали — только когда порядок «лучшие сверху» по базовому показателю: иначе места 1–3 окажутся где попало.
  const medalsOn = sortedColSlug === SORT_BASE_COLUMN && sortedColDir === baseDirection;
  const medalOf = (rank) => (medalsOn && rank >= 1 && rank <= 3 ? rank : undefined);

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
  // Ориентир по странам: медиана поясняется словами, а не термином.
  const benchmark = mapSeriesQ.data?.benchmark_by_year?.[String(activeYear)];
  const medianNote = useMemo(() => {
    if (!benchmark || benchmark.value == null || !Number.isFinite(Number(benchmark.value))) return '';
    const isMedian = /медиан|median/i.test(String(benchmark.label || '')) || ['gdp-usd', 'gdp-per-capita-usd', 'hicp-index'].includes(viewSlug);
    const value = [fmtValue(benchmark.value), shortUnitOf(factUnit)].filter(Boolean).join(' ');
    return t(isMedian ? 'w6d.rating.medianNote' : 'w6d.rating.meanNote', { value });
  }, [benchmark, viewSlug, fmtValue, factUnit, t]);

  return (
    <div className="fe-data-page z6-page mx-auto w-full px-4 pb-12 pt-24 sm:px-6">
      <Breadcrumbs
        items={worldRatingTrail(targetName || targetConcept.name || t('crumb.rating'), activeConcept)}
      />

      <header className="z6-head mb-4">
        <div className="w2-kicker mb-2 flex items-center gap-2">
          <Globe2 size={14} aria-hidden="true" />
          {t('nav.worldRating')}
        </div>
        <h1 className="max-w-4xl font-display text-2xl font-bold leading-tight text-text-primary sm:text-3xl lg:text-4xl">
          {heading.title}
        </h1>
        {/* Подзаголовок и «Подробнее» в одну строку: пояснение раскрывается поверх, а не сдвигает рейтинг вниз. */}
        <div className="z6-head__sub">
          {heading.subtitle && <p className="w6d-subtitle">{heading.subtitle}</p>}
          <details className="w2-details w2-details--tight">
            <summary>{t('x1.rating.details')}</summary>
            <p className="max-w-3xl leading-6">{t('world.rating.intro')}</p>
          </details>
        </div>
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
          <div className="z6-split">
            <div className="z6-main">
              <section className="z6-toolbar" aria-busy={switching}>
                <RatingMetricPicker
                  concepts={concepts}
                  value={activeConcept}
                  linkForSlug={(slug) => ({
                    pathname: activeYear ? worldRatingYearPath(slug, activeYear) : worldRatingPath(slug),
                    search: keepSearch,
                  })}
                  label={t('world.rating.conceptLabel')}
                  loading={loading && concepts.length === 0}
                  trailing={<WorldMapConceptNote conceptSlug={activeConcept} label={t('z6.rating.whatIsMetric')} />}
                />
              </section>

              {ranked.length > 0 && (
                <aside className="w2-facts z6-ribbon fe-reveal" aria-label={t('world.rating.summary')}>
                  <div className="w2-facts-grid">
                    {[
                      [first, t('w2.rating.first')],
                      [last, t('w2.rating.last')],
                    ].filter(([item]) => item).map(([item, label]) => (
                      <Link
                        key={item.country_code}
                        to={rowHref(item, { conceptSlug: viewSlug, russiaIndicatorCode })}
                        className="w2-fact fe-press"
                        data-place={label === t('w2.rating.first') ? 'first' : 'last'}
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
                </aside>
              )}

              <section id="rating-table" className="z6-table scroll-mt-24">
                <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="font-display text-2xl font-bold text-text-primary">
                      {t('world.rating.allWithData', { n: ranked.length })}
                    </h2>
                    {periodNote && <p className="z6-table__sub">{periodNote}</p>}
                  </div>
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
                  <div className="z3-add-panel fe-reveal" role="group" aria-label={t('world.rating.addColumn')}>
                    {isAuthed && atExtraMax ? (
                      <p className="z3-add-panel__text">{t('world.rating.extraMax')}</p>
                    ) : (
                      <>
                        <h3 className="z3-add-panel__title">
                          {isAuthed
                            ? t('z3.rating.pickTitle')
                            : t(atExtraMax ? 'z3.rating.guestLimitTitle' : 'z3.rating.guestPickTitle')}
                        </h3>
                        {!isAuthed && (
                          <p className="z3-add-panel__text">
                            {t(atExtraMax ? 'z3.rating.guestLimitHint' : 'z3.rating.guestPickHint')}
                          </p>
                        )}
                      </>
                    )}
                    {addableConcepts.length > 0 && !atExtraMax && (
                      <ChipGroup label={t('z3.rating.pickTitle')} className="z3-add-panel__chips">
                        {addableConcepts.map((item) => {
                          const name = homeConceptLabel(item.slug, t, item.name);
                          return (
                            <Chip
                              key={item.slug}
                              aria-pressed={undefined}
                              aria-label={t('z3.rating.addNamed', { name })}
                              className="z3-add-chip"
                              onClick={() => addExtra(item.slug)}
                            >
                              <Plus size={13} aria-hidden="true" />
                              {name}
                            </Chip>
                          );
                        })}
                      </ChipGroup>
                    )}
                    {!isAuthed && atExtraMax && (
                      <div className="z3-add-panel__actions">
                        <Button as={Link} size="sm" to="/register">
                          {t('world.rating.register')}
                        </Button>
                        <Button as={Link} variant="secondary" size="sm" to="/login">
                          {t('world.rating.login')}
                        </Button>
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
                    <ol className={`w2-rank-list${switching ? ' w6d-switching' : ''}`}>
                      {visibleRows.map((item) => {
                        const share = shareOf(item.value, barMax.max, barMax.positive);
                        return (
                          <li key={item.country_code} className="w2-rank-item">
                            <Link
                              to={rowHref(item, { conceptSlug: viewSlug, russiaIndicatorCode })}
                              className="w2-rank-row fe-press"
                            >
                              <span className="w2-rank-pos" data-medal={medalOf(item.rank)}>{item.rank}</span>
                              <span className="w2-rank-flag"><CountryFlag code={item.country_code} /></span>
                              <span className="w2-rank-name">
                                {ratingCountryName(item)}
                                <span className="w6d-rank-sub">
                                  <RatingDelta
                                    change={changeByCode.get(item.country_code)}
                                    percentUnit={percentUnit}
                                    polarity={polarity}
                                    locale={locale}
                                  />
                                </span>
                              </span>
                              <span className="w2-rank-value">
                                <strong>{fmtValue(item.value)}</strong>
                                {cardUnit(item) && <small>{cardUnit(item)}</small>}
                              </span>
                              <ChevronRight className="w2-rank-chev" size={16} aria-hidden="true" />
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
                  <div
                    className="z6-table-card overflow-x-auto rounded-3xl border border-border-subtle bg-surface"
                    data-scroll={extraColumns.length > 0 ? 'x' : undefined}
                  >
                    <div style={tableStyle} className="transition-transform duration-200">
                      <table className="w6d-table w-full min-w-[34rem] text-sm">
                        <thead className="sticky top-0 z-10 bg-obsidian-light/95 backdrop-blur-sm">
                          <tr className="text-left text-xs text-text-secondary">
                            <th className="w-20 px-4 py-3 font-medium">{t('world.rating.col.rank')}</th>
                            <SortableTh
                              label={t('world.rating.col.country')}
                              right={false}
                              active={sortedColSlug === SORT_NAME_COLUMN}
                              dir={sortedColDir}
                              onClick={() => handleSortClick(SORT_NAME_COLUMN)}
                            />
                            <SortableTh
                              label={valueHeader}
                              active={sortedColSlug === SORT_BASE_COLUMN}
                              dir={sortedColDir}
                              onClick={() => handleSortClick(SORT_BASE_COLUMN)}
                            />
                            <th className="w6d-col-bar px-2 py-3 font-medium" aria-hidden="true" />
                            <SortableTh
                              label={t('w6d.rating.col.change')}
                              active={sortedColSlug === SORT_DELTA_COLUMN}
                              dir={sortedColDir}
                              onClick={() => handleSortClick(SORT_DELTA_COLUMN)}
                            />
                            <th className="w6d-col-trend px-4 py-3 text-right font-medium">{t('w6d.rating.col.trend')}</th>
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
                          </tr>
                        </thead>
                        <tbody>
                          {visibleRows.map((item, rowIndex) => (
                            <tr
                              key={item.country_code}
                              className="z6-row border-t border-border-subtle"
                              data-top={medalOf(item.rank)}
                              style={{ '--z6-i': Math.min(rowIndex, 24) }}
                            >
                              <td className="px-4 py-3 tabular-nums text-text-tertiary">
                                <span className="w2-rank-pos" data-medal={medalOf(item.rank)}>{item.rank}</span>
                              </td>
                              <td className="px-4 py-3">
                                <Link to={rowHref(item, { conceptSlug: viewSlug, russiaIndicatorCode })} className="inline-flex items-center gap-2.5 font-medium text-text-primary transition-colors hover:text-champagne">
                                  <CountryFlag code={item.country_code} />
                                  {ratingCountryName(item)}
                                </Link>
                              </td>
                              <td
                                className="z6-val px-4 py-3 text-right font-semibold tabular-nums text-text-primary"
                                title={item.date ? t('z6.rating.rowPeriod', { period: formatDate(item.date, periodGranularity, locale) }) : undefined}
                              >
                                {fmtValue(item.value)}
                              </td>
                              <td className="w6d-col-bar px-2 py-3" aria-hidden="true">
                                <span className="w6d-bar" style={{ '--z6-s': (shareOf(item.value, barMax.max, barMax.positive) / 100).toFixed(3) }}>
                                  <span style={{ width: `${shareOf(item.value, barMax.max, barMax.positive)}%` }} />
                                </span>
                              </td>
                              <td className="px-4 py-3 text-right">
                                <RatingDelta
                                  change={changeByCode.get(item.country_code)}
                                  percentUnit={percentUnit}
                                  polarity={polarity}
                                  locale={locale}
                                />
                              </td>
                              <td className="w6d-col-trend px-4 py-3 text-right text-champagne-ink">
                                <RatingSpark
                                  points={sparkByCode.get(item.country_code)}
                                  label={t('w6d.rating.trendLabel', { name: ratingCountryName(item) })}
                                />
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
                {displayRows.length > TABLE_COMPACT_ROWS + 3 && (
                  <button
                    type="button"
                    className="w6d-showall fe-press"
                    aria-expanded={!compactRows}
                    onClick={() => setShowAllRows((open) => !open)}
                  >
                    {compactRows ? t('w6d.rating.showAll', { n: displayRows.length }) : t('w6d.rating.showLess')}
                    <ChevronDown size={15} aria-hidden="true" className={compactRows ? '' : 'w6d-rot'} />
                  </button>
                )}
                {medianNote && <p className="w6d-median">{medianNote}</p>}
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

              {ranked.length > 0 && (
                <section className="w2-facts z6-notes fe-reveal">
                  <details className="w2-details">
                    <summary>{t('w2.rating.howTitle')}</summary>
                    <p>
                      {viewSlug === 'hicp-index' || mapSeriesQ.data?.concept?.value_mode === 'yoy'
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
                </section>
              )}

              <OtherYears
                years={years}
                activeYear={activeYear}
                hrefFor={(year) => ratingTarget(activeConcept, year)}
              />
            </div>
            <div className="z6-side">
              <section id="chart" className="z6-planet scroll-mt-24">
                {switching && (
                  <p className="w6d-switching-note" role="status">
                    <span className="fe-search-spinner" aria-hidden="true" />
                    {t('w6d.rating.updating', { name: targetName })}
                  </p>
                )}
                <div className={`min-w-0${switching ? ' w6d-switching' : ''}`} aria-busy={switching}>
                  {mapSeriesQ.isLoading ? (
                    <div className="w2-planet-skeleton" role="status" aria-label={t('planet.loading')}>
                      <LoadingNote onRefresh={() => mapSeriesQ.refetch()} />
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
                        colorMode={conceptColorMode(viewSlug)}
                        colorDirection={sortedColDir}
                        defaultScope="world"
                        years={years}
                        year={activeYear}
                        onYearChange={setSelectedYear}
                        conceptSlug={viewSlug}
                        rankingItems={ranked}
                        benchmark={mapSeriesQ.data?.benchmark_by_year?.[String(activeYear)]}
                        ratingHref="#rating-table"
                        hideListOnPhone
                        onSelect={openCountry}
                      />
                    </>
                  )}
                </div>
              </section>

              <RankShifts
                compact
                shifts={shifts}
                nameOf={(code) => ratingCountryName(yearItems[code] || { country_code: code })}
                hrefOf={(code) => rowHref(yearItems[code] || { country_code: code }, { conceptSlug: viewSlug, russiaIndicatorCode })}
              />
            </div>
          </div>

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
