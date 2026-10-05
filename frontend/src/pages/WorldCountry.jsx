// Страница страны: /world/{slug}
// Темы слева + сетка показателей; поиск не ломает сетку.
import NotFound from './NotFound';
import { useEffect, useMemo, useState, useDeferredValue } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  Search, BarChart3, ArrowUpRight, ChevronDown, Scale, Spline,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  worldCountryDescription,
  worldCountryTitle,
} from '../lib/pageMeta';
import {
  useWorldCountry, useWorldIndicatorData, formatWorldValue, localizeWorldUnit, pluralRu,
} from '../lib/worldApi';
import {
  collapseCountryIndicators, indicatorPublicName, localizedDisplay,
} from '../lib/worldViewModes';
import { formatChange, formatCount, formatDate } from '../lib/format';
import { indicatorPolarity } from '../lib/deltaTone';
import { splitUnit } from '../lib/countryFlag';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Button from '../components/Button';
import Chip from '../components/Chip';
import CountryFlag from '../components/CountryFlag';
import DeltaBadge from '../components/DeltaBadge';
import Sparkline, { SparklineSkeleton } from '../components/Sparkline';
import WorldCountUp from '../components/WorldCountUp';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import MobileNavSelect from '../components/MobileNavSelect';
import UsCatalogNav from '../components/UsCatalogNav';
import { groupUsSections, shortUsIndicatorName } from '../lib/usCatalogTopics';
import useSearchTracking from '../lib/useSearchTracking';
import { filterSearchOptions } from '../lib/searchSynonyms';
import { CountrySilhouette } from '../components/WorldMap';
import {
  breadcrumbJsonLd,
  worldCountryTrail,
} from '../lib/breadcrumbs';
import { mountJsonLd } from '../lib/jsonLd';
import {
  countryPath,
  countryRegionsPath,
  indicatorPath,
  russiaIndicatorPath,
} from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import { localizeSource } from '../i18n/viewModeLabels';
import { countryPublicName, homeConceptLabel, HOME_MAP_RUSSIA_CONCEPT_CODES } from '../lib/homeWorkbench';
import { dropRepeatedUnit, groupNearDuplicates } from '../lib/countryIndicatorGroups';
import '../styles/world.css';
import '../styles/x2-indicator.css';
import '../styles/z1-polish.css';
import usePageLoading, { useSlowFlag } from '../lib/usePageLoading';

/** Главные темы идут первыми: человек ждёт «Экономику» и «Население», а не алфавитный «Бизнес». */
const TOPIC_PRIORITY = [
  'Национальные счета', 'Цены', 'Рынок труда', 'Население', 'Государственные финансы',
  'Внешняя торговля', 'Бизнес и инвестиции',
];
function topicRank(category) {
  const index = TOPIC_PRIORITY.indexOf(category?.name_ru || category?.name);
  return index === -1 ? TOPIC_PRIORITY.length : index;
}

/** Тема с меньшим числом показателей уходит в конец списка и не открывается по умолчанию. */
const THIN_TOPIC = 5;

function normalize(s) {
  return (s || '').toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ').trim();
}

function formatIndicatorDate(dateStr, frequency, locale) {
  if (!dateStr) return '—';
  if (frequency === 'annual') return formatDate(dateStr, 'annual', locale);
  if (frequency === 'quarterly') return formatDate(dateStr, 'quarterly', locale);
  return formatDate(dateStr, 'full', locale);
}

function CompactChange({ change, label, locale }) {
  if (change == null || !Number.isFinite(Number(change)) || Math.abs(Number(change)) < 1e-12) {
    return null;
  }
  const n = Number(change);
  // Цвет по смыслу показателя: рост безработицы или инфляции не «зелёный», неизвестный смысл — нейтрально.
  return (
    <DeltaBadge delta={n} polarity={indicatorPolarity(label)} className="text-xs">
      {formatChange(n, locale)}
    </DeltaBadge>
  );
}

/** Единицу и период человек видит рядом с числом: «2,9 % — август 2026», а не голая цифра. */
function kpiDigits(value) {
  const abs = Math.abs(Number(value));
  if (abs >= 1000) return 0;
  return abs >= 1 ? 1 : 2;
}

function CountryKpiCard({ item, slug, hero, locale }) {
  const t = useT();
  const mode = `${item.concept_slug === 'hicp-index' ? 'yoy' : 'level'}-${item.frequency || 'annual'}`;
  const seriesQ = useWorldIndicatorData(slug, item.indicator_code, mode);
  const spark = useMemo(
    () => (seriesQ.data?.points || []).map((point) => Number(point.value)).filter(Number.isFinite).slice(-36),
    [seriesQ.data],
  );
  const unit = splitUnit(localizeWorldUnit(item.unit, locale));
  // «изменение за год, %» уже сказано в названии («… за год») — не повторяем в подписи периода.
  const longUnit = unit.long && unit.long !== unit.short && !/за год|year[- ]over[- ]year|yoy/i.test(unit.long)
    ? unit.long
    : '';
  const fullName = localizedDisplay(locale, item.name, item.name_en);
  // Короткое человеческое имя («Инфляция», «Баланс бюджета») вместо длинного официального названия.
  const kpiName = homeConceptLabel(item.concept_slug, t, fullName);
  const digits = kpiDigits(item.value);
  const format = (value) => formatWorldValue(value, digits, locale);
  return (
    <Link
      to={indicatorPath(slug, item.indicator_code)}
      className={`w2-kpi fe-press group${hero ? ' w2-kpi--hero' : ''}`}
    >
      <span className="w2-kpi-name" title={fullName}>{kpiName}</span>
      <span className="w2-kpi-value">
        <WorldCountUp value={item.value} format={format} />
        {unit.short && <small>{unit.short}</small>}
      </span>
      <span className="w2-kpi-period">
        {formatIndicatorDate(item.date, item.frequency, locale)}
        {longUnit ? `, ${longUnit}` : ''}
      </span>
      <span className="w2-kpi-spark" aria-hidden="true">
        {seriesQ.isLoading
          ? <SparklineSkeleton height={hero ? 52 : 40} />
          : (spark.length > 1
            ? <Sparkline points={spark} trend="flat" sentiment="neutral" height={hero ? 52 : 40} />
            : (
              <span className="w2-kpi-nospark">
                <Spline size={14} aria-hidden="true" />
                {t('w6b.country.noChart')}
              </span>
            ))}
      </span>
    </Link>
  );
}

/**
 * Частота плитки — самая детальная из доступных: месячные данные показывают
 * «мес.», квартальные (без месячных) — «кв.», только годовые — «год».
 * Если частот несколько, остальные перечислены в подсказке бейджа.
 */
const FREQ_BADGE_PRIORITY = ['daily', 'weekly', 'monthly', 'quarterly', 'annual'];

function FreqBadges({ item, t }) {
  const officialFreqs = Array.isArray(item.frequencies)
    ? item.frequencies.map((f) => (typeof f === 'string' ? f : f.freq)).filter(Boolean)
    : (item.frequency ? [item.frequency] : []);
  const aggregated = Array.isArray(item.aggregated_frequencies)
    ? item.aggregated_frequencies.filter((f) => f && !officialFreqs.includes(f))
    : [];
  if (!officialFreqs.length && !aggregated.length) return null;

  const toLabel = (f) => {
    const key = `world.freq.${f}`;
    const label = t(key);
    return label !== key ? label : f;
  };

  const byPriority = (freqs) => FREQ_BADGE_PRIORITY.filter((f) => freqs.includes(f));
  const shown = byPriority([...officialFreqs, ...aggregated]);
  if (!shown.length) return null;
  const primary = shown[0];
  const primaryIsAggregated = !officialFreqs.includes(primary);
  // Официальный годовой ряд: дата «2025» и так говорит «раз в год»; лишний чип «год» только рвёт строку.
  if (primary === 'annual' && !primaryIsAggregated) return null;
  const restLabels = shown.slice(1).map(
    (f) => `${officialFreqs.includes(f) ? '' : '~'}${toLabel(f)}`,
  );
  const title = restLabels.length
    ? `${primaryIsAggregated ? '~' : ''}${toLabel(primary)}; также: ${restLabels.join(', ')}`
    : undefined;

  return (
    <span
      title={title}
      className={
        'cursor-help rounded-full bg-obsidian-light px-2 py-0.5'
        + (primaryIsAggregated ? ' opacity-60' : '')
      }
    >
      {primaryIsAggregated ? '~' : ''}{toLabel(primary)}
    </span>
  );
}

function IndicatorRow({ item, slug, to, sectionName }) {
  const t = useT();
  const { locale } = useLocale();
  const unit = localizeWorldUnit(item.unit, locale);
  // Единица показана под названием: в самом названии («..., человек») её не повторяем.
  const name = dropRepeatedUnit(shortUsIndicatorName(indicatorPublicName(item, locale), sectionName, locale), unit);
  return (
    <Link
      to={to || indicatorPath(slug, item.code)}
      className="group flex flex-col gap-2 rounded-xl border border-border-subtle bg-white px-3.5 py-3 transition-all hover:border-border-champagne hover:shadow-[0_12px_30px_rgba(35,30,16,0.06)] sm:min-h-[84px] sm:flex-row sm:items-center sm:gap-3 sm:px-4 sm:py-3.5"
    >
      <div className="min-w-0 flex-1">
        <div className="break-words text-[13px] leading-snug text-text-primary transition-colors group-hover:text-champagne sm:text-[14px]">
          {name}
        </div>
        <div className="mt-1 flex min-w-0 flex-wrap items-center gap-1.5 text-xs text-text-tertiary sm:mt-1.5">
          <FreqBadges item={item} t={t} />
          {unit && <span className="min-w-0 break-words">{unit}</span>}
        </div>
      </div>
      <div className="flex items-baseline justify-between gap-3 border-t border-border-subtle/60 pt-2 sm:w-[7.5rem] sm:shrink-0 sm:flex-col sm:items-end sm:justify-center sm:border-0 sm:pt-0 sm:text-right">
        <div className="text-[15px] font-semibold tabular-nums text-text-primary sm:text-[14px] sm:font-medium">
          {formatWorldValue(item.last_value, undefined, locale)}
        </div>
        <div className="flex items-center gap-1.5">
          <CompactChange change={item.change} label={indicatorPublicName(item, locale)} locale={locale} />
          <span className="text-xs text-text-tertiary">
            {formatIndicatorDate(item.last_date, item.frequency, locale)}
          </span>
        </div>
      </div>
    </Link>
  );
}

/** Несколько близких показателей («Число родившихся» в трёх разрезах) одной свёрнутой строкой. */
function IndicatorGroup({ group, slug, sectionName }) {
  const t = useT();
  const { locale } = useLocale();
  const n = group.items.length;
  const word = locale === 'en'
    ? t('w6b.country.cuts_many')
    : pluralRu(n, [t('w6b.country.cuts_one'), t('w6b.country.cuts_few'), t('w6b.country.cuts_many')]);
  return (
    <details className="fe-ind-group md:col-span-2">
      <summary className="fe-ind-group__summary">
        <span className="fe-ind-group__name">{group.base}</span>
        <span className="fe-ind-group__count">{n} {word}</span>
        <ChevronDown size={16} aria-hidden="true" className="fe-ind-group__chevron" />
      </summary>
      <div className="mt-2 grid gap-2 md:grid-cols-2">
        {group.items.map((ind) => (
          <IndicatorRow key={ind.code} item={ind} slug={slug} sectionName={sectionName} />
        ))}
      </div>
    </details>
  );
}

/** Строки категории: почти-дубли свёрнуты, остальные показатели идут как есть. */
function IndicatorRows({ items, slug, sectionName, locale, collapse }) {
  const rows = useMemo(
    () => (collapse
      ? groupNearDuplicates(items, (item) => indicatorPublicName(item, locale))
      : items.map((item) => ({ kind: 'single', item }))),
    [items, locale, collapse],
  );
  return rows.map((row) => (row.kind === 'group'
    ? <IndicatorGroup key={`g-${row.items[0].code}`} group={row} slug={slug} sectionName={sectionName} />
    : <IndicatorRow key={row.item.code} item={row.item} slug={slug} sectionName={sectionName} />));
}

/** «The economy of the United States»: у нескольких стран английское название идёт с артиклем. */
function withEnglishArticle(name) {
  return /^(United States|United Kingdom|Netherlands)$/i.test(String(name || '').trim()) ? `the ${name}` : name;
}

export default function WorldCountry() {
  const t = useT();
  const { locale } = useLocale();
  const { countrySlug, slug: slugParam } = useParams();
  const slug = countrySlug || slugParam;
  const { data, isLoading, isError, refetch, isFetching, error } = useWorldCountry(slug);
  const [query, setQuery] = useState('');
  const [searchLimit, setSearchLimit] = useState(120);
  const [catalogLimits, setCatalogLimits] = useState({});
  const [activeCategory, setActiveCategory] = useState('');
  const [isMobileSingle, setIsMobileSingle] = useState(
    () => typeof window !== 'undefined' && window.matchMedia
      ? !window.matchMedia('(min-width: 1024px)').matches
      : false,
  );
  usePageLoading(isLoading);
  const slowLoading = useSlowFlag(isLoading, 5000);
  const deferredQuery = useDeferredValue(query);
  const searching = normalize(deferredQuery).length > 0;

  const countryName = countryPublicName(data?.country, locale);
  const notFound = isError && error?.response?.status === 404;

  const countryMeta = useMemo(() => {
    if (!countryName || !data) return null;
    const flat = (data.categories || []).flatMap((c) => c.indicators || []);
    const total = flat.length || Number(data.indicators_count) || 0;
    const hasNational = flat.some((ind) => {
      const prov = String(ind.provider || '').trim().toLowerCase();
      return prov && prov !== 'eurostat';
    });
    const sources = [...new Set(
      flat.map((ind) => ind.source).filter(Boolean),
    )].map((src) => localizeSource(src, locale));
    const conj = locale === 'en' ? ' and ' : ' и ';
    let sourcePhrase = locale === 'en' ? 'Eurostat' : 'Евростат';
    if (sources.length === 1) sourcePhrase = sources[0];
    else if (sources.length === 2) sourcePhrase = `${sources[0]}${conj}${sources[1]}`;
    else if (sources.length > 2) {
      sourcePhrase = `${sources.slice(0, -1).join(', ')}${conj}${sources[sources.length - 1]}`;
    }
    const title = worldCountryTitle(slug, countryName, locale);
    return {
      title,
      description: worldCountryDescription(slug, countryName, total, {
        hasNational,
        sourcePhrase,
        locale,
      }),
      h1: title,
    };
  }, [countryName, data, slug, locale]);

  useDocumentMeta(countryMeta ? {
    title: countryMeta.title,
    description: countryMeta.description,
    path: countryPath(slug),
  } : null);

  useEffect(() => {
    if (!countryName) return undefined;
    return mountJsonLd(breadcrumbJsonLd(worldCountryTrail(countryName, slug)));
  }, [countryName, slug]);

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)');
    const onChange = () => setIsMobileSingle(!mq.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  const catalogCategories = useMemo(() => {
    const mapped = (data?.categories || []).map((cat) => {
      const indicators = collapseCountryIndicators(cat.indicators || []);
      return {
        ...cat,
        indicators,
        count: indicators.length,
      };
    });
    // Каталог США своей навигацией по темам; остальные страны — главные темы первыми, остальное по алфавиту.
    return slug === 'united-states'
      ? mapped
      : [...mapped].sort((a, b) => (
        Number(a.count < THIN_TOPIC) - Number(b.count < THIN_TOPIC) || topicRank(a) - topicRank(b)
      ));
  }, [data, slug]);

  const filteredCategories = useMemo(() => {
    const q = normalize(deferredQuery);
    if (!q) return catalogCategories;
    return catalogCategories
      .map((cat) => ({
        ...cat,
        indicators: filterSearchOptions(cat.indicators, q, {
          getSearchItem: (item) => ({
            ...item,
            search_label: indicatorPublicName(item, locale),
            category: cat.name,
            country_slug: slug,
            country_name: countryName,
            search_codes: (item._freqMembers || []).map((member) => member.code).filter(Boolean),
            search_frequencies: (item.frequencies || []).map((frequency) => typeof frequency === 'string' ? frequency : frequency.freq),
          }),
        }),
      }))
      .filter((cat) => cat.indicators.length > 0)
      .map((cat) => ({ ...cat, count: cat.indicators.length }));
  }, [catalogCategories, deferredQuery, locale, slug, countryName]);

  const totalIndicators = useMemo(
    () => catalogCategories.reduce((n, cat) => n + cat.indicators.length, 0),
    [catalogCategories],
  );

  // «Сравнить с Россией»: первый главный показатель страны, который есть и у России (честная сопоставимость).
  const russiaCompareHref = useMemo(() => {
    const pick = (data?.overview || []).find((item) => HOME_MAP_RUSSIA_CONCEPT_CODES[item.concept_slug]);
    return pick ? `/compare?codes=w:${slug}:${pick.concept_slug},w:russia:${pick.concept_slug}` : '';
  }, [data, slug]);

  const isUsCatalog = slug === 'united-states';
  const usTopics = useMemo(
    () => isUsCatalog ? groupUsSections(filteredCategories, locale) : [],
    [filteredCategories, isUsCatalog, locale],
  );

  const matchCount = useMemo(
    () => filteredCategories.reduce((n, c) => n + c.indicators.length, 0),
    [filteredCategories],
  );

  useSearchTracking('world-country-indicators', deferredQuery, matchCount);

  const resolvedActiveCategory = filteredCategories.some((cat) => cat.name === activeCategory)
    ? activeCategory
    : ((isUsCatalog ? usTopics[0]?.sections[0] : filteredCategories[0])?.name || '');
  const activeUsTopic = usTopics.find((topic) => topic.sections.some((cat) => cat.name === resolvedActiveCategory));
  const selectCategory = (name) => {
    setActiveCategory(name);
  };
  const selectUsTopic = (id) => {
    const first = usTopics.find((topic) => topic.id === id)?.sections[0];
    if (first) selectCategory(first.name);
  };
  const denseCatalog = totalIndicators > 200;
  const initialCategoryLimit = (isMobileSingle || isUsCatalog) ? 120 : 40;
  let remaining = searchLimit;
  const visibleCategories = searching
    ? ((isUsCatalog || denseCatalog) ? filteredCategories.map((cat) => {
      const indicators = cat.indicators.slice(0, remaining);
      remaining -= indicators.length;
      return { ...cat, indicators };
    }).filter((cat) => cat.indicators.length > 0) : filteredCategories)
    : (isMobileSingle || (isUsCatalog && denseCatalog)
      ? filteredCategories.filter((cat) => cat.name === resolvedActiveCategory)
      : filteredCategories).map((cat) => (isMobileSingle || denseCatalog
      ? {
        ...cat,
        indicators: cat.indicators.slice(
          0,
          catalogLimits[`${slug}:${cat.name}`] || initialCategoryLimit,
        ),
      }
      : cat));

  useEffect(() => {
    if (searching || isMobileSingle || (isUsCatalog && denseCatalog) || filteredCategories.length < 2) return undefined;
    let frame = 0;
    const syncActive = () => {
      frame = 0;
      const sections = document.querySelectorAll('[data-world-country-category]');
      let current = sections[0]?.dataset.worldCountryCategory;
      for (const section of sections) {
        if (section.getBoundingClientRect().top > 150) break;
        current = section.dataset.worldCountryCategory;
      }
      if (current) setActiveCategory((previous) => previous === current ? previous : current);
    };
    const schedule = () => {
      if (!frame) frame = window.requestAnimationFrame(syncActive);
    };
    schedule();
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    return () => {
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [filteredCategories, searching, isMobileSingle, isUsCatalog, denseCatalog]);

  // Несуществующий адрес страны — общая страница 404 (та же оболочка, поиск и популярные разделы).
  if (notFound) return <NotFound />;

  return (
    <div className="fe-data-page mx-auto w-full max-w-7xl overflow-x-clip px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs items={worldCountryTrail(countryName || '…', slug)} />

      {isError && !notFound && (
        <ApiRetryBanner onRetry={refetch} isFetching={isFetching} className="mb-6">
          {t('world.country.loadError')}
        </ApiRetryBanner>
      )}

      {isLoading && (
        <div className="space-y-5" role="status" aria-busy="true" aria-label={t('common.loading')} data-testid="country-skeleton">
          <SkeletonBox className="h-4 w-28" />
          <SkeletonBox className="h-9 w-3/4 max-w-md" />
          <div className="space-y-2">
            <SkeletonBox className="h-4 w-full max-w-xl" />
            <SkeletonBox className="h-4 w-2/3 max-w-md" />
          </div>
          <SkeletonBox className="h-12 w-full rounded-xl sm:w-60" />
          <SkeletonBox className="h-32 w-full rounded-3xl" />
          <div className="fe-kpi-grid">
            {[0, 1, 2].map((i) => <SkeletonBox key={i} className="h-[104px] rounded-3xl sm:h-44" />)}
          </div>
          <SkeletonBox className="h-12 w-full rounded-xl" />
          <SkeletonBox className="h-14 w-full rounded-xl" />
          {slowLoading && <p className="fe-slow-hint">{t('z1.country.slowLoading')}</p>}
        </div>
      )}

      {data && (
        <>
          <div className="fe-data-header">
            <div className="w2-kicker mb-2 flex items-center gap-2">
              <CountryFlag code={data.country.code} className="w2-kicker-flag" />
              {localizedDisplay(locale, data.country.region, data.country.region_en)}
            </div>
            <div className="grid gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(260px,0.7fr)] lg:items-start lg:gap-7">
              <div>
                <h1 className="font-display text-[1.65rem] font-bold leading-tight text-text-primary sm:text-4xl">
                  {locale === 'en' && countryName ? `The economy of ${withEnglishArticle(countryName)}` : (countryMeta?.h1 || countryName)}
                </h1>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-text-secondary sm:text-base">
                  {t('w2.country.lead', { country: countryName })}
                </p>
                <Button
                  as={Link}
                  to={data.overview?.[0]
                    ? `/compare?codes=w:${slug}:${data.overview[0].concept_slug}`
                    : '/compare'}
                  className="mt-4 w-full sm:w-auto"
                >
                  <BarChart3 size={15} aria-hidden="true" />
                  {t('world.country.compareCta')}
                  <ArrowUpRight size={14} aria-hidden="true" />
                </Button>
                {slug !== 'russia' && russiaCompareHref ? (
                  <Button
                    as={Link}
                    to={russiaCompareHref}
                    variant="secondary"
                    className="mt-3 w-full sm:ml-3 sm:mt-4 sm:w-auto"
                  >
                    <Scale size={15} aria-hidden="true" />
                    {t('w6b.country.compareRussia')}
                  </Button>
                ) : null}
              </div>
              <CountrySilhouette
                code={data.country.code}
                name={countryName}
                slug={slug}
                area={data.area}
                population={data.population}
              />
            </div>

            <h2 className="w2-main-title mt-6">{t('w6b.country.main')}</h2>
            <div id="chart" className="fe-kpi-grid mt-3 scroll-mt-28">
              {(data.overview || []).slice(0, 3).map((item, index) => (
                <CountryKpiCard key={item.concept_slug} item={item} slug={slug} hero={index === 0} locale={locale} />
              ))}
              {!data.overview?.length && (
                <div className="col-span-2 text-sm text-text-secondary sm:col-span-3">
                  {t('world.country.coverageAlt')}
                </div>
              )}
            </div>
          </div>

          {data.country?.has_regions && (
            <Link
              to={countryRegionsPath(slug)}
              className="fe-panel mb-8 flex items-center justify-between gap-4 rounded-xl border border-border-subtle bg-surface px-5 py-4 transition-colors hover:border-border-champagne"
            >
              <div>
                <div className="w2-kicker">
                  {t('world.regions.cardKicker')}
                </div>
                <div className="mt-1 font-display text-xl font-bold text-text-primary">
                  {data.country.region_kind_label_plural || t('world.regions.cardTitle')}
                </div>
                <p className="mt-1 text-sm text-text-secondary">
                  {t('world.regions.cardBody')}
                </p>
              </div>
              <span className="shrink-0 rounded-full bg-champagne/15 px-3 py-1.5 text-sm text-champagne-ink">
                {t('world.regions.open')}
              </span>
            </Link>
          )}

          <div className="relative mb-6">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-tertiary" />
            <input
              type="search"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setSearchLimit(120); }}
              placeholder={t('world.country.findIndicator')}
              aria-label={t('world.country.findIndicatorAria')}
              className="w-full rounded-xl border border-border-subtle bg-surface py-3 pl-10 pr-4 text-sm text-text-primary shadow-sm placeholder:text-text-tertiary focus:border-border-champagne focus:outline-none"
            />
          </div>

          {filteredCategories.length === 0 && (
            <div className="rounded-2xl border border-border-subtle bg-surface p-6 text-center text-sm text-text-secondary">
              {searching ? (
                <>
                  {t('world.country.emptySearch', { query })}
                  {' '}
                  <Button variant="ghost" size="sm" onClick={() => { setQuery(''); setSearchLimit(120); }} className="px-2">
                    {t('world.country.emptySearchReset')}
                  </Button>
                </>
              ) : (
                <>
                  {t('world.country.emptyCatalog')}
                  {' '}
                  <Link to="/#countries" className="inline-flex items-center text-champagne-ink hover:underline pointer-coarse:min-h-11">
                    {t('world.country.toCountries')}
                  </Link>
                </>
              )}
            </div>
          )}

          {!searching && !isUsCatalog && (
            <MobileNavSelect
              label={t('world.country.themes')}
              value={resolvedActiveCategory}
              onChange={selectCategory}
              options={filteredCategories.map((cat) => ({
                value: cat.name,
                label: localizedDisplay(locale, cat.name, cat.name_en),
                count: formatCount(cat.indicators.length, locale),
              }))}
            />
          )}

          <div className={searching
            ? 'min-w-0 space-y-8'
            : 'grid min-w-0 gap-6 lg:grid-cols-[250px_minmax(0,1fr)]'}
          >
            {!searching && isUsCatalog && (
              <UsCatalogNav
                topics={usTopics}
                activeTopic={activeUsTopic?.id}
                activeSection={resolvedActiveCategory}
                onTopic={selectUsTopic}
                onSection={selectCategory}
                sectionKey={(cat) => cat.name}
                sectionLabel={(cat) => localizedDisplay(locale, cat.name, cat.name_en)}
                themesLabel={t('world.country.themes')}
                detailLabel={locale === 'en' ? 'Detailed topics' : 'Подробные темы'}
              />
            )}
            {!searching && !isUsCatalog && (
              <aside className="hidden min-w-0 lg:sticky lg:top-24 lg:block lg:max-h-[calc(100vh-7rem)] lg:self-start lg:overflow-y-auto">
                <div className="mb-2 px-2 text-[13px] font-semibold text-text-secondary">
                  {t('world.country.themes')}
                </div>
                <div className="flex flex-col gap-2">
                  {filteredCategories.map((cat) => (
                    <Chip
                      key={cat.name}
                      active={resolvedActiveCategory === cat.name}
                      onClick={() => {
                        selectCategory(cat.name);
                        document.querySelectorAll('[data-world-country-category]')
                          .forEach((section) => {
                            if (section.dataset.worldCountryCategory === cat.name) {
                              section.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
                            }
                          });
                      }}
                      aria-current={resolvedActiveCategory === cat.name ? 'true' : undefined}
                      className="w-full justify-between! gap-4 px-3.5 py-2.5 text-left text-sm!"
                    >
                      <span className="min-w-0 truncate">{localizedDisplay(locale, cat.name, cat.name_en)}</span>
                      <span className="shrink-0 text-xs tabular-nums opacity-70">{formatCount(cat.indicators.length, locale)}</span>
                    </Chip>
                  ))}
                </div>
              </aside>
            )}

            <div className="min-w-0 space-y-8">
              {visibleCategories.map((cat) => (
                <section key={cat.name} className="scroll-mt-24" data-world-country-category={cat.name}>
                  <div className={`mb-3 flex items-end justify-between gap-3 sm:mb-4 sm:gap-4${isMobileSingle && !searching && !isUsCatalog ? ' sr-only' : ''}`}>
                    <div className="min-w-0">
                      {searching && (
                        <div className="w2-kicker">
                          {t('regions.searchResults')}
                        </div>
                      )}
                      <h2 className="font-display text-xl font-bold leading-snug text-text-primary sm:text-2xl">{localizedDisplay(locale, cat.name, cat.name_en)}</h2>
                    </div>
                    <span className="shrink-0 text-sm tabular-nums text-text-tertiary">{formatCount(cat.count ?? cat.indicators.length, locale)}</span>
                  </div>
                  <div className="grid gap-2 sm:gap-2.5 md:grid-cols-2">
                    <IndicatorRows
                      items={cat.indicators}
                      slug={slug}
                      sectionName={isUsCatalog ? cat.name_ru : undefined}
                      locale={locale}
                      collapse={!isUsCatalog && !searching}
                    />
                  </div>
                  {!searching && (isMobileSingle || denseCatalog) && cat.count > cat.indicators.length && (
                    <Button
                      variant="secondary"
                      onClick={() => setCatalogLimits((current) => ({
                        ...current,
                        [`${slug}:${cat.name}`]: (current[`${slug}:${cat.name}`] || initialCategoryLimit) + 120,
                      }))}
                      className="mt-4 rounded-full! px-5"
                    >
                      {locale === 'en' ? 'Show more indicators' : 'Показать ещё показатели'}
                      {locale === 'en' ? ' of ' : ' из '}
                      {cat.indicators.length} / {cat.count}
                    </Button>
                  )}
                </section>
              ))}
            </div>
          </div>
          {(data.market_indicators || []).length > 0 && (
            <section className="mt-10" data-testid="country-market-indicators">
              <div className="mb-3 flex items-end justify-between gap-3 sm:mb-4 sm:gap-4">
                <div className="min-w-0">
                  <h2 className="font-display text-xl font-bold leading-snug text-text-primary sm:text-2xl">
                    {t('world.country.markets')}
                  </h2>
                </div>
                <span className="shrink-0 text-sm text-text-tertiary">
                  {data.market_indicators.length}
                </span>
              </div>
              <div className="grid gap-2 sm:gap-2.5 md:grid-cols-2">
                {data.market_indicators.map((ind) => (
                  <IndicatorRow
                    key={ind.code}
                    item={ind}
                    slug={slug}
                    to={russiaIndicatorPath(ind.code)}
                  />
                ))}
              </div>
            </section>
          )}

          {(isUsCatalog || denseCatalog) && searching && matchCount > searchLimit && (
            <Button
              variant="secondary"
              onClick={() => setSearchLimit((current) => current + 120)}
              className="mt-5 rounded-full! px-5"
            >
              {locale === 'en' ? 'Show more indicators' : 'Показать ещё показатели'}
              {locale === 'en' ? ' of ' : ' из '}
              {Math.min(searchLimit, matchCount)} / {matchCount}
            </Button>
          )}
        </>
      )}
    </div>
  );
}
