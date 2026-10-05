// Страница страны: /world/{slug}
// Темы слева + сетка показателей; поиск не ломает сетку.
import NotFound from './NotFound';
import {
  useEffect, useMemo, useState, useDeferredValue,
} from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import {
  Search, BarChart3, ArrowUpRight, Scale,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  worldCountryDescription,
  worldCountryTitle,
} from '../lib/pageMeta';
import {
  useWorldCountry, useWorldCountries, useCachedWorldCountry,
} from '../lib/worldApi';
import {
  collapseCountryIndicators, indicatorPublicName, localizedDisplay,
} from '../lib/worldViewModes';
import { formatCount } from '../lib/format';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Button from '../components/Button';
import CountryFlag from '../components/CountryFlag';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import LoadingNote from '../components/LoadingNote';
import MobileNavSelect from '../components/MobileNavSelect';
import UsCatalogNav from '../components/UsCatalogNav';
import CountryKeyFigures, { KEY_FIGURES_MAX } from '../components/country/CountryKeyFigures';
import CountryTopicNav, { GdpForecastCard, SimilarCountries } from '../components/country/CountryTopicNav';
import { IndicatorRow, IndicatorRows } from '../components/country/CountryIndicatorRow';
import { SparkBudgetContext, createSparkBudget } from '../components/country/sparkBudget';
import { groupUsSections } from '../lib/usCatalogTopics';
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
  russiaIndicatorPath,
} from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import { localizeSource } from '../i18n/viewModeLabels';
import { countryPublicName, HOME_MAP_RUSSIA_CONCEPT_CODES } from '../lib/homeWorkbench';
import { indicatorsCountText, similarCountries, topicDisplayName } from '../lib/countryKeyFigures';
import { readCountryBootstrap } from '../lib/countryBootstrap';
import '../styles/world.css';
import '../styles/x2-indicator.css';
import '../styles/z1-polish.css';
import '../styles/z5-country.css';
import usePageLoading from '../lib/usePageLoading';

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

/** Сколько мини-графиков в строках списка загружается за один визит: сайт не должен «душить» себя запросами. */
const SPARK_BUDGET = 36;

function normalize(s) {
  return (s || '').toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ').trim();
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
  const deferredQuery = useDeferredValue(query);
  const searching = normalize(deferredQuery).length > 0;

  const countryName = countryPublicName(data?.country, locale);
  // Название и флаг из каталога стран, который уже в кэше: человек видит страну сразу после нажатия.
  const cachedCountry = useCachedWorldCountry(slug);
  // Серверная предзагрузка «Главного» (#fe-country-bootstrap): название страны и четыре карточки до ответа API.
  const preload = useMemo(() => readCountryBootstrap(slug, locale), [slug, locale]);
  const previewCountry = cachedCountry || preload?.country || null;
  const previewName = countryPublicName(previewCountry, locale);
  // Переход по крошке с карточки показателя: название страны уже известно и стоит в крошках сразу, пока грузятся данные.
  const crumbNameFromLink = useLocation().state?.crumbName;
  const notFound = isError && error?.response?.status === 404;
  // Каталог стран нужен только для «Похожих стран»: из кэша берётся сразу, иначе грузится после основных данных.
  const [catalogWanted, setCatalogWanted] = useState(false);
  const hasData = !!data;
  useEffect(() => {
    if (!hasData) return undefined;
    const timer = window.setTimeout(() => setCatalogWanted(true), 600);
    return () => window.clearTimeout(timer);
  }, [hasData]);
  const catalogQ = useWorldCountries({ enabled: catalogWanted });
  const similar = useMemo(
    () => similarCountries(catalogQ.data, data?.country || cachedCountry),
    [catalogQ.data, data, cachedCountry],
  );
  const gdpItem = useMemo(
    () => (data?.overview || []).find((item) => /^gdp-/.test(item.concept_slug)) || null,
    [data],
  );
  // Новая страна: новый бюджет мини-графиков.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const sparkBudget = useMemo(() => createSparkBudget(SPARK_BUDGET), [slug]);

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
  const heroOverview = useMemo(() => data?.overview || preload?.overview || [], [data, preload]);
  const russiaCompareHref = useMemo(() => {
    const pick = heroOverview.find((item) => HOME_MAP_RUSSIA_CONCEPT_CODES[item.concept_slug]);
    return pick ? `/compare?codes=w:${slug}:${pick.concept_slug},w:russia:${pick.concept_slug}` : '';
  }, [heroOverview, slug]);

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

  // Кнопки героя одинаковы до и после ответа API: «Главное» из предзагрузки даёт их сразу.
  const heroActions = (
    <div className="z5-hero__actions">
      <Button
        as={Link}
        to={heroOverview[0] ? `/compare?codes=w:${slug}:${heroOverview[0].concept_slug}` : '/compare'}
        className="w-full sm:w-auto"
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
          className="w-full sm:w-auto"
        >
          <Scale size={15} aria-hidden="true" />
          {t('w6b.country.compareRussia')}
        </Button>
      ) : null}
    </div>
  );

  // Несуществующий адрес страны — общая страница 404 (та же оболочка, поиск и популярные разделы).
  if (notFound) return <NotFound />;

  return (
    <div className="fe-data-page z5-page mx-auto w-full max-w-7xl overflow-x-clip px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs items={worldCountryTrail(countryName || previewName || crumbNameFromLink || '…', slug)} />

      {isError && !notFound && (
        <ApiRetryBanner onRetry={refetch} isFetching={isFetching} className="mb-6">
          {t('world.country.loadError')}
        </ApiRetryBanner>
      )}

      {isLoading && (
        <div
          className="fe-data-header z5-hero z5-hero--loading"
          role="status"
          aria-busy="true"
          aria-label={t('common.loading')}
          data-testid="country-skeleton"
        >
          <div className="z5-hero__grid">
            <div className="z5-hero__lead">
              {previewName ? (
                <div data-testid="country-preview">
                  <div className="w2-kicker mb-2 flex items-center gap-2">
                    <CountryFlag code={previewCountry.code} className="w2-kicker-flag" />
                    {localizedDisplay(locale, previewCountry.region, previewCountry.region_en)}
                  </div>
                  <h1 className="z5-hero__title font-display font-bold text-text-primary">
                    {worldCountryTitle(slug, previewName, locale)}
                  </h1>
                  <p className="z5-hero__text text-text-secondary">
                    {t('w2.country.lead', { country: previewName })}
                  </p>
                </div>
              ) : (
                <>
                  <SkeletonBox className="mb-3 h-4 w-28" />
                  <SkeletonBox className="mb-4 h-12 w-3/4 max-w-md" />
                  <div className="space-y-2">
                    <SkeletonBox className="h-4 w-full max-w-xl" />
                    <SkeletonBox className="h-4 w-2/3 max-w-md" />
                  </div>
                </>
              )}
              {preload ? heroActions : (
                <div className="z5-hero__actions">
                  <SkeletonBox className="h-11 w-52 rounded-xl" />
                  <SkeletonBox className="h-11 w-44 rounded-xl" />
                </div>
              )}
            </div>
            <div className="z5-hero__profile z5-profile-skel" aria-hidden="true" />
          </div>
          <h2 className="w2-main-title z5-main-title" aria-hidden="true">{t('w6b.country.main')}</h2>
          {preload ? (
            <CountryKeyFigures
              items={preload.overview.slice(0, KEY_FIGURES_MAX)}
              slug={slug}
              locale={locale}
              preload={preload}
            />
          ) : (
            <div className="z5-key-grid z5-key-grid--n3">
              {[0, 1, 2].map((i) => <div key={i} className="z5-key z5-key--skel w2-kpi" aria-hidden="true" />)}
            </div>
          )}
          <LoadingNote onRefresh={() => refetch()} />
        </div>
      )}

      {data && (
        <>
          <div className="fe-data-header z5-hero">
            <div className="z5-hero__grid">
              <div className="z5-hero__lead">
                <div className="w2-kicker mb-2 flex items-center gap-2">
                  <CountryFlag code={data.country.code} className="w2-kicker-flag" />
                  {localizedDisplay(locale, data.country.region, data.country.region_en)}
                </div>
                <h1 className="z5-hero__title font-display font-bold text-text-primary">
                  {locale === 'en' && countryName ? `The economy of ${withEnglishArticle(countryName)}` : (countryMeta?.h1 || countryName)}
                </h1>
                <p className="z5-hero__text text-text-secondary">
                  {t('w2.country.lead', { country: countryName })}
                </p>
                {heroActions}
              </div>
              <div className="z5-hero__profile">
                <CountrySilhouette
                  code={data.country.code}
                  name={countryName}
                  slug={slug}
                  area={data.area}
                  population={data.population}
                  className="z5-profile"
                  badge={(
                    <span className="z5-flag-badge">
                      <CountryFlag code={data.country.code} />
                      <span>{countryName}</span>
                    </span>
                  )}
                />
              </div>
            </div>

            <h2 className="w2-main-title z5-main-title">{t('w6b.country.main')}</h2>
            <CountryKeyFigures
              items={(data.overview || []).slice(0, KEY_FIGURES_MAX)}
              slug={slug}
              locale={locale}
              preload={preload}
            />
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

          <div className="z5-search relative mb-6">
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
                label: topicDisplayName(cat, locale),
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
                detailLabel={t('z5.topics.more')}
              />
            )}
            {!searching && !isUsCatalog && (
              <CountryTopicNav
                categories={filteredCategories}
                active={resolvedActiveCategory}
                locale={locale}
                onPick={(name) => {
                  selectCategory(name);
                  document.querySelectorAll('[data-world-country-category]')
                    .forEach((section) => {
                      if (section.dataset.worldCountryCategory === name) {
                        section.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
                      }
                    });
                }}
              >
                <GdpForecastCard slug={slug} item={gdpItem} />
                <SimilarCountries countries={similar} locale={locale} />
              </CountryTopicNav>
            )}

            <SparkBudgetContext.Provider value={sparkBudget}>
            <div className="z5-catalog min-w-0 space-y-8">
              {visibleCategories.map((cat) => (
                <section key={cat.name} className="z5-section scroll-mt-24" data-world-country-category={cat.name}>
                  <div className={`mb-3 flex items-end justify-between gap-3 sm:mb-4 sm:gap-4${isMobileSingle && !searching && !isUsCatalog ? ' sr-only' : ''}`}>
                    <div className="min-w-0">
                      {searching && (
                        <div className="w2-kicker">
                          {t('regions.searchResults')}
                        </div>
                      )}
                      <h2 className="z5-section-title font-display font-bold text-text-primary">{topicDisplayName(cat, locale)}</h2>
                    </div>
                    <span className="z5-section-count">{indicatorsCountText(cat.count ?? cat.indicators.length, locale, t)}</span>
                  </div>
                  <div className="z5-rows">
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
            </SparkBudgetContext.Provider>
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
              <div className="z5-rows">
                {data.market_indicators.map((ind) => (
                  <IndicatorRow
                    key={ind.code}
                    item={ind}
                    slug={slug}
                    to={russiaIndicatorPath(ind.code)}
                    sparkEnabled={false}
                  />
                ))}
              </div>
            </section>
          )}

          <SimilarCountries countries={similar} locale={locale} className="z5-similar--page" />

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
