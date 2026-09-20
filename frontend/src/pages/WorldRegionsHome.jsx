// Хаб субнациональных регионов: /{country}/regions
// Эталон — RegionsHome: список/карта, rounded-full чипы, MapTimeline, PNG.
import { useMemo, lazy, Suspense, useState, useDeferredValue, useRef } from 'react';
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  MapPin, Search, List, Map as MapIcon, Image as ImageIcon, ChevronRight, Database, X,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  useWorldRegionsHub,
  useWorldRegionsMap,
  formatSubnationalValue,
} from '../lib/worldSubnationalApi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import { worldSubnationalHubTrail } from '../lib/breadcrumbs';
import { exportNodeToPng } from '../lib/chartImage';
import { track, events } from '../lib/track';
import useSearchTracking from '../lib/useSearchTracking';
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
  return (periods || []).find((p) => String(p.key).startsWith(String(year)))?.key;
}

function MetricSearch({ indicators, activeCode, activeName, onPick, onClear }) {
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const deferred = useDeferredValue(query);
  const results = useMemo(() => {
    const q = normalize(deferred);
    const list = indicators || [];
    if (!q) return list.slice(0, 12);
    return list.filter((i) => normalize(`${i.name} ${i.section} ${i.code}`).includes(q)).slice(0, 20);
  }, [indicators, deferred]);
  const isCustom = !!activeCode;

  return (
    <div className="relative min-w-0 flex-1 sm:max-w-xs">
      <div className={`flex items-center gap-1.5 rounded-full border px-3 py-2 text-xs transition-colors sm:py-1.5 ${
        isCustom
          ? 'border-transparent bg-champagne/15 text-champagne'
          : 'border-border-subtle bg-surface text-text-secondary focus-within:border-border-champagne'
      }`}
      >
        <Search size={13} className="shrink-0" />
        <input
          type="text"
          value={open ? query : (isCustom ? activeName : '')}
          placeholder={t('regions.map.customPlaceholder')}
          onFocus={() => { setOpen(true); setQuery(''); }}
          onClick={() => { if (!open) { setOpen(true); setQuery(''); } }}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onChange={(e) => { if (!open) setOpen(true); setQuery(e.target.value); }}
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
            className="shrink-0 text-champagne/70 hover:text-champagne"
          >
            <X size={13} />
          </button>
        )}
      </div>
      {open && (
        <div className="absolute right-0 z-30 mt-2 max-h-72 w-[min(calc(100vw-2rem),26rem)] overflow-auto rounded-xl border border-border-subtle bg-surface shadow-2xl sm:left-0 sm:right-auto">
          {results.length === 0 ? (
            <div className="px-3.5 py-3 text-[13px] text-text-tertiary">
              {t('regions.home.nothingFound', { query })}
            </div>
          ) : results.map((i) => (
            <button
              key={i.code}
              type="button"
              onMouseDown={(e) => { e.preventDefault(); onPick(i); setOpen(false); setQuery(''); }}
              className="w-full px-3.5 py-2 text-left transition-colors hover:bg-surface-hover"
            >
              <div className="text-[13px] leading-snug text-text-primary">{i.name}</div>
              <div className="text-[11px] text-text-tertiary">{i.section}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function RegionCard({ region, metric, countrySlug }) {
  const { locale } = useLocale();
  return (
    <Link
      to={countryRegionPath(countrySlug, region.slug)}
      className="group flex items-center justify-between gap-2.5 rounded-xl border border-border-subtle bg-surface px-3.5 py-3 transition-all hover:border-border-champagne hover:shadow-sm sm:gap-3 sm:px-4 sm:py-3.5"
    >
      <div className="min-w-0">
        <div className="truncate text-[14px] font-medium leading-snug text-text-primary transition-colors group-hover:text-champagne sm:text-[15px]">
          {region.name}
        </div>
        {metric && (
          <div className="mt-1 font-mono text-[11px] text-text-secondary sm:text-xs">
            {formatSubnationalValue(metric.value, locale)}
            {metric.unit ? ` ${metric.unit}` : ''}
            {metric.rank != null ? ` — ${metric.rank}` : ''}
          </div>
        )}
      </div>
      <ChevronRight size={16} className="hidden shrink-0 text-text-tertiary transition-colors group-hover:text-champagne sm:block" />
    </Link>
  );
}

export default function WorldRegionsHome() {
  const { countrySlug, code: mapCode } = useParams();
  const { t } = useLocale();
  const { isAuthed } = useAuth();
  const navigate = useNavigate();
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
  const title = t('world.regions.hubTitle', { kind: kindPlural, country: countryName });

  useDocumentMeta({
    title: `${title} | Forecast Economy`,
    description: t('world.regions.hubDescription', { kind: kindPlural, country: countryName }),
  });

  const valuesBySlug = useMemo(() => {
    const m = new Map();
    for (const row of map.data?.values || []) {
      if (row.value != null) m.set(row.slug, row.value);
    }
    return m;
  }, [map.data]);

  const metricBySlug = useMemo(() => {
    const o = {};
    const unit = map.data?.indicator?.unit || '';
    for (const row of map.data?.values || []) {
      o[row.slug] = { value: row.value, rank: row.rank, unit };
    }
    return o;
  }, [map.data]);

  const nameBySlug = useMemo(() => {
    const o = {};
    for (const r of hub.data?.regions || []) o[r.slug] = r.name;
    return o;
  }, [hub.data]);

  const geometry = MAPS[hub.data?.map_id] || usStatesMap;
  const periods = map.data?.periods || [];
  const indicators = hub.data?.indicators || [];
  const presetCodes = new Set(indicators.slice(0, 8).map((i) => i.code));
  const chipIndicators = indicators.slice(0, 8);
  const isCustomMetric = !!(activeCode && !presetCodes.has(activeCode));
  const customName = indicators.find((i) => i.code === activeCode)?.name || '';

  const years = yearsFromPeriods(periods);
  const mapYear = map.data?.period ? Number(String(map.data.period).slice(0, 4)) : null;

  const setView = (next) => {
    if (next === 'map') {
      navigate(countryRegionMapPath(countrySlug, activeCode || defaultCode || OVERVIEW));
      return;
    }
    navigate(countryRegionsPath(countrySlug));
  };

  const setMetric = (nextCode) => {
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

  const regions = hub.data?.regions || [];
  const filteredRegions = useMemo(() => {
    const q = normalize(deferredQuery);
    if (!q) return regions;
    return regions.filter((r) => normalize(`${r.name} ${r.name_en} ${r.slug}`).includes(q));
  }, [regions, deferredQuery]);
  useSearchTracking('world-regions-hub', deferredQuery, filteredRegions.length);

  if (countrySlug === RUSSIA) {
    return <Navigate to={regionHubPath()} replace />;
  }

  const view = isMapRoute ? 'map' : 'list';
  const chipCls = (active) => `min-h-9 shrink-0 rounded-full px-3.5 py-2 text-xs font-medium transition-colors ${
    active
      ? 'bg-champagne/15 text-champagne'
      : 'bg-surface border border-border-subtle text-text-secondary hover:text-text-primary'
  }`;

  return (
    <div className="mx-auto w-full max-w-7xl overflow-x-clip px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs items={worldSubnationalHubTrail(countryName, countrySlug, kindPlural)} />
      {hub.isError && (
        <ApiRetryBanner onRetry={hub.refetch} isFetching={hub.isFetching} className="mb-6">
          {t('world.regions.loadError')}
        </ApiRetryBanner>
      )}

      <div className="mb-8">
        <div className="mb-3 flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-champagne">
          <MapPin size={14} />
          {kindPlural}
        </div>
        <h1 className="font-display text-[1.75rem] font-bold leading-tight text-text-primary sm:text-4xl">
          {title}
        </h1>
        <p className="mt-3 max-w-2xl text-[14px] leading-relaxed text-text-secondary sm:text-[15px]">
          {t('world.regions.hubLead', { kind: kindPlural, country: countryName })}
        </p>
        {hub.data?.totals && (
          <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 font-mono text-xs text-text-tertiary">
            <span className="inline-flex items-center gap-1.5">
              <Database size={12} />
              {t('world.regions.stat.indicators', { n: hub.data.totals.indicators })}
            </span>
            <span>{t('world.regions.stat.regions', { n: hub.data.totals.regions })}</span>
          </div>
        )}
      </div>

      <div className="mb-2 flex w-fit items-center gap-1 rounded-xl border border-border-subtle bg-surface p-1" role="tablist" aria-label={t('regions.viewAria')}>
        <button
          type="button"
          role="tab"
          aria-selected={view === 'list'}
          onClick={() => setView('list')}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors ${
            view === 'list' ? 'bg-champagne/15 text-champagne' : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <List size={15} /> {t('regions.view.list')}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={view === 'map'}
          onClick={() => setView('map')}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors ${
            view === 'map' ? 'bg-champagne/15 text-champagne' : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <MapIcon size={15} /> {t('regions.view.map')}
        </button>
      </div>

      {hub.isLoading && (
        <div className="space-y-4">
          <SkeletonBox className="h-9 w-72 max-w-full" />
          <SkeletonBox className="h-80 rounded-xl" />
        </div>
      )}

      {hub.data && view === 'list' && (
        <>
          <div className="relative mb-6 mt-4">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-tertiary" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('world.regions.searchPlaceholder')}
              className="w-full rounded-xl border border-border-subtle bg-surface py-3 pl-10 pr-4 text-sm text-text-primary shadow-sm placeholder:text-text-tertiary focus:border-border-champagne focus:outline-none"
              aria-label={t('world.regions.searchAria')}
            />
          </div>
          <section>
            <div className="mb-3 flex items-end justify-between gap-3 sm:mb-4">
              <div className="min-w-0">
                <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-champagne">
                  {normalize(deferredQuery) ? t('regions.searchResults') : t('world.regions.listHeading')}
                </div>
                <h2 className="mt-1 font-display text-xl font-bold leading-snug text-text-primary sm:text-2xl">
                  {kindPlural}
                </h2>
              </div>
              <span className="shrink-0 font-mono text-xs text-text-tertiary">{filteredRegions.length}</span>
            </div>
            <div className="grid gap-2 sm:grid-cols-2 sm:gap-2.5">
              {filteredRegions.map((r) => (
                <RegionCard
                  key={r.slug}
                  region={r}
                  countrySlug={countrySlug}
                  metric={metricBySlug[r.slug]}
                />
              ))}
            </div>
            {filteredRegions.length === 0 && (
              <div className="rounded-2xl border border-border-subtle bg-surface p-5 text-center text-sm text-text-secondary sm:p-6">
                {t('world.regions.noRegions', { query })}
              </div>
            )}
          </section>
        </>
      )}

      {hub.data && view === 'map' && (
        <div className="mt-4">
          <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="scrollbar-hide flex min-w-0 items-center gap-1.5 overflow-x-auto pb-1" role="tablist" aria-label={t('regions.map.metricAria')}>
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
                    {ind.name}
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

          <div data-block="world-regions-map" className="relative rounded-xl border border-border-subtle bg-surface p-3 sm:p-5" ref={mapCardRef}>
            <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0 text-xs text-text-tertiary">
                {activeCode && map.data?.indicator ? (
                  t('world.regions.mapCaptionMetric', {
                    name: map.data.indicator.name,
                    yearBit: mapYear != null ? t('world.regions.mapYearBit', { year: mapYear }) : '',
                    unitBit: map.data.indicator.unit
                      ? t('world.regions.mapUnitBit', { unit: map.data.indicator.unit })
                      : '',
                  })
                ) : (
                  t('world.regions.mapCaptionOverview')
                )}
              </div>
              <div className="flex shrink-0 items-center gap-1.5" data-no-export="true">
                <button
                  type="button"
                  disabled={exportingMap}
                  onClick={handlePng}
                  title={isAuthed ? t('download.mapPng') : t('download.afterRegister')}
                  aria-label={t('download.mapPng')}
                  className="inline-flex min-h-9 items-center gap-1 rounded-full border border-border-subtle px-3 py-2 text-xs text-text-tertiary transition-colors hover:border-border-champagne hover:text-champagne disabled:opacity-50"
                >
                  <ImageIcon size={12} /> PNG
                </button>
              </div>
            </div>
            <Suspense fallback={<SkeletonBox className="h-80 rounded-xl" />}>
              <RegionsMap
                mapData={geometry}
                valuesBySlug={activeCode ? valuesBySlug : null}
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
          <p className="mt-3 text-xs leading-relaxed text-text-tertiary">
            {activeCode ? t('world.regions.mapHintMetric') : t('world.regions.mapHintOverview')}
            {t('world.regions.mapHintZoom')}
          </p>
        </div>
      )}
    </div>
  );
}
