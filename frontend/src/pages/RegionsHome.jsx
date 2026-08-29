// Лендинг регионального блока: /regions
// Мобильный сценарий: поиск сверху → чипы округов → карточки регионов.
// Режим «Карта»: choropleth по выбранному показателю (предустановки + поиск по
// всем RegionIndicator), тап по региону — карточка показателя; режим «Обзор» — профиль
// региона. Зум/пан — созвон «На правки 13». PNG/GIF-выгрузка карты — только для
// зарегистрированных, без watermark (правило 2026-07-08). Состояние карты в URL:
// /russia/region/map/{code}?year=YYYY (legacy query → 301/client replace на канон).
import { useMemo, useState, useRef, useDeferredValue, useCallback, useEffect, lazy, Suspense } from 'react';
import { Link, useNavigate, useSearchParams, useLocation, useParams } from 'react-router-dom';
import {
  Search, MapPin, ChevronRight, Database, List, Map as MapIcon,
  Image as ImageIcon, Film, X, RefreshCw,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  useRegionsLanding, useRegionsHeatmap, useRegionsHeatmapSeries,
  useRegionsCatalog, formatRegionValue,
} from '../lib/regionsApi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import MobileNavSelect from '../components/MobileNavSelect';
import { exportNodeToPng } from '../lib/chartImage';
import { buildRegionsMapGif, downloadBlob } from '../lib/regionsMapGif';
import {
  parseRegionsMapLocation, buildRegionsMapLocation, buildRegionsMapHref,
  locationsEqual, MAP_OVERVIEW, DEFAULT_MAP_CODE,
} from '../lib/regionsMapUrl';
import { track, events } from '../lib/track';
import useSearchTracking from '../lib/useSearchTracking';
import { useAuth } from '../context/authContext';
import {
  regionHubPath,
  regionIndicatorPath,
  regionPath,
} from '../lib/sitePaths';
import { useLocale } from '../i18n';

const RegionsMap = lazy(() => import('../components/RegionsMap'));
const MapTimeline = lazy(() => import('../components/MapTimeline'));

const DISTRICT_SHORT_KEYS = {
  cfo: 'regions.district.cfo',
  szfo: 'regions.district.szfo',
  'ufo-south': 'regions.district.ufo-south',
  skfo: 'regions.district.skfo',
  pfo: 'regions.district.pfo',
  urfo: 'regions.district.urfo',
  sfo: 'regions.district.sfo',
  dfo: 'regions.district.dfo',
};

const MAP_METRICS = [
  { code: 'srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy', labelKey: 'regions.metric.wages' },
  { code: 'chislennost-naseleniya', labelKey: 'regions.metric.population' },
  { code: 'uroven-bezrabotitsy', labelKey: 'regions.metric.unemployment' },
  { code: 'valovoy-regionalnyy-produkt-na-dushu-naseleniya', labelKey: 'regions.metric.grpPerCapita' },
  { code: 'investitsii-v-osnovnoy-kapital', labelKey: 'regions.metric.investment' },
  { code: 'chislennost-naseleniya-s-denezhnymi-dohodami-nizhe-granitsy', labelKey: 'regions.metric.poverty' },
];

const PRESET_CODES = new Set(MAP_METRICS.map((m) => m.code));

function normalize(s) {
  return s.toLowerCase().replace(/ё/g, 'е').replace(/[^а-яa-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
}

function MapMetricSearch({ activeCode, onPick, onClear, activeName }) {
  const { t } = useLocale();
  const catalog = useRegionsCatalog();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);

  const results = useMemo(() => {
    const sections = catalog.data?.sections || [];
    const all = sections.flatMap((s) =>
      s.indicators.map((i) => ({ code: i.code, name: i.name, section: s.name })));
    const q = normalize(query);
    if (!q) return all.slice(0, 50);
    return all.filter((i) => normalize(i.name).includes(q)).slice(0, 50);
  }, [catalog.data, query]);

  useSearchTracking('map-metric', open ? query : '', results.length);

  const isCustom = !!activeCode;
  const openWith = (q) => { setOpen(true); setQuery(q); };

  return (
    <div className="relative min-w-0 flex-1 sm:max-w-xs">
      <div className={`flex items-center gap-1.5 px-3 py-2 sm:py-1.5 rounded-full text-xs border transition-colors ${
        isCustom
          ? 'bg-champagne/15 text-champagne border-transparent'
          : 'bg-surface border-border-subtle text-text-secondary focus-within:border-border-champagne'
      }`}
      >
        <Search size={13} className="shrink-0" />
        <input
          type="text"
          value={open ? query : (isCustom ? activeName : '')}
          placeholder={t('regions.map.customPlaceholder')}
          onFocus={() => openWith('')}
          onClick={() => { if (!open) openWith(''); }}
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
        <div className="absolute right-0 sm:left-0 sm:right-auto z-30 mt-2 w-[min(calc(100vw-2rem),26rem)] max-h-72 overflow-auto rounded-xl border border-border-subtle bg-surface shadow-2xl">
          {catalog.isLoading ? (
            <div className="px-3.5 py-3 text-[13px] text-text-tertiary">{t('regions.home.loadingCatalog')}</div>
          ) : results.length === 0 ? (
            <div className="px-3.5 py-3 text-[13px] text-text-tertiary">
              {t('regions.home.nothingFound', { query })}
            </div>
          ) : (
            results.map((i) => (
              <button
                key={i.code}
                type="button"
                onMouseDown={(e) => { e.preventDefault(); onPick(i); setOpen(false); setQuery(''); }}
                className="w-full px-3.5 py-2 text-left hover:bg-surface-hover transition-colors"
              >
                <div className="text-[13px] text-text-primary leading-snug">{i.name}</div>
                <div className="text-[11px] text-text-tertiary">{i.section}</div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

const CONTRAST_METRICS = [
  { code: 'srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy', labelKey: 'regions.metric.wages' },
  { code: 'uroven-bezrabotitsy', labelKey: 'regions.metric.unemployment', betterIsLow: true },
  { code: 'valovoy-regionalnyy-produkt-na-dushu-naseleniya', labelKey: 'regions.metric.grpPerCapita' },
  { code: 'chislennost-naseleniya-s-denezhnymi-dohodami-nizhe-granitsy', labelKey: 'regions.metric.poverty', betterIsLow: true },
  { code: 'investitsii-v-osnovnoy-kapital', labelKey: 'regions.metric.investment' },
  { code: 'chislennost-naseleniya', labelKey: 'regions.metric.population' },
];
const CONTRAST_PAGE_SIZE = 2;
const CONTRAST_PAGES = Math.ceil(CONTRAST_METRICS.length / CONTRAST_PAGE_SIZE);

function ContrastRow({ heat, metricLabel, betterIsLow = false }) {
  const { t, locale } = useLocale();
  const rows = heat?.data?.values;
  if (!rows?.length) return null;
  const sorted = [...rows].sort((a, b) => b.value - a.value);
  const hi = sorted[0];
  const lo = sorted[sorted.length - 1];
  const first = betterIsLow ? lo : hi;
  const second = betterIsLow ? hi : lo;
  const code = heat.data.indicator.code;
  const unit = heat.data.indicator.unit || '';
  const short = /процент|percent/i.test(unit) ? '%'
    : /миллионов рублей|million rubles/i.test(unit) ? t('regions.home.unit.mlnRub')
    : /рубл|ruble/i.test(unit) ? '₽'
    : /тысяч человек|thousand people/i.test(unit) ? t('regions.home.unit.thousPeople')
    : '';
  const ratio = second.value ? Math.abs(first.value / second.value) : null;
  const ratioLabel = ratio && ratio >= 1.05
    ? `× ${ratio.toLocaleString(locale === 'en' ? 'en-US' : 'ru-RU', { maximumFractionDigits: 1 })}`
    : null;
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-x-3 gap-y-0.5 text-[13px]">
      <span className="text-text-tertiary w-28 shrink-0">{metricLabel}</span>
      <span className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
        <Link to={regionIndicatorPath(first.slug, code)} className="text-text-primary hover:text-champagne transition-colors">
          {first.name} <span className="font-mono text-positive">{formatRegionValue(first.value)} {short}</span>
        </Link>
        <span className="text-text-tertiary">{t('common.vs')}</span>
        <Link to={regionIndicatorPath(second.slug, code)} className="text-text-primary hover:text-champagne transition-colors">
          {second.name} <span className="font-mono text-negative">{formatRegionValue(second.value)} {short}</span>
        </Link>
        {ratioLabel && (
          <span className="text-[11px] font-mono text-champagne/70" title={t('regions.contrasts.ratioTitle')}>
            {ratioLabel}
          </span>
        )}
      </span>
    </div>
  );
}

function RegionCard({ region }) {
  const { t } = useLocale();
  const pop = region.stats['1.1'];
  const wage = region.stats['3.4'];
  const unemp = region.stats['2.10.1'];
  return (
    <Link
      to={regionPath(region.slug)}
      className="group flex items-center justify-between gap-2.5 rounded-xl border border-border-subtle bg-surface px-3.5 py-3 transition-all hover:border-border-champagne hover:shadow-sm sm:gap-3 sm:px-4 sm:py-3.5"
    >
      <div className="min-w-0">
        <div className="truncate text-[14px] font-medium leading-snug text-text-primary transition-colors group-hover:text-champagne sm:text-[15px]">
          {region.name}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-0.5 font-mono text-[11px] text-text-secondary sm:gap-x-3 sm:text-xs">
          {pop && <span>{formatRegionValue(pop.value)} {pop.unit || ''}</span>}
          {wage && <span>{formatRegionValue(wage.value)} ₽</span>}
          {unemp && (
            <span>{t('regions.card.unemp', { value: formatRegionValue(unemp.value) })}</span>
          )}
        </div>
      </div>
      <ChevronRight size={16} className="hidden shrink-0 text-text-tertiary transition-colors group-hover:text-champagne sm:block" />
    </Link>
  );
}

export default function RegionsHome() {
  const { t, locale } = useLocale();
  const { isAuthed } = useAuth();
  const { data, isLoading, isError, refetch, isFetching } = useRegionsLanding();
  const catalog = useRegionsCatalog();
  const [query, setQuery] = useState('');
  const [activeDistrict, setActiveDistrict] = useState(null);
  const deferredQuery = useDeferredValue(query);
  const navigate = useNavigate();
  const location = useLocation();
  const { code: pathCode } = useParams();
  const [searchParams] = useSearchParams();

  const { view, indicator: urlIndicator, year: urlYear } = parseRegionsMapLocation(
    location.pathname,
    searchParams,
  );

  // Legacy query на /regions?view=map… → канон /russia/region/map/{code}?year=
  useEffect(() => {
    const hub = regionHubPath();
    if (
      location.pathname !== hub
      && location.pathname !== `${hub}/`
      && location.pathname !== '/regions'
      && location.pathname !== '/regions/'
    ) return;
    if (searchParams.get('view') !== 'map') return;
    const next = buildRegionsMapLocation({
      view: 'map',
      indicator: urlIndicator || DEFAULT_MAP_CODE,
      year: urlYear,
    });
    navigate(`${next.pathname}${next.search}`, { replace: true });
  }, [location.pathname, searchParams, urlIndicator, urlYear, navigate]);

  const isOverview = urlIndicator === MAP_OVERVIEW;
  const activeMapCode = view !== 'map' || isOverview
    ? null
    : (urlIndicator || pathCode || DEFAULT_MAP_CODE);
  const isCustomMetric = !!(activeMapCode && !PRESET_CODES.has(activeMapCode));

  const customName = useMemo(() => {
    if (!isCustomMetric || !activeMapCode) return '';
    const sections = catalog.data?.sections || [];
    for (const s of sections) {
      const hit = s.indicators.find((i) => i.code === activeMapCode);
      if (hit) return hit.name;
    }
    return activeMapCode;
  }, [isCustomMetric, activeMapCode, catalog.data]);

  const series = useRegionsHeatmapSeries(activeMapCode, view === 'map' && !!activeMapCode);
  const mapCardRef = useRef(null);
  const [exportingMap, setExportingMap] = useState(false);
  const [exportingGif, setExportingGif] = useState(false);

  const seriesYears = series.data?.years || null;

  // Год — из URL (?year=); если нет или вне ряда — последний доступный.
  const mapYear = useMemo(() => {
    if (!seriesYears?.length) return null;
    if (urlYear != null && seriesYears.includes(urlYear)) return urlYear;
    return seriesYears[seriesYears.length - 1];
  }, [seriesYears, urlYear]);

  const syncMapUrl = useCallback((next) => {
    const desired = buildRegionsMapLocation(next);
    const current = { pathname: location.pathname, search: location.search || '' };
    if (locationsEqual(desired, current)) return;
    navigate(`${desired.pathname}${desired.search}`, { replace: true });
  }, [navigate, location.pathname, location.search]);

  const mapIndicatorParam = isOverview ? MAP_OVERVIEW : activeMapCode;

  const setMapYear = useCallback((y) => {
    syncMapUrl({
      view: 'map',
      indicator: mapIndicatorParam,
      year: y,
    });
  }, [syncMapUrl, mapIndicatorParam]);

  const contrastHeat0 = useRegionsHeatmap(CONTRAST_METRICS[0].code, view === 'list');
  const contrastHeat1 = useRegionsHeatmap(CONTRAST_METRICS[1].code, view === 'list');
  const contrastHeat2 = useRegionsHeatmap(CONTRAST_METRICS[2].code, view === 'list');
  const contrastHeat3 = useRegionsHeatmap(CONTRAST_METRICS[3].code, view === 'list');
  const contrastHeat4 = useRegionsHeatmap(CONTRAST_METRICS[4].code, view === 'list');
  const contrastHeat5 = useRegionsHeatmap(CONTRAST_METRICS[5].code, view === 'list');
  const contrastHeats = [contrastHeat0, contrastHeat1, contrastHeat2, contrastHeat3, contrastHeat4, contrastHeat5];
  const [contrastPage, setContrastPage] = useState(0);
  const contrastStart = contrastPage * CONTRAST_PAGE_SIZE;
  const contrastVisible = CONTRAST_METRICS.slice(contrastStart, contrastStart + CONTRAST_PAGE_SIZE)
    .map((m, i) => ({ ...m, heat: contrastHeats[contrastStart + i] }));

  const setView = (v) => {
    if (v === 'list') {
      syncMapUrl({ view: 'list' });
    } else {
      syncMapUrl({
        view: 'map',
        indicator: mapIndicatorParam || DEFAULT_MAP_CODE,
        year: activeMapCode && mapYear != null ? mapYear : null,
      });
    }
    track(events.REGIONS_VIEW_TOGGLE, { view: v });
  };

  const selectOverview = () => {
    syncMapUrl({ view: 'map', indicator: MAP_OVERVIEW });
    track(events.REGIONS_MAP_METRIC, { metric: 'overview' });
  };

  const selectPreset = (m) => {
    syncMapUrl({ view: 'map', indicator: m.code });
    track(events.REGIONS_MAP_METRIC, { metric: t(m.labelKey) });
  };

  const selectCustom = (i) => {
    syncMapUrl({ view: 'map', indicator: i.code });
    track(events.REGIONS_MAP_METRIC, { metric: `search:${i.code}` });
  };

  const clearCustom = () => {
    syncMapUrl({ view: 'map', indicator: DEFAULT_MAP_CODE });
  };

  const heatmapValues = useMemo(() => {
    if (!series.data || mapYear == null) return null;
    const slice = series.data.values_by_year[String(mapYear)];
    if (!slice) return null;
    return new Map(Object.entries(slice));
  }, [series.data, mapYear]);

  const namesBySlug = useMemo(() => {
    const out = {};
    (data?.districts || []).forEach((d) => d.regions.forEach((r) => { out[r.slug] = r.name; }));
    return out;
  }, [data]);

  const mapMetaTitle = series.data?.indicator?.name
    ? t('regions.mapTitle', { name: series.data.indicator.name })
    : isOverview
      ? t('regions.mapOverviewTitle')
      : t('regions.hubTitle');
  const mapMetaDesc = t('regions.hubDesc');

  useDocumentMeta({
    title: view === 'map' ? mapMetaTitle : t('regions.hubTitle'),
    description: mapMetaDesc,
    path: view === 'map'
      ? buildRegionsMapHref({
        view: 'map',
        indicator: mapIndicatorParam,
        year: activeMapCode && urlYear != null ? urlYear : null,
      })
      : regionHubPath(),
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = normalize(deferredQuery);
    const searching = q.length > 0;
    return data.districts
      .filter((d) => searching || !activeDistrict || d.slug === activeDistrict)
      .map((d) => ({
        ...d,
        regions: searching
          ? d.regions.filter((r) => normalize(r.name).includes(q))
          : d.regions,
      }))
      .filter((d) => d.regions.length > 0);
  }, [data, deferredQuery, activeDistrict]);

  const totalShown = filtered.reduce((n, d) => n + d.regions.length, 0);

  useSearchTracking('regions-list', deferredQuery, totalShown);

  const handlePng = async () => {
    if (exportingMap) return;
    if (!isAuthed) {
      track(events.CHART_IMAGE_BLOCKED, { indicator: `regions-map:${activeMapCode || 'overview'}` });
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return;
    }
    setExportingMap(true);
    const ok = await exportNodeToPng(mapCardRef.current, {
      filename: `regions-map_${activeMapCode || 'overview'}.png`,
      watermark: false,
    }).catch(() => false);
    setExportingMap(false);
    if (ok) track(events.CHART_IMAGE_DOWNLOAD, { indicator: `regions-map:${activeMapCode || 'overview'}` });
  };

  const handleGif = async () => {
    if (exportingGif) return;
    if (!isAuthed) {
      track(events.REGIONS_MAP_GIF_BLOCKED, { indicator: activeMapCode || 'overview' });
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return;
    }
    if (!series.data || !seriesYears || seriesYears.length < 2) return;
    setExportingGif(true);
    try {
      const blob = await buildRegionsMapGif(series.data);
      downloadBlob(blob, `regions-map_${activeMapCode}.gif`);
      track(events.REGIONS_MAP_GIF_DOWNLOAD, {
        indicator: activeMapCode,
        years: seriesYears.length,
      });
    } catch {
      /* генерация сорвалась — молча, без файла */
    }
    setExportingGif(false);
  };

  const gifAvailable = !!(activeMapCode && seriesYears && seriesYears.length > 1 && series.data);

  return (
    <div className="mx-auto w-full max-w-7xl overflow-x-clip px-4 pb-24 pt-24 sm:px-6">
      <div className="mb-8">
        <div className="flex items-center gap-2 text-champagne text-xs font-mono uppercase tracking-widest mb-3">
          <MapPin size={14} />
          {t('regions.eyebrow')}
        </div>
        <h1 className="font-display text-[1.75rem] font-bold leading-tight text-text-primary sm:text-4xl">
          {t('regions.h1')}
        </h1>
        <p className="mt-3 max-w-2xl text-[14px] leading-relaxed text-text-secondary sm:text-[15px]">
          {t('regions.intro')}
        </p>
        {data && (
          <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs font-mono text-text-tertiary">
            <span className="inline-flex items-center gap-1.5">
              <Database size={12} />
              {t('regions.stat.values', {
                n: data.totals.points.toLocaleString(locale === 'en' ? 'en-US' : 'ru-RU'),
              })}
            </span>
            <span>{t('regions.stat.indicators', { n: data.totals.indicators })}</span>
            <span>{t('regions.stat.regions', { n: data.totals.regions })}</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-1 mb-2 bg-surface border border-border-subtle rounded-xl p-1 w-fit" role="tablist" aria-label={t('regions.viewAria')}>
        <button
          role="tab"
          aria-selected={view === 'list'}
          onClick={() => setView('list')}
          className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            view === 'list' ? 'bg-champagne/15 text-champagne' : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <List size={15} /> {t('regions.view.list')}
        </button>
        <button
          role="tab"
          aria-selected={view === 'map'}
          onClick={() => setView('map')}
          className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            view === 'map' ? 'bg-champagne/15 text-champagne' : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <MapIcon size={15} /> {t('regions.view.map')}
        </button>
      </div>

      {view === 'list' && (
        <>
          {contrastVisible.some((m) => m.heat.data) && (
            <div data-block="contrasts" className="mb-4 bg-surface border border-border-subtle rounded-xl p-4 space-y-2">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-mono uppercase tracking-widest text-champagne">
                  {t('regions.contrasts')}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    const next = (contrastPage + 1) % CONTRAST_PAGES;
                    setContrastPage(next);
                    track(events.REGIONS_CONTRASTS_SHUFFLE, { page: next });
                  }}
                  title={t('regions.contrasts.shuffleTitle')}
                  aria-label={t('regions.contrasts.shuffleAria')}
                  className="p-2 -m-1 text-text-tertiary transition-colors hover:text-champagne"
                >
                  <RefreshCw size={13} />
                </button>
              </div>
              {contrastVisible.map((m) => (
                <ContrastRow key={m.code} heat={m.heat} metricLabel={t(m.labelKey)} betterIsLow={m.betterIsLow} />
              ))}
            </div>
          )}

          <div className="relative mb-6">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-tertiary" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('regions.searchPlaceholder')}
              className="w-full rounded-xl border border-border-subtle bg-surface py-3 pl-10 pr-4 text-sm text-text-primary shadow-sm placeholder:text-text-tertiary focus:border-border-champagne focus:outline-none"
              aria-label={t('regions.searchAria')}
            />
          </div>

          {isError && <ApiRetryBanner onRetry={refetch} retrying={isFetching} />}

          {isLoading && (
            <div className="grid gap-2 sm:grid-cols-2">
              {Array.from({ length: 10 }).map((_, i) => <SkeletonBox key={i} className="h-16 rounded-xl" />)}
            </div>
          )}

          {!isLoading && (() => {
            const searching = normalize(deferredQuery).length > 0;
            const districtNav = data?.districts || [];
            const resolvedDistrict = activeDistrict
              && districtNav.some((d) => d.slug === activeDistrict)
              ? activeDistrict
              : null;
            const totalRegions = districtNav.reduce((n, d) => n + d.regions.length, 0);

            return (
              <>
                {!searching && (
                  <MobileNavSelect
                    label={t('regions.districts')}
                    value={resolvedDistrict || ''}
                    onChange={(v) => setActiveDistrict(v || null)}
                    options={[
                      { value: '', label: t('regions.allDistricts'), count: totalRegions },
                      ...districtNav.map((d) => ({
                        value: d.slug,
                        label: locale === 'en'
                          ? d.name
                          : (DISTRICT_SHORT_KEYS[d.slug] ? t(DISTRICT_SHORT_KEYS[d.slug]) : d.name),
                        count: d.regions.length,
                      })),
                    ]}
                  />
                )}

                <div className={searching
                  ? 'min-w-0 space-y-8'
                  : 'grid min-w-0 gap-6 lg:grid-cols-[250px_minmax(0,1fr)]'}
                >
                  {!searching && (
                    <aside className="hidden min-w-0 lg:sticky lg:top-24 lg:block lg:self-start" aria-label={t('regions.districts')}>
                      <div className="mb-2 px-2 text-[10px] font-mono uppercase tracking-[0.18em] text-text-tertiary">
                        {t('regions.districts')}
                      </div>
                      <div className="flex flex-col gap-2">
                        <button
                          type="button"
                          onClick={() => setActiveDistrict(null)}
                          className={[
                            'flex items-center justify-between gap-4 rounded-xl px-3.5 py-2.5 text-left text-sm transition-colors',
                            !resolvedDistrict
                              ? 'bg-champagne/12 font-medium text-champagne'
                              : 'bg-surface text-text-secondary hover:bg-surface-hover hover:text-text-primary',
                          ].join(' ')}
                        >
                          <span>{t('regions.allDistricts')}</span>
                          <span className="font-mono text-[10px] opacity-60">{totalRegions}</span>
                        </button>
                        {districtNav.map((d) => (
                          <button
                            key={d.slug}
                            type="button"
                            onClick={() => setActiveDistrict(d.slug)}
                            className={[
                              'flex items-center justify-between gap-4 rounded-xl px-3.5 py-2.5 text-left text-sm transition-colors',
                              resolvedDistrict === d.slug
                                ? 'bg-champagne/12 font-medium text-champagne'
                                : 'bg-surface text-text-secondary hover:bg-surface-hover hover:text-text-primary',
                            ].join(' ')}
                          >
                            <span className="min-w-0 truncate">
                              {locale === 'en'
                                ? d.name
                                : (DISTRICT_SHORT_KEYS[d.slug] ? t(DISTRICT_SHORT_KEYS[d.slug]) : d.name)}
                            </span>
                            <span className="shrink-0 font-mono text-[10px] opacity-60">{d.regions.length}</span>
                          </button>
                        ))}
                      </div>
                    </aside>
                  )}

                  <div className="min-w-0 space-y-8">
                    {filtered.map((d) => (
                      <section key={d.slug} aria-labelledby={`district-${d.slug}`}>
                        <div className="mb-3 flex items-end justify-between gap-3 sm:mb-4 sm:gap-4">
                          <div className="min-w-0">
                            <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-champagne">
                              {searching ? t('regions.searchResults') : t('regions.regionsLabel')}
                            </div>
                            <h2 id={`district-${d.slug}`} className="mt-1 font-display text-xl font-bold leading-snug text-text-primary sm:text-2xl">
                              {d.name}
                            </h2>
                          </div>
                          <span className="shrink-0 font-mono text-xs text-text-tertiary">{d.regions.length}</span>
                        </div>
                        <div className="grid gap-2 sm:grid-cols-2 sm:gap-2.5">
                          {d.regions.map((r) => <RegionCard key={r.slug} region={r} />)}
                        </div>
                      </section>
                    ))}
                    {totalShown === 0 && searching && (
                      <div className="rounded-2xl border border-border-subtle bg-surface p-5 text-center text-sm text-text-secondary sm:p-6">
                        {t('regions.home.noRegions', { query })}
                      </div>
                    )}
                  </div>
                </div>
              </>
            );
          })()}
        </>
      )}

      {view === 'map' && (
        <div className="mt-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center mb-3">
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-hide min-w-0" role="tablist" aria-label={t('regions.map.metricAria')}>
              <button
                role="tab"
                aria-selected={isOverview}
                onClick={selectOverview}
                title={t('regions.home.mapClickTitle')}
                className={`min-h-9 shrink-0 rounded-full px-3.5 py-2 text-xs font-medium transition-colors ${
                  isOverview
                    ? 'bg-champagne/15 text-champagne'
                    : 'bg-surface border border-border-subtle text-text-secondary hover:text-text-primary'
                }`}
              >
                {t('regions.map.overview')}
              </button>
              {MAP_METRICS.map((m) => {
                const selected = !isOverview && !isCustomMetric && activeMapCode === m.code;
                return (
                  <button
                    key={m.code}
                    role="tab"
                    aria-selected={selected}
                    onClick={() => selectPreset(m)}
                    className={`min-h-9 shrink-0 rounded-full px-3.5 py-2 text-xs font-medium transition-colors ${
                      selected
                        ? 'bg-champagne/15 text-champagne'
                        : 'bg-surface border border-border-subtle text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    {t(m.labelKey)}
                  </button>
                );
              })}
            </div>
            <MapMetricSearch
              activeCode={isCustomMetric ? activeMapCode : null}
              activeName={customName}
              onPick={selectCustom}
              onClear={clearCustom}
            />
          </div>

          <div data-block="regions-map" className="bg-surface border border-border-subtle rounded-xl p-3 sm:p-5 relative" ref={mapCardRef}>
            <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
              <div className="text-xs text-text-tertiary min-w-0">
                {activeMapCode && series.data ? (
                  t('regions.home.mapCaptionMetric', {
                    name: series.data.indicator.name,
                    yearBit: mapYear != null ? t('regions.home.mapYearBit', { year: mapYear }) : '',
                    unitBit: series.data.indicator.unit
                      ? t('regions.home.mapUnitBit', { unit: series.data.indicator.unit })
                      : '',
                  })
                ) : (
                  t('regions.home.mapCaptionOverview')
                )}
              </div>
              <div className="shrink-0 flex items-center gap-1.5" data-no-export="true">
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
                <button
                  type="button"
                  disabled={exportingGif || !gifAvailable}
                  onClick={handleGif}
                  title={
                    !gifAvailable
                      ? t('download.mapGifNeedHistory')
                      : (isAuthed ? t('download.mapGif') : t('download.afterRegister'))
                  }
                  aria-label={t('download.mapGif')}
                  className="inline-flex min-h-9 items-center gap-1 rounded-full border border-border-subtle px-3 py-2 text-xs text-text-tertiary transition-colors hover:border-border-champagne hover:text-champagne disabled:opacity-50"
                >
                  <Film size={12} /> {exportingGif ? t('download.mapGifBusy') : 'GIF'}
                </button>
              </div>
            </div>
            <Suspense fallback={<SkeletonBox className="h-80 rounded-xl" />}>
              <RegionsMap
                valuesBySlug={activeMapCode ? heatmapValues : null}
                transitionMs={activeMapCode ? 650 : 150}
                unit={series.data?.indicator?.unit || ''}
                nameBySlug={namesBySlug}
                brandMark
                onSelect={(slug) => {
                  track(events.REGIONS_MAP_SELECT, { region: slug, metric: activeMapCode || 'overview' });
                  navigate(activeMapCode ? regionIndicatorPath(slug, activeMapCode) : regionPath(slug));
                }}
              />
            </Suspense>

            {activeMapCode && seriesYears && seriesYears.length > 1 && mapYear != null && (
              <Suspense fallback={null}>
                <MapTimeline
                  key={activeMapCode}
                  years={seriesYears}
                  year={mapYear}
                  onYearChange={setMapYear}
                  metric={activeMapCode}
                />
              </Suspense>
            )}
          </div>
          <p className="mt-3 text-xs text-text-tertiary leading-relaxed">
            {activeMapCode
              ? t('regions.home.mapHintMetric')
              : t('regions.home.mapHintOverview')}
            {t('regions.home.mapHintCities')}
          </p>
        </div>
      )}
    </div>
  );
}
