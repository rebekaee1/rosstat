// Страница страны: /world/{slug}
// Темы слева + сетка показателей; поиск не ломает сетку.
import { useEffect, useMemo, useState, useDeferredValue } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ChevronRight, Search, Globe2, BarChart3, ArrowUpRight,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  worldCountryDescription,
  worldCountryTitle,
} from '../lib/pageMeta';
import {
  useWorldCountry, formatWorldValue, pluralRu, localizeWorldUnit,
} from '../lib/worldApi';
import {
  collapseCountryIndicators, indicatorPublicName, localizedDisplay,
} from '../lib/worldViewModes';
import { formatChange, formatDate } from '../lib/format';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import MobileNavSelect from '../components/MobileNavSelect';
import UsCatalogNav from '../components/UsCatalogNav';
import { groupUsSections, shortUsIndicatorName } from '../lib/usCatalogTopics';
import useSearchTracking from '../lib/useSearchTracking';
import { CountrySilhouette } from '../components/WorldMap';
import {
  breadcrumbJsonLd,
  worldCountryTrail,
} from '../lib/breadcrumbs';
import {
  countryPath,
  countryRegionsPath,
  indicatorPath,
  russiaIndicatorPath,
  regionHubPath,
} from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import { localizeSource } from '../i18n/viewModeLabels';
import { countryPublicName } from '../lib/homeWorkbench';

function normalize(s) {
  return (s || '').toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ').trim();
}

function formatIndicatorDate(dateStr, frequency, locale) {
  if (!dateStr) return '—';
  if (frequency === 'annual') return formatDate(dateStr, 'annual', locale);
  if (frequency === 'quarterly') return formatDate(dateStr, 'quarterly', locale);
  return formatDate(dateStr, 'full', locale);
}

function CompactChange({ change }) {
  if (change == null || !Number.isFinite(Number(change)) || Math.abs(Number(change)) < 1e-12) {
    return null;
  }
  const n = Number(change);
  return (
    <span className={`font-mono text-[10px] tabular-nums ${n > 0 ? 'text-positive' : 'text-negative'}`}>
      {formatChange(n)}
    </span>
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
        'cursor-help rounded-full bg-obsidian-light px-2 py-0.5 font-mono'
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
  const name = shortUsIndicatorName(indicatorPublicName(item, locale), sectionName, locale);
  const unit = localizeWorldUnit(item.unit, locale);
  return (
    <Link
      to={to || indicatorPath(slug, item.code)}
      className="group flex flex-col gap-2 rounded-xl border border-border-subtle bg-white px-3.5 py-3 transition-all hover:border-border-champagne hover:shadow-[0_12px_30px_rgba(35,30,16,0.06)] sm:min-h-[92px] sm:flex-row sm:items-center sm:gap-3 sm:px-4 sm:py-3.5"
    >
      <div className="min-w-0 flex-1">
        <div className="break-words text-[13px] leading-snug text-text-primary transition-colors group-hover:text-champagne sm:text-[14px]">
          {name}
        </div>
        <div className="mt-1 flex min-w-0 flex-wrap items-center gap-1.5 text-[10px] text-text-tertiary sm:mt-1.5">
          <FreqBadges item={item} t={t} />
          {unit && <span className="min-w-0 break-words">{unit}</span>}
        </div>
      </div>
      <div className="flex items-baseline justify-between gap-3 border-t border-border-subtle/60 pt-2 sm:w-[7.5rem] sm:shrink-0 sm:flex-col sm:items-end sm:justify-center sm:border-0 sm:pt-0 sm:text-right">
        <div className="font-mono text-[15px] font-semibold tabular-nums text-text-primary sm:text-[14px] sm:font-medium">
          {formatWorldValue(item.last_value, undefined, locale)}
        </div>
        <div className="flex items-center gap-1.5">
          <CompactChange change={item.change} />
          <span className="font-mono text-[10px] text-text-tertiary">
            {formatIndicatorDate(item.last_date, item.frequency, locale)}
          </span>
        </div>
      </div>
    </Link>
  );
}

export default function WorldCountry() {
  const t = useT();
  const { locale } = useLocale();
  const { countrySlug, slug: slugParam } = useParams();
  const slug = countrySlug || slugParam;
  const { data, isLoading, isError, refetch, isFetching, error } = useWorldCountry(slug);
  const [query, setQuery] = useState('');
  const [searchLimit, setSearchLimit] = useState(120);
  const [activeCategory, setActiveCategory] = useState('');
  const [isMobileSingle, setIsMobileSingle] = useState(
    () => typeof window !== 'undefined' && window.matchMedia
      ? !window.matchMedia('(min-width: 1024px)').matches
      : false,
  );
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
  } : (notFound ? {
    title: t('world.country.notFoundTitle'),
    description: t('world.country.notFoundMetaDesc'),
    path: countryPath(slug),
  } : null));

  useEffect(() => {
    if (!countryName) return undefined;
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.id = 'world-country-jsonld';
    script.textContent = JSON.stringify(breadcrumbJsonLd(worldCountryTrail(countryName, slug)));
    document.getElementById('world-country-jsonld')?.remove();
    document.head.appendChild(script);
    return () => script.remove();
  }, [countryName, slug]);

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)');
    const onChange = () => setIsMobileSingle(!mq.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  const filteredCategories = useMemo(() => {
    const cats = data?.categories || [];
    const collapsed = cats.map((cat) => ({
      ...cat,
      indicators: collapseCountryIndicators(cat.indicators || []),
      count: undefined,
    }));
    const withCounts = collapsed.map((cat) => ({
      ...cat,
      count: cat.indicators.length,
    }));
    const q = normalize(deferredQuery);
    if (!q) return withCounts;
    return withCounts
      .map((cat) => ({
        ...cat,
        indicators: cat.indicators.filter((i) =>
          normalize(indicatorPublicName(i, locale)).includes(q)
          || normalize(i.name).includes(q)
          || normalize(i.name_en).includes(q)
          || normalize(i.code).includes(q)),
      }))
      .filter((cat) => cat.indicators.length > 0)
      .map((cat) => ({ ...cat, count: cat.indicators.length }));
  }, [data, deferredQuery, locale]);

  const totalIndicators = useMemo(
    () => (data?.categories || []).reduce(
      (n, c) => n + collapseCountryIndicators(c.indicators || []).length,
      0,
    ),
    [data],
  );

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
  const selectUsTopic = (id) => {
    const first = usTopics.find((topic) => topic.id === id)?.sections[0];
    if (first) setActiveCategory(first.name);
  };
  const denseCatalog = isUsCatalog && totalIndicators > 200;
  let remaining = searchLimit;
  const visibleCategories = searching
    ? (isUsCatalog ? filteredCategories.map((cat) => {
      const indicators = cat.indicators.slice(0, remaining);
      remaining -= indicators.length;
      return { ...cat, indicators };
    }).filter((cat) => cat.indicators.length > 0) : filteredCategories)
    : (isMobileSingle || denseCatalog
      ? filteredCategories.filter((cat) => cat.name === resolvedActiveCategory)
      : filteredCategories);

  useEffect(() => {
    if (searching || isMobileSingle || denseCatalog || filteredCategories.length < 2) return undefined;
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
  }, [filteredCategories, searching, isMobileSingle, denseCatalog]);

  return (
    <div className="fe-data-page mx-auto w-full max-w-7xl overflow-x-clip px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs items={worldCountryTrail(countryName || '…', slug)} />

      {notFound && (
        <div className="mt-8 rounded-2xl border border-border-subtle bg-surface p-8 text-center">
          <h1 className="mb-3 font-display text-2xl font-bold text-text-primary">{t('world.country.notFoundTitle')}</h1>
          <p className="mb-6 text-text-secondary">
            {t('world.country.notFoundBody', { slug })}
          </p>
          <div className="flex flex-wrap justify-center gap-3 text-sm">
            <Link to="/#countries" className="rounded-xl bg-champagne/10 px-4 py-2 text-champagne transition-colors hover:bg-champagne/20">
              {t('world.country.allCountries')}
            </Link>
            <Link to={regionHubPath()} className="rounded-xl border border-border-subtle px-4 py-2 text-text-secondary transition-colors hover:text-champagne">
              {t('world.country.russiaRegions')}
            </Link>
            <Link to="/" className="rounded-xl border border-border-subtle px-4 py-2 text-text-secondary transition-colors hover:text-champagne">
              {t('world.country.home')}
            </Link>
          </div>
        </div>
      )}

      {isError && !notFound && (
        <ApiRetryBanner onRetry={refetch} isFetching={isFetching} className="mb-6">
          {t('world.country.loadError')}
        </ApiRetryBanner>
      )}

      {isLoading && (
        <div className="min-h-screen space-y-4">
          <SkeletonBox className="h-9 w-64 max-w-full" />
          <SkeletonBox className="h-10 w-full rounded-xl" />
          <SkeletonBox className="h-40 rounded-xl" />
        </div>
      )}

      {data && (
        <>
          <div className="fe-data-header">
            <div className="mb-2 flex items-center gap-1.5 font-mono text-xs uppercase tracking-widest text-champagne">
              <Globe2 size={13} />
              {localizedDisplay(locale, data.country.region, data.country.region_en)}
            </div>
            <div className="grid gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(260px,0.7fr)] lg:items-start lg:gap-7">
              <div>
                <h1 className="font-display text-[1.65rem] font-bold leading-tight text-text-primary sm:text-4xl">
                  {countryMeta?.h1 || countryName}
                </h1>
                {data.country.name_en && data.country.name_en !== countryName && (
                  <div className="mt-1 text-xs text-text-tertiary">{data.country.name_en}</div>
                )}
                <p className="mt-3 max-w-2xl text-sm leading-6 text-text-secondary">
                  {t('world.country.coverage', {
                    indicators: `${totalIndicators} ${locale === 'en'
                      ? (totalIndicators === 1 ? t('world.unit.indicator_one') : t('world.unit.indicator_many'))
                      : pluralRu(totalIndicators, [t('world.unit.indicator_one'), t('world.unit.indicator_few'), t('world.unit.indicator_many')])}`,
                    sections: `${isUsCatalog ? usTopics.length : data.categories.length} ${locale === 'en'
                      ? ((isUsCatalog ? usTopics.length : data.categories.length) === 1 ? t('world.unit.section_one') : t('world.unit.section_many'))
                      : pluralRu(isUsCatalog ? usTopics.length : data.categories.length, [t('world.unit.section_one'), t('world.unit.section_few'), t('world.unit.section_many')])}`,
                    history: data.coverage?.history_start
                      ? t('world.country.historyFrom', { year: formatDate(data.coverage.history_start, 'annual', locale) })
                      : '.',
                  })}
                </p>
              </div>
              <div>
                <CountrySilhouette
                  code={data.country.code}
                  name={countryName}
                  slug={slug}
                  region={data.country.region}
                  historyStart={data.coverage?.history_start}
                  historyEnd={data.coverage?.history_end}
                  frequencies={data.coverage?.frequencies}
                  area={data.area}
                  population={data.population}
                />
                <Link
                  to={data.overview?.[0]
                    ? `/compare?codes=w:${slug}:${data.overview[0].concept_slug}`
                    : '/compare'}
                  className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-champagne px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-transform hover:-translate-y-0.5"
                >
                  <BarChart3 size={15} />
                  {t('world.country.compareCta')}
                  <ArrowUpRight size={14} />
                </Link>
              </div>
            </div>

            <div id="chart" className="mt-7 grid scroll-mt-28 gap-2 sm:grid-cols-3 sm:gap-4">
              {(data.overview || []).slice(0, 3).map((item) => (
                <Link
                  key={item.concept_slug}
                  to={indicatorPath(slug, item.indicator_code)}
                  className="fe-panel fe-summary-card group rounded-xl border border-border-subtle bg-surface p-3.5 transition-all hover:border-border-champagne hover:shadow-sm"
                >
                  <div className="text-[11px] uppercase tracking-wide text-text-tertiary">
                    {localizedDisplay(locale, item.name, item.name_en)}
                  </div>
                  <div className="mt-1 font-mono text-lg font-semibold leading-none text-text-primary">
                    {formatWorldValue(item.value, undefined, locale)}
                  </div>
                  <div className="mt-1.5 font-mono text-[11px] text-text-tertiary">
                    {formatIndicatorDate(item.date, item.frequency, locale)}
                  </div>
                </Link>
              ))}
              {!data.overview?.length && (
                <div className="text-xs text-text-tertiary sm:col-span-3">
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
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
                  {t('world.regions.cardKicker')}
                </div>
                <div className="mt-1 font-display text-xl font-bold text-text-primary">
                  {data.country.region_kind_label_plural || t('world.regions.cardTitle')}
                </div>
                <p className="mt-1 text-sm text-text-secondary">
                  {t('world.regions.cardBody')}
                </p>
              </div>
              <span className="shrink-0 rounded-full bg-champagne/15 px-3 py-1.5 text-sm text-champagne">
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

          {(data.market_indicators || []).length > 0 && (
            <section className="mb-8" data-testid="country-market-indicators">
              <div className="mb-3 flex items-end justify-between gap-3 sm:mb-4 sm:gap-4">
                <div className="min-w-0">
                  <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-champagne">
                    {t('world.country.markets')}
                  </div>
                  <h2 className="mt-1 font-display text-xl font-bold leading-snug text-text-primary sm:text-2xl">
                    {t('world.country.markets')}
                  </h2>
                </div>
                <span className="shrink-0 font-mono text-xs text-text-tertiary">
                  {data.market_indicators.length}
                </span>
              </div>
              <div className="grid gap-2 sm:gap-2.5 xl:grid-cols-2">
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

          {filteredCategories.length === 0 && (
            <div className="rounded-2xl border border-border-subtle bg-surface p-6 text-center text-sm text-text-secondary">
              {searching ? (
                <>
                  {t('world.country.emptySearch', { query })}
                  {' '}
                  <button type="button" onClick={() => { setQuery(''); setSearchLimit(120); }} className="text-champagne hover:underline">
                    {t('world.country.emptySearchReset')}
                  </button>
                </>
              ) : (
                <>
                  {t('world.country.emptyCatalog')}
                  {' '}
                  <Link to="/#countries" className="text-champagne hover:underline">
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
              onChange={setActiveCategory}
              options={filteredCategories.map((cat) => ({
                value: cat.name,
                label: localizedDisplay(locale, cat.name, cat.name_en),
                count: cat.indicators.length,
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
                onSection={setActiveCategory}
                sectionKey={(cat) => cat.name}
                sectionLabel={(cat) => localizedDisplay(locale, cat.name, cat.name_en)}
                themesLabel={t('world.country.themes')}
                detailLabel={locale === 'en' ? 'Detailed topics' : 'Подробные темы'}
              />
            )}
            {!searching && !isUsCatalog && (
              <aside className="hidden min-w-0 lg:sticky lg:top-24 lg:block lg:max-h-[calc(100vh-7rem)] lg:self-start lg:overflow-y-auto">
                <div className="mb-2 px-2 text-[10px] font-mono uppercase tracking-[0.18em] text-text-tertiary">
                  {t('world.country.themes')}
                </div>
                <div className="flex flex-col gap-2">
                  {filteredCategories.map((cat) => (
                    <button
                      key={cat.name}
                      type="button"
                      onClick={() => {
                        setActiveCategory(cat.name);
                        document.querySelectorAll('[data-world-country-category]')
                          .forEach((section) => {
                            if (section.dataset.worldCountryCategory === cat.name) {
                              section.scrollIntoView({ behavior: 'smooth', block: 'start' });
                            }
                          });
                      }}
                      aria-current={resolvedActiveCategory === cat.name ? 'true' : undefined}
                      className={[
                        'flex items-center justify-between gap-4 rounded-xl px-3.5 py-2.5 text-left text-sm transition-colors',
                        resolvedActiveCategory === cat.name
                          ? 'bg-champagne/12 font-medium text-champagne'
                          : 'bg-surface text-text-secondary hover:bg-surface-hover hover:text-text-primary',
                      ].join(' ')}
                    >
                      <span className="min-w-0 truncate">{localizedDisplay(locale, cat.name, cat.name_en)}</span>
                      <span className="shrink-0 font-mono text-[10px] opacity-60">{cat.indicators.length}</span>
                    </button>
                  ))}
                </div>
              </aside>
            )}

            <div className="min-w-0 space-y-8">
              {visibleCategories.map((cat) => (
                <section key={cat.name} className="scroll-mt-24" data-world-country-category={cat.name}>
                  <div className="mb-3 flex items-end justify-between gap-3 sm:mb-4 sm:gap-4">
                    <div className="min-w-0">
                      <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-champagne">
                        {searching ? t('regions.searchResults') : t('world.country.indicators')}
                      </div>
                      <h2 className="mt-1 font-display text-xl font-bold leading-snug text-text-primary sm:text-2xl">{localizedDisplay(locale, cat.name, cat.name_en)}</h2>
                    </div>
                    <span className="shrink-0 font-mono text-xs text-text-tertiary">{cat.indicators.length}</span>
                  </div>
                  <div className="grid gap-2 sm:gap-2.5 xl:grid-cols-2">
                    {cat.indicators.map((ind) => (
                      <IndicatorRow key={ind.code} item={ind} slug={slug} sectionName={isUsCatalog ? cat.name_ru : undefined} />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </div>
          {isUsCatalog && searching && matchCount > searchLimit && (
            <button
              type="button"
              onClick={() => setSearchLimit((current) => current + 120)}
              className="mt-5 rounded-full border border-border-subtle bg-surface px-5 py-2.5 text-sm text-text-secondary hover:border-border-champagne hover:text-text-primary"
            >
              {locale === 'en' ? 'Show more indicators' : 'Показать ещё показатели'}
              {locale === 'en' ? ' of ' : ' из '}
              {Math.min(searchLimit, matchCount)} / {matchCount}
            </button>
          )}
        </>
      )}
    </div>
  );
}
