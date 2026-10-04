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
  Search, MapPin, ChevronRight, List, Map as MapIcon, ChevronDown,
  Image as ImageIcon, Film, X, RefreshCw,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  useRegionsLanding, useRegionsHeatmap, useRegionsHeatmapSeries,
  useRegionsCatalog,
} from '../lib/regionsApi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import Spinner from '../components/Spinner';
import Button from '../components/Button';
import { RegionSearchField, RegionSectionHeading } from '../components/regions/RegionParts';
import { formatRegionCompact, formatRegionWithUnit, unitLabel } from '../lib/regionUi';
import { rememberScroll, useRestoreScroll } from '../lib/keepScroll';
import MobileNavSelect from '../components/MobileNavSelect';
import Breadcrumbs from '../components/Breadcrumbs';
import { regionsTrail } from '../lib/breadcrumbs';
import { exportNodeToPng } from '../lib/chartImage';
import { buildRegionsMapGif, downloadBlob } from '../lib/regionsMapGif';
import {
  parseRegionsMapLocation, buildRegionsMapLocation, buildRegionsMapHref,
  locationsEqual, MAP_OVERVIEW, DEFAULT_MAP_CODE, resolveRegionsMapPaint,
} from '../lib/regionsMapUrl';
import { track, events } from '../lib/track';
import useSearchTracking from '../lib/useSearchTracking';
import { filterSearchOptions, normalizeSearchQuery } from '../lib/searchSynonyms';
import { useAuth } from '../context/authContext';
import {
  regionHubPath,
  regionIndicatorPath,
  regionPath,
  regionRatingHubPath,
  regionRatingPath,
} from '../lib/sitePaths';
import { useLocale } from '../i18n';
import '../styles/platform-pages.css';
import '../styles/regions-w4.css';

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

function MapMetricSearch({ activeCode, onPick, onClear, activeName }) {
  const { t, locale } = useLocale();
  const catalog = useRegionsCatalog();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [resultLimit, setResultLimit] = useState(50);

  const results = useMemo(() => {
    const sections = catalog.data?.sections || [];
    const all = sections.flatMap((s) =>
      s.indicators.map((i) => ({ ...i, section: s.name })));
    return filterSearchOptions(all, query);
  }, [catalog.data, query]);

  useSearchTracking('map-metric', open ? query : '', results.length);

  const isCustom = !!activeCode;
  const openWith = (q) => { setOpen(true); setQuery(q); setResultLimit(50); };

  return (
    <div className="relative min-w-0 flex-1 sm:max-w-xs">
      <div className={`flex min-h-11 items-center gap-2 rounded-xl border px-3 text-sm transition-colors ${
        isCustom
          ? 'border-transparent bg-champagne/15 text-champagne-ink'
          : 'border-border-subtle bg-surface text-text-secondary focus-within:border-border-champagne'
      }`}
      >
        <Search size={14} className="shrink-0" aria-hidden="true" />
        <input
          type="text"
          value={open ? query : (isCustom ? activeName : '')}
          placeholder={t('regions.map.customPlaceholder')}
          onFocus={() => openWith('')}
          onClick={() => { if (!open) openWith(''); }}
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
        <div className="absolute right-0 sm:left-0 sm:right-auto z-30 mt-2 w-[min(calc(100vw-2rem),26rem)] max-h-72 overflow-auto rounded-xl border border-border-subtle bg-surface shadow-2xl">
          {catalog.isLoading ? (
            <div className="px-3.5 py-3 text-sm text-text-secondary">{t('regions.home.loadingCatalog')}</div>
          ) : results.length === 0 ? (
            <div className="px-3.5 py-3 text-sm text-text-secondary">
              {t('regions.home.nothingFound', { query })}
            </div>
          ) : (
            results.slice(0, resultLimit).map((i) => (
              <button
                key={i.code}
                type="button"
                onMouseDown={(e) => { e.preventDefault(); onPick(i); setOpen(false); setQuery(''); }}
                className="fe-tap w-full px-3.5 py-2 text-left hover:bg-surface-hover transition-colors"
              >
                <div className="text-sm text-text-primary leading-snug">{i.name}</div>
                <div className="text-xs text-text-secondary">{i.section}</div>
              </button>
            ))
          )}
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

const CONTRAST_METRICS = [
  { code: 'srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy', labelKey: 'regions.metric.wages' },
  { code: 'uroven-bezrabotitsy', labelKey: 'regions.metric.unemployment', betterIsLow: true },
  { code: 'valovoy-regionalnyy-produkt-na-dushu-naseleniya', labelKey: 'regions.metric.grpPerCapita' },
  { code: 'chislennost-naseleniya-s-denezhnymi-dohodami-nizhe-granitsy', labelKey: 'regions.metric.poverty', betterIsLow: true },
  { code: 'investitsii-v-osnovnoy-kapital', labelKey: 'regions.metric.investment' },
  { code: 'chislennost-naseleniya', labelKey: 'regions.metric.population', neutral: true },
];
const CONTRAST_PAGE_SIZE = 2;
const CONTRAST_PAGES = Math.ceil(CONTRAST_METRICS.length / CONTRAST_PAGE_SIZE);

/** Пара «лидер — аутсайдер»: две аккуратные половинки и разница в разах, без оторванных слов. */
function ContrastRow({ heat, metricLabel, betterIsLow = false, neutral = false }) {
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
  const ratio = second.value ? Math.abs(first.value / second.value) : null;
  const ratioLabel = ratio && ratio >= 1.05
    ? `× ${ratio.toLocaleString(locale === 'en' ? 'en-US' : 'ru-RU', { maximumFractionDigits: 1 })}`
    : null;
  const side = (row, tone) => (
    <Link
      to={regionIndicatorPath(row.slug, code)}
      className="fe-contrast-side fe-press block transition-colors hover:bg-obsidian-lighter"
    >
      <span className="block text-[13px] leading-snug text-text-primary">{row.name}</span>
      <span className={`fe-num mt-1 block whitespace-nowrap text-[17px] font-semibold ${tone}`}>
        {formatRegionCompact(row.value, unit, locale)}
      </span>
    </Link>
  );
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-text-secondary">{metricLabel}</span>
        {ratioLabel && <span className="fe-contrast-ratio" title={t('regions.contrasts.ratioTitle')}>{ratioLabel}</span>}
      </div>
      <div className="fe-contrast-pair">
        {side(first, neutral ? 'text-text-primary' : 'fe-ink-pos')}
        {side(second, neutral ? 'text-text-primary' : 'fe-ink-neg')}
      </div>
    </div>
  );
}

function RegionCard({ region }) {
  const { t, locale } = useLocale();
  const pop = region.stats['1.1'];
  const wage = region.stats['3.4'];
  const unemp = region.stats['2.10.1'];
  const mini = (label, text) => (
    <div className="min-w-0">
      <div className="text-xs text-text-secondary">{label}</div>
      <div className="fe-num mt-0.5 whitespace-nowrap text-[13px] font-medium text-text-primary">{text}</div>
    </div>
  );
  return (
    <Link
      to={regionPath(region.slug)}
      className="fe-press group flex items-center justify-between gap-3 rounded-2xl border border-border-subtle bg-surface px-3.5 py-3 transition-colors hover:border-border-champagne sm:px-4 sm:py-3.5"
    >
      <div className="min-w-0 flex-1">
        <div className="text-[15px] font-medium leading-snug text-text-primary transition-colors group-hover:text-champagne-ink">
          {region.name}
        </div>
        {(pop || wage || unemp) && (
          <div className="mt-2 grid grid-cols-3 gap-2">
            {mini(t('w4.regions.card.pop'), pop ? formatRegionCompact(pop.value, pop.unit, locale) : '\u2014')}
            {mini(t('w4.regions.card.wage'), wage ? formatRegionWithUnit(wage.value, '₽', locale) : '\u2014')}
            {mini(t('w4.regions.card.unemp'), unemp ? formatRegionWithUnit(unemp.value, '%', locale) : '\u2014')}
          </div>
        )}
      </div>
      <ChevronRight size={16} className="hidden shrink-0 text-text-secondary transition-colors group-hover:text-champagne-ink sm:block" aria-hidden="true" />
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
  useRestoreScroll();

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

  const mapOn = view === 'map' && !!activeMapCode;
  // heatmap последнего года — первый кадр choropleth (~8 КБ).
  // series (все годы) — после heatmap, иначе оба бьют один public pool.
  const heatmap = useRegionsHeatmap(activeMapCode, mapOn);
  const series = useRegionsHeatmapSeries(
    activeMapCode,
    mapOn && (heatmap.isSuccess || heatmap.isError),
  );
  const mapCardRef = useRef(null);
  const [exportingMap, setExportingMap] = useState(false);
  const [exportingGif, setExportingGif] = useState(false);

  const paint = useMemo(
    () => resolveRegionsMapPaint({
      heatmap: heatmap.data,
      series: series.data,
      urlYear,
    }),
    [heatmap.data, series.data, urlYear],
  );
  const seriesYears = paint.years.length ? paint.years : null;
  const mapYear = paint.year;

  const syncMapUrl = useCallback((next) => {
    const desired = buildRegionsMapLocation(next);
    const current = { pathname: location.pathname, search: location.search || '' };
    if (locationsEqual(desired, current)) return;
    // «Список/Карта» и смена показателя — один экран: не уезжаем в начало страницы.
    rememberScroll();
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

  const heatmapValues = paint.valuesBySlug;

  const namesBySlug = useMemo(() => {
    const out = {};
    (data?.districts || []).forEach((d) => d.regions.forEach((r) => { out[r.slug] = r.name; }));
    return out;
  }, [data]);

  const mapMetaTitle = paint.indicator?.name
    ? t('regions.mapTitle', { name: paint.indicator.name })
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
    const q = normalizeSearchQuery(deferredQuery);
    const searching = q.length > 0;
    return data.districts
      .filter((d) => searching || !activeDistrict || d.slug === activeDistrict)
      .map((d) => ({
        ...d,
        regions: searching
          ? filterSearchOptions(d.regions, q, { searchKind: 'region', getSearchItem: (item) => ({ ...item, country_slug: 'russia' }) })
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

  const gifAvailable = !!(activeMapCode && paint.hasHistory && series.data);

  return (
    <div className="fe-data-page mx-auto w-full max-w-7xl overflow-x-clip px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs items={regionsTrail()} className="mb-6" />
      <div className="mb-6">
        <div className="mb-2 inline-flex items-center gap-1.5 text-sm font-medium text-champagne-ink">
          <MapPin size={15} aria-hidden="true" />
          {t('regions.eyebrow')}
        </div>
        <h1 className="font-display text-[1.75rem] font-bold leading-tight text-text-primary sm:text-4xl">
          {t('regions.h1')}
        </h1>
        <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-text-secondary">
          {t('regions.intro')}
        </p>
        {data && (
          <p className="mt-2 text-sm text-text-secondary">
            {t('w4.regions.scope', { n: data.totals.regions })}
          </p>
        )}
        <section className="mt-5" aria-labelledby="regions-rankings-title">
          <h2 id="regions-rankings-title" className="text-base font-semibold text-text-primary">
            <Link to={regionRatingHubPath()} className="fe-tap-inline hover:text-champagne-ink">
              {t('russia.link.ratings.title')}
            </Link>
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-text-secondary">
            {t('regions.hub.ratingsLead')}
          </p>
          <div className="fe-scroll-row mt-3">
            {MAP_METRICS.map((metric) => (
              <Link
                key={metric.code}
                to={regionRatingPath(metric.code)}
                className="fe-chip fe-press"
              >
                {t('regions.ratingLink', { name: t(metric.labelKey) })}
              </Link>
            ))}
          </div>
        </section>
      </div>

      <div className="mb-3 flex w-fit items-center gap-1 rounded-2xl border border-border-subtle bg-surface p-1" role="tablist" aria-label={t('regions.viewAria')}>
        <button
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

      {view === 'list' && (
        <>
          {contrastVisible.some((m) => m.heat.data) ? (
            <div data-block="contrasts" className="fe-reveal mb-4 space-y-4 rounded-3xl border border-border-subtle bg-surface p-4">
              <div className="flex items-center justify-between gap-3">
                <h2 className="font-display text-lg font-bold text-text-primary">
                  {t('regions.contrasts')}
                </h2>
                <button
                  type="button"
                  onClick={() => {
                    const next = (contrastPage + 1) % CONTRAST_PAGES;
                    setContrastPage(next);
                    track(events.REGIONS_CONTRASTS_SHUFFLE, { page: next });
                  }}
                  title={t('regions.contrasts.shuffleTitle')}
                  aria-label={t('regions.contrasts.shuffleAria')}
                  className="fe-chip fe-press gap-1.5 text-champagne-ink"
                >
                  <RefreshCw size={14} aria-hidden="true" />
                  {t('w4.regions.shuffle')}
                </button>
              </div>
              {contrastVisible.map((m) => (
                <ContrastRow
                  key={m.code}
                  heat={m.heat}
                  metricLabel={t(m.labelKey)}
                  betterIsLow={m.betterIsLow}
                  neutral={m.neutral}
                />
              ))}
            </div>
          ) : contrastVisible.some((m) => m.heat.isLoading) ? (
            <SkeletonBox className="mb-4 h-[236px] rounded-3xl" />
          ) : null}

          <RegionSearchField
            className="mb-6"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('regions.searchPlaceholder')}
            ariaLabel={t('regions.searchAria')}
          />

          {isError && (
            <ApiRetryBanner onRetry={refetch} isFetching={isFetching} className="mb-6">
              {t('pgui.regions.loadError')}
            </ApiRetryBanner>
          )}

          {isLoading && (
            <div className="grid gap-2 sm:grid-cols-2 sm:gap-2.5" role="status" aria-busy="true" aria-label={t('common.loading')}>
              {Array.from({ length: 10 }).map((_, i) => <SkeletonBox key={i} className="h-[98px] rounded-xl sm:h-[78px]" />)}
            </div>
          )}

          {!isLoading && !isError && !data?.districts?.length && (
            <div className="rounded-2xl border border-border-subtle bg-surface p-5 text-center text-sm text-text-secondary sm:p-6">
              {t('pgui.regions.empty')}
            </div>
          )}

          {!isLoading && (() => {
            const searching = normalizeSearchQuery(deferredQuery).length > 0;
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
                      { value: '', label: t('w4.regions.allRegions'), count: totalRegions },
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
                      <div className="mb-2 px-2 text-sm font-medium text-text-secondary">
                        {t('regions.districts')}
                      </div>
                      <div className="flex flex-col gap-2">
                        <button
                          type="button"
                          onClick={() => setActiveDistrict(null)}
                          className={[
                            'fe-tap flex items-center justify-between gap-4 rounded-xl px-3.5 py-2.5 text-left text-sm transition-colors',
                            !resolvedDistrict
                              ? 'bg-champagne/12 font-medium text-champagne-ink'
                              : 'bg-surface text-text-secondary hover:bg-surface-hover hover:text-text-primary',
                          ].join(' ')}
                        >
                          <span>{t('w4.regions.allRegions')}</span>
                          <span className="fe-num text-xs">{totalRegions}</span>
                        </button>
                        {districtNav.map((d) => (
                          <button
                            key={d.slug}
                            type="button"
                            onClick={() => setActiveDistrict(d.slug)}
                            className={[
                              'fe-tap flex items-center justify-between gap-4 rounded-xl px-3.5 py-2.5 text-left text-sm transition-colors',
                              resolvedDistrict === d.slug
                                ? 'bg-champagne/12 font-medium text-champagne-ink'
                                : 'bg-surface text-text-secondary hover:bg-surface-hover hover:text-text-primary',
                            ].join(' ')}
                          >
                            <span className="min-w-0 truncate">
                              {locale === 'en'
                                ? d.name
                                : (DISTRICT_SHORT_KEYS[d.slug] ? t(DISTRICT_SHORT_KEYS[d.slug]) : d.name)}
                            </span>
                            <span className="fe-num shrink-0 text-xs">{d.regions.length}</span>
                          </button>
                        ))}
                      </div>
                    </aside>
                  )}

                  <div className="min-w-0 space-y-8">
                    {filtered.map((d) => (
                      <section key={d.slug} aria-labelledby={`district-${d.slug}`}>
                        <RegionSectionHeading
                          id={`district-${d.slug}`}
                          eyebrow={searching ? t('regions.searchResults') : null}
                          title={d.name}
                          count={d.regions.length}
                        />
                        <div className="grid gap-2 sm:grid-cols-2 sm:gap-2.5">
                          {d.regions.map((r) => <RegionCard key={r.slug} region={r} />)}
                        </div>
                      </section>
                    ))}
                    {totalShown === 0 && searching && (
                      <div className="rounded-3xl border border-border-subtle bg-surface p-6 text-center text-sm text-text-secondary">
                        <MapPin size={22} className="mx-auto mb-2 text-champagne-ink" aria-hidden="true" />
                        {t('regions.home.noRegions', { query })}
                        <div className="mt-3">
                          <Button variant="secondary" size="sm" onClick={() => setQuery('')}>{t('regions.profile.resetSearch')}</Button>
                        </div>
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
          <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="fe-scroll-row min-w-0 sm:flex-1" role="tablist" aria-label={t('regions.map.metricAria')}>
              <button
                type="button"
                role="tab"
                aria-selected={isOverview}
                onClick={selectOverview}
                title={t('regions.home.mapClickTitle')}
                className={`fe-chip fe-press ${isOverview ? 'is-active' : ''}`}
              >
                {t('regions.map.overview')}
              </button>
              {MAP_METRICS.map((m) => {
                const selected = !isOverview && !isCustomMetric && activeMapCode === m.code;
                return (
                  <button
                    key={m.code}
                    type="button"
                    role="tab"
                    aria-selected={selected}
                    onClick={() => selectPreset(m)}
                    className={`fe-chip fe-press ${selected ? 'is-active' : ''}`}
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

          <div id="chart" data-block="regions-map" className="relative rounded-3xl border border-border-subtle bg-surface p-3 sm:p-5" ref={mapCardRef}>
            <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                {activeMapCode && paint.indicator ? (
                  <>
                    <div className="text-sm font-medium leading-snug text-text-primary">{paint.indicator.name}</div>
                    <div className="mt-0.5 text-xs text-text-secondary">
                      {[
                        mapYear != null ? t('w4.map.yearLabel', { year: mapYear }) : null,
                        unitLabel(paint.indicator.unit, locale) || paint.indicator.unit,
                      ].filter(Boolean).join(', ')}
                    </div>
                  </>
                ) : (
                  <div className="text-sm text-text-secondary">{t('regions.home.mapCaptionOverview')}</div>
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
                  className="fe-chip fe-press gap-1 border-border-subtle"
                >
                  <Film size={13} aria-hidden="true" /> {exportingGif ? t('download.mapGifBusy') : 'GIF'}
                </button>
              </div>
            </div>
            {mapOn && heatmap.isError && (
              <ApiRetryBanner onRetry={heatmap.refetch} isFetching={heatmap.isFetching} className="mb-3">
                {t('pgui.regions.mapError')}
              </ApiRetryBanner>
            )}
            {mapOn && heatmap.isLoading && (
              <div className="mb-2 flex items-center gap-2 text-xs text-text-secondary" role="status">
                <Spinner size={14} />
                {t('pgui.regions.mapLoading')}
              </div>
            )}
            {mapOn && heatmap.isSuccess && heatmapValues.size === 0 && (
              <div role="status" className="mb-3 rounded-2xl bg-obsidian-light px-4 py-3 text-sm text-text-secondary">
                <p>{t('w4.map.emptyTitle')}</p>
                {activeMapCode !== DEFAULT_MAP_CODE && (
                  <Button variant="secondary" size="sm" className="mt-2" onClick={clearCustom}>
                    {t('w4.map.emptyAction')}
                  </Button>
                )}
              </div>
            )}
            <Suspense fallback={<SkeletonBox className="aspect-[1000/538] w-full rounded-2xl" />}>
              <RegionsMap
                valuesBySlug={activeMapCode ? heatmapValues : null}
                transitionMs={activeMapCode ? 650 : 150}
                unit={paint.indicator?.unit || ''}
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
          <div className="mt-3 text-sm leading-relaxed text-text-secondary">
            <p>{activeMapCode ? t('w4.map.hintMetric') : t('w4.map.hintOverview')}</p>
            <details className="fe-acc mt-1">
              <summary className="fe-tap-inline gap-1 text-champagne-ink">
                {t('w4.map.howToRead')}
                <ChevronDown size={14} className="fe-acc__chev" aria-hidden="true" />
              </summary>
              <p className="mt-1">{t('w4.map.howToReadBody')}</p>
            </details>
          </div>
        </div>
      )}
    </div>
  );
}
