// Хаб субнациональных регионов: /{country}/regions
// Эталон — RegionsHome: список/карта, rounded-full чипы, MapTimeline, PNG.
import { useMemo, lazy, Suspense, useState, useDeferredValue, useRef } from 'react';
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  MapPin, Search, List, Map as MapIcon, Image as ImageIcon, ChevronRight, ChevronDown, X,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  useWorldRegionsHub,
  useWorldRegionsMap,
} from '../lib/worldSubnationalApi';
import Button from '../components/Button';
import { RegionSearchField, RegionSectionHeading, RegionMetricLine } from '../components/regions/RegionParts';
import MapMetricTopics from '../components/regions/MapMetricTopics';
import { pickPopularIndicators } from '../lib/mapMetricPicks';
import { unitLabel } from '../lib/regionUi';
import { rememberScroll, useRestoreScroll } from '../lib/keepScroll';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import { worldSubnationalHubTrail } from '../lib/breadcrumbs';
import { exportNodeToPng } from '../lib/chartImage';
import { track, events } from '../lib/track';
import useSearchTracking from '../lib/useSearchTracking';
import { filterSearchOptions } from '../lib/searchSynonyms';
import { useAuth } from '../context/authContext';
import {
  RUSSIA,
  countryRegionPath,
  countryRegionsPath,
  countryRegionMapPath,
  countryRegionIndicatorPath,
  regionHubPath,
} from '../lib/sitePaths';
import { useLocale } from '../i18n';
import usStatesMap from '../lib/usStatesMap.json';
import { plainUsIndicatorName } from '../lib/usCatalogTopics';
import Spinner from '../components/Spinner';
import '../styles/platform-pages.css';
import '../styles/regions-w4.css';
import '../styles/w6f-pages.css';

const RegionsMap = lazy(() => import('../components/RegionsMap'));
const MapTimeline = lazy(() => import('../components/MapTimeline'));

const MAPS = {
  'us-states': usStatesMap,
};
const OVERVIEW = 'overview';

function normalize(s) {
  return (s || '').toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ').trim();
}

function yearsFromPeriods(periods) {
  const seen = new Set();
  const years = [];
  for (const p of periods || []) {
    const y = Number(String(p.key || '').slice(0, 4));
    if (!Number.isFinite(y) || seen.has(y)) continue;
    seen.add(y);
    years.push(y);
  }
  return years.sort((a, b) => a - b);
}

function lastPeriodOfYear(periods, year) {
  const prefix = String(year);
  let best = null;
  for (const p of periods || []) {
    const key = String(p.key || '');
    if (!key.startsWith(prefix)) continue;
    if (best == null || key > best) best = key;
  }
  return best;
}

function MetricSearch({ indicators, activeCode, activeName, onPick, onClear }) {
  const { t, locale } = useLocale();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [resultLimit, setResultLimit] = useState(12);
  const deferred = useDeferredValue(query);
  const results = useMemo(() => {
    const q = normalize(deferred);
    const list = indicators || [];
    return filterSearchOptions(list, q);
  }, [indicators, deferred]);
  useSearchTracking('world-map-metric', open ? deferred : '', results.length);
  const isCustom = !!activeCode;

  return (
    <div className="relative w-full shrink-0 sm:w-64 sm:flex-none">
      <div className={`flex min-h-11 items-center gap-2 rounded-xl border px-3 text-sm transition-colors ${
        isCustom
          ? 'border-transparent bg-champagne/15 text-champagne-ink'
          : 'border-border-subtle bg-surface text-text-secondary focus-within:border-champagne-ink focus-within:ring-1 focus-within:ring-champagne-ink'
      }`}
      >
        <Search size={13} className="shrink-0" />
        <input
          type="text"
          value={open ? query : (isCustom ? activeName : '')}
          placeholder={t('regions.map.customPlaceholder')}
          onFocus={() => { setOpen(true); setQuery(''); setResultLimit(12); }}
          onClick={() => { if (!open) { setOpen(true); setQuery(''); setResultLimit(12); } }}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onChange={(e) => { if (!open) setOpen(true); setQuery(e.target.value); setResultLimit(50); }}
          className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-text-tertiary"
          aria-label={t('regions.map.customAria')}
          role="combobox"
          aria-expanded={open}
        />
        {isCustom && !open && (
          <button
            type="button"
            aria-label={t('regions.map.clearMetric')}
            onMouseDown={(e) => { e.preventDefault(); onClear(); }}
            className="fe-map-btn shrink-0 text-champagne-ink hover:text-champagne-ink"
          >
            <X size={13} />
          </button>
        )}
      </div>
      {open && (
        <div className="absolute right-0 z-30 mt-2 max-h-72 w-[min(calc(100vw-2rem),26rem)] overflow-auto rounded-xl border border-border-subtle bg-surface shadow-2xl sm:left-0 sm:right-auto">
          {results.length === 0 ? (
            <div className="px-3.5 py-3 text-sm text-text-secondary">
              {t('regions.home.nothingFound', { query })}
            </div>
          ) : results.slice(0, resultLimit).map((i) => (
            <button
              key={i.code}
              type="button"
              onMouseDown={(e) => { e.preventDefault(); onPick(i); setOpen(false); setQuery(''); }}
              className="fe-tap w-full px-3.5 py-2 text-left transition-colors hover:bg-surface-hover"
            >
              <div className="text-sm leading-snug text-text-primary">{i.name}</div>
              <div className="text-xs text-text-secondary">{i.section}</div>
            </button>
          ))}
          {results.length > resultLimit && (
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => setResultLimit((current) => current + 50)}
              className="w-full border-t border-border-subtle px-3.5 py-3 text-left text-sm text-champagne-ink hover:bg-surface-hover"
            >
              {locale === 'en' ? 'Show more indicators' : 'Показать ещё показатели'}: {Math.min(resultLimit, results.length)} / {results.length}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function RegionCard({ region, metric, metricName, countrySlug }) {
  return (
    <Link
      to={countryRegionPath(countrySlug, region.slug)}
      className="fe-press group flex items-center justify-between gap-3 rounded-2xl border border-border-subtle bg-surface px-3.5 py-3 transition-colors hover:border-border-champagne sm:px-4 sm:py-3.5"
    >
      <div className="min-w-0">
        <div className="text-[15px] font-medium leading-snug text-text-primary transition-colors group-hover:text-champagne-ink">
          {region.name}
        </div>
        {metric && (
          <RegionMetricLine name={metricName} value={metric.value} unit={metric.unit} rank={metric.rank} />
        )}
      </div>
      <ChevronRight size={16} className="hidden shrink-0 text-text-secondary transition-colors group-hover:text-champagne-ink sm:block" aria-hidden="true" />
    </Link>
  );
}

export default function WorldRegionsHome() {
  const { countrySlug, code: mapCode } = useParams();
  const { t, locale } = useLocale();
  const { isAuthed } = useAuth();
  const navigate = useNavigate();
  useRestoreScroll();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState('');
  const deferredQuery = useDeferredValue(query);
  const mapCardRef = useRef(null);
  const [exportingMap, setExportingMap] = useState(false);
  const hub = useWorldRegionsHub(countrySlug === RUSSIA ? undefined : countrySlug);

  const isMapRoute = Boolean(mapCode);
  const isOverview = mapCode === OVERVIEW;
  const defaultCode = hub.data?.default_indicator;
  const activeCode = isOverview ? null : (isMapRoute ? mapCode : defaultCode);
  const period = isMapRoute ? (params.get('period') || undefined) : undefined;
  const map = useWorldRegionsMap(
    countrySlug === RUSSIA ? undefined : countrySlug,
    activeCode,
    period,
  );

  const countryName = hub.data?.country?.name || countrySlug;
  const kindPlural = hub.data?.kind_label_plural || t('world.regions.fallbackKindPlural');
  const title = countrySlug === 'united-states' && locale === 'ru'
    ? 'Штаты США'
    : countrySlug === 'united-states' && locale === 'en'
      ? 'US states'
      : t('world.regions.hubTitle', { kind: kindPlural, country: countryName });

  useDocumentMeta({
    title: `${title} | Forecast Economy`,
    description: t('world.regions.hubDescription', { kind: kindPlural, country: countryName }),
  });

  const valuesBySlug = useMemo(() => {
    const m = new Map();
    // The previous map stays in the query cache so the timeline never unmounts.
    // Its values must not be presented as observations for the newly selected year.
    if (map.isPlaceholderData) return m;
    for (const row of map.data?.values || []) {
      if (row.value != null) m.set(row.slug, row.value);
    }
    return m;
  }, [map.data, map.isPlaceholderData]);

  const metricBySlug = useMemo(() => {
    const o = {};
    if (map.isPlaceholderData) return o;
    const unit = map.data?.indicator?.unit || '';
    for (const row of map.data?.values || []) {
      o[row.slug] = { value: row.value, rank: row.rank, unit };
    }
    return o;
  }, [map.data, map.isPlaceholderData]);

  const nameBySlug = useMemo(() => {
    const o = {};
    for (const r of hub.data?.regions || []) o[r.slug] = r.name;
    return o;
  }, [hub.data]);

  const geometry = MAPS[hub.data?.map_id] || usStatesMap;
  const periods = map.data?.periods || [];
  const indicators = useMemo(() => hub.data?.indicators || [], [hub.data?.indicators]);
  // Шесть понятных тем сверху; остальное — поиск и «Все показатели по темам».
  const chipIndicators = useMemo(
    () => pickPopularIndicators(indicators, defaultCode, 6),
    [indicators, defaultCode],
  );
  const presetCodes = new Set(chipIndicators.map((i) => i.code));
  const isCustomMetric = !!(activeCode && !presetCodes.has(activeCode));
  const customName = indicators.find((i) => i.code === activeCode)?.name || '';

  const years = yearsFromPeriods(periods);
  const requestedYear = period ? Number(String(period).slice(0, 4)) : null;
  const mapYear = requestedYear && years.includes(requestedYear)
    ? requestedYear
    : (map.data?.period ? Number(String(map.data.period).slice(0, 4)) : null);

  const setView = (next) => {
    rememberScroll();
    if (next === 'map') {
      navigate(countryRegionMapPath(countrySlug, activeCode || defaultCode || OVERVIEW));
      return;
    }
    navigate(`${countryRegionsPath(countrySlug)}?view=list`);
  };

  const setMetric = (nextCode) => {
    rememberScroll();
    const qs = period ? `?period=${period}` : '';
    navigate(`${countryRegionMapPath(countrySlug, nextCode)}${qs}`);
  };

  const setPeriod = (next) => {
    const nextParams = new URLSearchParams(params);
    if (next) nextParams.set('period', next);
    else nextParams.delete('period');
    setParams(nextParams, { replace: true });
  };

  const setMapYear = (year) => {
    const key = lastPeriodOfYear(periods, year);
    if (key) setPeriod(key);
  };

  const handlePng = async () => {
    if (exportingMap) return;
    if (!isAuthed) {
      track(events.CHART_IMAGE_BLOCKED, { indicator: `world-regions-map:${activeCode || 'overview'}` });
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return;
    }
    setExportingMap(true);
    const ok = await exportNodeToPng(mapCardRef.current, {
      filename: `${countrySlug}-map_${activeCode || 'overview'}.png`,
      watermark: false,
    }).catch(() => false);
    setExportingMap(false);
    if (ok) track(events.CHART_IMAGE_DOWNLOAD, { indicator: `world-regions-map:${activeCode || 'overview'}` });
  };

  const regions = useMemo(() => hub.data?.regions || [], [hub.data?.regions]);
  const filteredRegions = useMemo(() => {
    const q = normalize(deferredQuery);
    if (!q) return regions;
    return filterSearchOptions(regions, q, { searchKind: 'region', getSearchItem: (item) => ({ ...item, country_slug: countrySlug }) });
  }, [regions, deferredQuery, countrySlug]);
  useSearchTracking('world-regions-hub', deferredQuery, filteredRegions.length);

  if (countrySlug === RUSSIA) {
    return <Navigate to={regionHubPath()} replace />;
  }

  // Карта по умолчанию: человек пришёл за картой, а не за списком из 51 одинаковой строки.
  // Список остаётся по вкладке «Список» (?view=list).
  const view = isMapRoute ? 'map' : (params.get('view') === 'list' ? 'list' : 'map');
  const chipCls = (active) => `fe-chip fe-press ${active ? 'is-active' : ''}`;

  return (
    <div className="fe-data-page mx-auto w-full max-w-7xl overflow-x-clip px-4 pb-12 pt-24 sm:px-6 sm:pb-16">
      <Breadcrumbs items={worldSubnationalHubTrail(countryName, countrySlug, kindPlural)} />
      {hub.isError && (
        <ApiRetryBanner onRetry={hub.refetch} isFetching={hub.isFetching} className="mb-6">
          {t('world.regions.loadError')}
        </ApiRetryBanner>
      )}

      <div className="mb-6">
        <h1 className="font-display text-[1.75rem] font-bold leading-tight text-text-primary sm:text-4xl">
          {title}
        </h1>
        <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-text-secondary">
          {t('world.regions.hubLead', { kind: kindPlural, country: countryName })}
        </p>
      </div>

      <div className="mb-3 flex w-fit items-center gap-1 rounded-2xl border border-border-subtle bg-surface p-1" role="tablist" aria-label={t('regions.viewAria')}>
        <button
          type="button"
          role="tab"
          aria-selected={view === 'list'}
          onClick={() => setView('list')}
          className={`fe-tap fe-press inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
            view === 'list' ? 'bg-champagne/15 text-champagne-ink' : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <List size={15} /> {t('regions.view.list')}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={view === 'map'}
          onClick={() => setView('map')}
          className={`fe-tap fe-press inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
            view === 'map' ? 'bg-champagne/15 text-champagne-ink' : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <MapIcon size={15} /> {t('regions.view.map')}
        </button>
      </div>

      {hub.isLoading && (
        <div className="mt-4" role="status" aria-busy="true" aria-label={t('common.loading')}>
          <SkeletonBox className="mb-6 h-[46px] w-full rounded-xl" />
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 sm:gap-2.5">
            {Array.from({ length: 8 }).map((_, i) => <SkeletonBox key={i} className="h-[98px] rounded-xl sm:h-[78px]" />)}
          </div>
        </div>
      )}

      {hub.data && view === 'list' && (
        <>
          <RegionSearchField
            className="mb-6 mt-4"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('world.regions.searchPlaceholder')}
            ariaLabel={t('world.regions.searchAria')}
          />
          <section>
            <RegionSectionHeading
              eyebrow={normalize(deferredQuery) ? t('regions.searchResults') : null}
              title={kindPlural}
              count={filteredRegions.length}
            />
            {countrySlug === 'united-states' && regions.length === 51 && (
              <p className="-mt-1 mb-3 text-sm text-text-secondary" data-testid="us-territories-note">{t('w6f.us.count51')}</p>
            )}
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 sm:gap-2.5">
              {filteredRegions.map((r) => (
                <RegionCard
                  key={r.slug}
                  region={r}
                  countrySlug={countrySlug}
                  metric={metricBySlug[r.slug]}
                  metricName={map.data?.indicator?.name}
                />
              ))}
            </div>
            {filteredRegions.length === 0 && (
              <div className="rounded-3xl border border-border-subtle bg-surface p-6 text-center text-sm text-text-secondary">
                <MapPin size={22} className="mx-auto mb-2 text-champagne-ink" aria-hidden="true" />
                {t('world.regions.noRegions', { query })}
                <div className="mt-3">
                  <Button variant="secondary" size="sm" onClick={() => setQuery('')}>{t('regions.profile.resetSearch')}</Button>
                </div>
              </div>
            )}
          </section>
        </>
      )}

      {hub.data && view === 'map' && (
        <div className="mt-4">
          <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="fe-chip-ribbon w-full min-w-0 sm:flex-1" role="tablist" aria-label={t('regions.map.metricAria')}>
              <button
                type="button"
                role="tab"
                aria-selected={isOverview}
                onClick={() => setMetric(OVERVIEW)}
                title={t('world.regions.mapClickTitle')}
                className={chipCls(isOverview)}
              >
                {t('regions.map.overview')}
              </button>
              {chipIndicators.map((ind) => {
                const selected = !isOverview && !isCustomMetric && activeCode === ind.code;
                return (
                  <button
                    key={ind.code}
                    type="button"
                    role="tab"
                    aria-selected={selected}
                    onClick={() => setMetric(ind.code)}
                    className={chipCls(selected)}
                  >
                    {plainUsIndicatorName(ind.name, locale).label}
                  </button>
                );
              })}
            </div>
            <MetricSearch
              indicators={indicators}
              activeCode={isCustomMetric ? activeCode : null}
              activeName={customName}
              onPick={(i) => setMetric(i.code)}
              onClear={() => setMetric(OVERVIEW)}
            />
          </div>
          <MapMetricTopics
            indicators={indicators}
            sections={hub.data?.sections}
            usTopics={countrySlug === 'united-states'}
            activeCode={isOverview ? null : activeCode}
            onPick={(i) => setMetric(i.code)}
          />

          <div id="chart" data-block="world-regions-map" className="relative rounded-3xl border border-border-subtle bg-surface p-3 sm:p-5" ref={mapCardRef}>
            <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                {activeCode && map.data?.indicator ? (
                  <>
                    <div className="text-sm font-medium leading-snug text-text-primary">{map.data.indicator.name}</div>
                    <div className="mt-0.5 text-xs text-text-secondary">
                      {[
                        mapYear != null ? t('w4.map.yearLabel', { year: mapYear }) : null,
                        unitLabel(map.data.indicator.unit, locale) || map.data.indicator.unit,
                      ].filter(Boolean).join(', ')}
                    </div>
                  </>
                ) : (
                  <div className="text-sm text-text-secondary">{t('world.regions.mapCaptionOverview')}</div>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-1.5" data-no-export="true">
                <button
                  type="button"
                  disabled={exportingMap}
                  onClick={handlePng}
                  title={isAuthed ? t('download.mapPng') : t('download.afterRegister')}
                  aria-label={t('download.mapPng')}
                  className="fe-chip fe-press gap-1 border-border-subtle"
                >
                  <ImageIcon size={13} aria-hidden="true" /> PNG
                </button>
              </div>
            </div>
            {activeCode && map.isError && (
              <ApiRetryBanner onRetry={map.refetch} isFetching={map.isFetching} className="mb-3">
                {t('pgui.regions.mapError')}
              </ApiRetryBanner>
            )}
            {activeCode && map.isLoading && (
              <div className="mb-2 flex items-center gap-2 text-xs text-text-secondary" role="status">
                <Spinner size={14} />
                {t('pgui.regions.mapLoading')}
              </div>
            )}
            <Suspense fallback={<SkeletonBox className="aspect-[960/600] w-full rounded-2xl" />}>
              <RegionsMap
                mapData={geometry}
                ariaLabel={t('world.regions.mapAria', { country: countryName })}
                valuesBySlug={activeCode ? valuesBySlug : null}
                transitionMs={activeCode ? 650 : 150}
                unit={map.data?.indicator?.unit || ''}
                nameBySlug={nameBySlug}
                colorDirection={map.data?.indicator?.better_is_low ? 'asc' : 'desc'}
                brandMark
                onSelect={(slug) => {
                  track(events.REGIONS_MAP_SELECT, { region: slug, metric: activeCode || 'overview', world: true });
                  navigate(activeCode
                    ? countryRegionIndicatorPath(countrySlug, slug, activeCode)
                    : countryRegionPath(countrySlug, slug));
                }}
              />
            </Suspense>
            {activeCode && years.length > 1 && mapYear != null && (
              <Suspense fallback={null}>
                <MapTimeline
                  key={activeCode}
                  years={years}
                  year={years.includes(mapYear) ? mapYear : years[years.length - 1]}
                  onYearChange={setMapYear}
                  metric={activeCode}
                />
              </Suspense>
            )}
          </div>
          <div className="mt-3 text-sm leading-relaxed text-text-secondary">
            <p>{activeCode ? t('w4.map.hintWorldMetric') : t('w4.map.hintOverview')}</p>
            <details className="fe-acc mt-1">
              <summary className="fe-tap-inline gap-1 text-champagne-ink">
                {t('w4.map.howToRead')}
                <ChevronDown size={14} className="fe-acc__chev" aria-hidden="true" />
              </summary>
              <p className="mt-1">{t('w4.map.howToReadWorld')}</p>
            </details>
          </div>
        </div>
      )}
    </div>
  );
}
