// Ряд субнационального показателя: /{country}/region/{slug}/{code}
// Эталон — RegionIndicatorPage: RegionAnnualChart + сравнение + страна + YoY +
// CSV/Excel/PNG (только для зарегистрированных), сетка StatCell, таблица.
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import {
  Trophy, Table2, ChevronDown, ArrowUpRight,
  Download, Image as ImageIcon, GitCompare,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  useWorldRegionIndicator, useWorldRegionForecast, useWorldRegionsHub, formatSubnationalValue,
} from '../lib/worldSubnationalApi';
import { yearDelta } from '../lib/regionsApi';
import RegionAnnualChart from '../components/RegionAnnualChart';
import IndicatorMethodologyPanel from '../components/IndicatorMethodologyPanel';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import { useAuth } from '../context/authContext';
import { exportTable } from '../lib/api';
import { exportNodeToPng } from '../lib/chartImage';
import { track, events } from '../lib/track';
import { worldSubnationalIndicatorTrail } from '../lib/breadcrumbs';
import {
  RUSSIA,
  countryRegionIndicatorPath,
  countryRegionIndicatorYearPath,
  countryRegionPath,
  countryRegionsPath,
  indicatorPath,
  indicatorYearPath,
  regionIndicatorPath,
} from '../lib/sitePaths';
import { useLocale } from '../i18n';

function toYoYSeries(series) {
  if (!series?.length) return [];
  const byYear = new Map(series.map((p) => [p.year, p.value]));
  return series
    .filter((p) => {
      const prev = byYear.get(p.year - 1);
      return prev != null && prev !== 0;
    })
    .map((p) => {
      const prev = byYear.get(p.year - 1);
      return { ...p, value: +(((p.value - prev) / Math.abs(prev)) * 100).toFixed(2) };
    });
}

function isNegativeCapable(series) {
  return Array.isArray(series) && series.some((p) => p?.value != null && p.value < 0);
}

function StatCell({ label, children }) {
  return (
    <div className="fe-stat-cell min-w-0 rounded-xl border border-border-subtle bg-surface p-3 sm:p-3.5">
      <div className="truncate text-[10px] uppercase tracking-wide text-text-tertiary sm:text-[11px]">{label}</div>
      <div className="mt-1 break-words font-mono text-sm font-semibold leading-tight text-text-primary sm:text-[15px]">
        {children}
      </div>
    </div>
  );
}

function pointLabel(p, isMonthly, locale) {
  if (!p) return '';
  if (!isMonthly) return String(p.year);
  if (p.label) return p.label;
  const loc = locale === 'en' ? 'en-US' : 'ru-RU';
  try {
    return new Date(p.year, (p.month || 1) - 1, 1).toLocaleDateString(loc, { month: 'long', year: 'numeric' });
  } catch {
    return `${p.month}/${p.year}`;
  }
}

export default function WorldRegionIndicatorPage() {
  const { countrySlug, slug, code } = useParams();
  const { t, locale } = useLocale();
  const { isAuthed } = useAuth();
  const chartRef = useRef(null);
  const [compareSlug, setCompareSlug] = useState('');
  const [showNational, setShowNational] = useState(true);
  const [showYoY, setShowYoY] = useState(false);
  const [showTable, setShowTable] = useState(false);
  const [exporting, setExporting] = useState(false);

  const data = useWorldRegionIndicator(countrySlug === RUSSIA ? undefined : countrySlug, slug, code);
  const hub = useWorldRegionsHub(countrySlug === RUSSIA ? undefined : countrySlug);
  const compare = useWorldRegionIndicator(
    countrySlug === RUSSIA ? undefined : countrySlug,
    compareSlug || undefined,
    compareSlug ? code : undefined,
  );
  const forecastQ = useWorldRegionForecast(
    countrySlug === RUSSIA ? undefined : countrySlug,
    slug, code, Boolean(data.data?.series?.length),
  );

  const payload = data.data;
  const countryName = payload?.country?.name || countrySlug;
  const regionName = payload?.region?.name || slug;
  const indName = payload?.indicator?.name || code;
  const kindPlural = payload
    ? (payload.kind_label_plural || payload.kind_label)
    : t('world.regions.fallbackKindPlural');
  const series = useMemo(() => payload?.series || [], [payload]);
  const nationalSeries = useMemo(() => payload?.national?.series || [], [payload]);
  const isMonthly = payload?.indicator?.frequency === 'monthly';
  const isAnnual = payload?.indicator?.frequency === 'annual';
  const last = series[series.length - 1];
  const first = series[0];
  const lastLabel = pointLabel(last, isMonthly, locale);
  const rank = payload?.rank;
  const rankPosition = rank?.position ?? (typeof payload?.rank === 'number' ? payload.rank : null);
  const rankTotal = rank?.total ?? payload?.of;

  useDocumentMeta({
    title: `${indName} — ${regionName} | Forecast Economy`,
    description: t('world.regions.seriesDescription', {
      indicator: indName,
      region: regionName,
      country: countryName,
    }),
  });

  const regionOptions = useMemo(() => {
    if (!hub.data?.regions) return [];
    return hub.data.regions
      .filter((r) => r.slug !== slug)
      .sort((a, b) => a.name.localeCompare(b.name, locale === 'en' ? 'en' : 'ru'));
  }, [hub.data, slug, locale]);

  const delta = last && series.length > 1
    ? yearDelta(last.value, series[series.length - 2].value)
    : null;

  const stats = useMemo(() => {
    if (!series.length) return null;
    const values = series.map((p) => p.value);
    const max = Math.max(...values);
    const min = Math.min(...values);
    const at = (idx) => pointLabel(series[idx], isMonthly, locale);
    return {
      max, maxAt: at(values.indexOf(max)),
      min, minAt: at(values.indexOf(min)),
    };
  }, [series, isMonthly, locale]);

  const chartSeries = (!isMonthly && showYoY) ? toYoYSeries(series) : series;
  const chartNational = showNational
    ? ((!isMonthly && showYoY) ? toYoYSeries(nationalSeries) : nationalSeries)
    : null;
  const chartCompare = compareSlug
    ? ((!isMonthly && showYoY) ? toYoYSeries(compare.data?.series || []) : (compare.data?.series || null))
    : null;
  const chartUnit = showYoY && !isMonthly ? t('regions.ind.yoyShort') : (payload?.indicator?.unit || '');

  const tableRows = useMemo(
    () => (series.length ? [...series].reverse() : []),
    [series],
  );
  const quickYears = useMemo(() => {
    const years = [...new Set(series.map((point) => point.year))].sort((a, b) => a - b);
    return years;
  }, [series]);

  const requireAuth = (blockedEvent) => {
    if (isAuthed) return true;
    track(blockedEvent, { indicator: `world-region:${slug}:${code}` });
    window.dispatchEvent(new CustomEvent('fe:download-limit'));
    return false;
  };

  const handleExportTable = async (format) => {
    const evt = format === 'csv' ? events.DOWNLOAD_CSV : events.DOWNLOAD_EXCEL;
    if (!requireAuth(events.DOWNLOAD_LIMIT_HIT) || !series.length || exporting) return;
    setExporting(true);
    try {
      const filename = `${slug}_${code}.${format}`;
      const { blob } = await exportTable({
        format,
        filename,
        valueLabel: `${indName} (${payload.indicator.unit})`,
        points: [
          ...series.map((p) => ({
          date: p.date || (isMonthly
            ? `${p.year}-${String(p.month).padStart(2, '0')}-01`
            : `${p.year}-01-01`),
          actual: p.value,
          forecast: null,
          })),
          ...(forecastQ.data?.available ? forecastQ.data.points.map((p) => ({
            date: p.date, actual: null, forecast: p.value,
          })) : []),
        ],
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 100);
      track(evt, { indicator: `world-region:${slug}:${code}`, region: slug, world: true });
    } catch {
      // Сетевые сбои экспорта не должны ронять страницу.
    } finally {
      setExporting(false);
    }
  };

  const handleExportPng = async () => {
    if (!requireAuth(events.CHART_IMAGE_BLOCKED) || exporting) return;
    setExporting(true);
    const ok = await exportNodeToPng(chartRef.current, {
      filename: `${slug}_${code}.png`,
      watermark: false,
    }).catch(() => false);
    setExporting(false);
    if (ok) track(events.CHART_IMAGE_DOWNLOAD, { indicator: `world-region:${slug}:${code}`, region: slug, world: true });
  };

  const viewTrackedRef = useRef('');
  useEffect(() => {
    if (!payload?.indicator) return;
    const key = `${countrySlug}:${slug}:${code}`;
    if (viewTrackedRef.current === key) return;
    viewTrackedRef.current = key;
    track(events.REGION_INDICATOR_VIEW, {
      indicator: `world-region:${slug}:${code}`,
      region: slug,
      code,
      world: true,
    });
  }, [payload?.indicator, countrySlug, slug, code]);


  if (countrySlug === RUSSIA) {
    return <Navigate to={regionIndicatorPath(slug, code)} replace />;
  }

  const methodologyContent = payload ? {
    description: payload.indicator.description,
    methodology: payload.indicator.methodology,
  } : null;
  const methodologyIndicator = payload ? {
    ...payload.indicator,
    name: indName,
  } : null;

  return (
    <div className="fe-data-page mx-auto w-full max-w-7xl px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs
        items={worldSubnationalIndicatorTrail(
          countryName, countrySlug, kindPlural, regionName, slug, indName, code,
        )}
      />

      {data.isError && !payload && (
        <ApiRetryBanner onRetry={data.refetch} isFetching={data.isFetching}>
          {t('world.regions.loadError')}
        </ApiRetryBanner>
      )}
      {!payload && (
        <div className="space-y-4">
          <SkeletonBox className="h-9 w-96 max-w-full" />
          <SkeletonBox className="h-72 rounded-xl" />
        </div>
      )}

      {payload && (
        <>
          <div className="fe-data-header">
            <div className="mb-2 font-mono text-xs uppercase tracking-widest text-champagne">
              {payload.indicator.section}
            </div>
            <div className="mb-5 flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
              <h1 className="min-w-0 flex-1 font-display text-[1.35rem] font-bold leading-tight text-text-primary sm:text-3xl">
                {indName}
              </h1>
              <span className="shrink-0 pt-0.5 text-sm text-text-secondary sm:pt-1.5">{regionName}</span>
            </div>

            <div className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="font-mono text-2xl font-bold text-text-primary sm:text-3xl">
                {formatSubnationalValue(last?.value, locale)}
              </span>
              <span className="text-sm text-text-secondary">{payload.indicator.unit}</span>
              <span className="font-mono text-sm text-text-tertiary">{lastLabel}</span>
              {delta && (
                <span className={`font-mono text-sm ${delta.up ? 'text-positive' : delta.down ? 'text-negative' : 'text-text-tertiary'}`}>
                  {t(isMonthly ? 'regions.ind.deltaMoM' : 'regions.ind.deltaYoY', {
                    pct: `${delta.up ? '+' : ''}${delta.pct.toFixed(1).replace('.', locale === 'en' ? '.' : ',')}`,
                  })}
                </span>
              )}
            </div>
          </div>

          <div id="chart" data-block="world-region-chart" className="fe-panel mb-4 scroll-mt-24 rounded-xl border border-border-subtle bg-surface p-3 sm:p-4" ref={chartRef}>
            <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
              <div className="font-mono text-xs text-text-tertiary">
                {first && last
                  ? (isMonthly
                    ? `${first.year}–${last.year}, ${payload.indicator.unit}`
                    : `${first.year}–${last.year}, ${showYoY ? t('regions.ind.yoyUnit') : payload.indicator.unit}`)
                  : payload.indicator.unit}
              </div>
              <div className="flex flex-wrap items-center gap-1.5" data-no-export="true">
                <label
                  className={`inline-flex max-w-full min-w-0 items-center gap-1.5 rounded-full border px-2.5 py-1 transition-colors ${
                    compareSlug
                      ? 'border-[#5B7DA8] text-[#5B7DA8]'
                      : 'border-border-subtle text-text-tertiary hover:text-text-secondary'
                  }`}
                >
                  <GitCompare size={12} className="shrink-0 opacity-70" aria-hidden />
                  <select
                    value={compareSlug}
                    onChange={(e) => {
                      setCompareSlug(e.target.value);
                      if (e.target.value) {
                        track(events.REGION_COMPARE_ADD, {
                          region: slug, compare: e.target.value, indicator: code, world: true,
                        });
                      }
                    }}
                    aria-label={t('world.regions.compareOther')}
                    className="min-w-0 flex-1 cursor-pointer appearance-auto border-0 bg-transparent p-0 pr-0.5 text-xs text-inherit focus:outline-none"
                  >
                    <option value="">{t('world.regions.comparePlaceholder')}</option>
                    {regionOptions.map((r) => (
                      <option key={r.slug} value={r.slug}>{r.name}</option>
                    ))}
                  </select>
                </label>
                {nationalSeries.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setShowNational((v) => !v)}
                    className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                      showNational
                        ? 'border-border-champagne bg-champagne/5 text-champagne'
                        : 'border-border-subtle text-text-tertiary hover:text-text-secondary'
                    }`}
                  >
                    {showNational
                      ? t('world.regions.vsCountry', { country: countryName })
                      : t('world.regions.addCountry', { country: countryName })}
                  </button>
                )}
                {isAnnual && series.length > 2 && !isNegativeCapable(series) && (
                  <button
                    type="button"
                    onClick={() => setShowYoY((v) => !v)}
                    title={t('regions.ind.yoyTitle')}
                    className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                      showYoY
                        ? 'border-border-champagne bg-champagne/5 text-champagne'
                        : 'border-border-subtle text-text-tertiary hover:text-text-secondary'
                    }`}
                  >
                    {t('regions.ind.yoyBtn')}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => handleExportTable('csv')}
                  disabled={exporting}
                  title={t('regions.ind.downloadCsv')}
                  aria-label={t('regions.ind.downloadCsv')}
                  className="inline-flex items-center gap-1 rounded-full border border-border-subtle px-2 py-1 text-xs text-text-tertiary transition-colors hover:border-border-champagne hover:text-champagne disabled:opacity-50"
                >
                  <Download size={12} /> CSV
                </button>
                <button
                  type="button"
                  onClick={() => handleExportTable('xlsx')}
                  disabled={exporting}
                  title={t('regions.ind.downloadExcel')}
                  aria-label={t('regions.ind.downloadExcel')}
                  className="inline-flex items-center gap-1 rounded-full border border-border-subtle px-2 py-1 text-xs text-text-tertiary transition-colors hover:border-border-champagne hover:text-champagne disabled:opacity-50"
                >
                  <Download size={12} /> Excel
                </button>
                <button
                  type="button"
                  onClick={handleExportPng}
                  disabled={exporting}
                  title={t('regions.ind.downloadPng')}
                  aria-label={t('regions.ind.downloadPng')}
                  className="inline-flex items-center gap-1 rounded-full border border-border-subtle px-2 py-1 text-xs text-text-tertiary transition-colors hover:border-border-champagne hover:text-champagne disabled:opacity-50"
                >
                  <ImageIcon size={12} /> PNG
                </button>
              </div>
            </div>
            <RegionAnnualChart
              frequency={payload.indicator.frequency}
              series={chartSeries}
              russiaSeries={chartNational}
              compareSeries={chartCompare}
              compareName={compareSlug ? (compare.data?.region?.name || '') : ''}
              unit={chartUnit}
              regionName={regionName}
              height={300}
              nationalLabel={t('world.regions.vsCountry', { country: countryName })}
              forecastSeries={!showYoY && forecastQ.data?.available ? forecastQ.data.points : null}
            />
            {forecastQ.data?.available && !showYoY && (
              <div className="mt-2 rounded-lg border border-border-subtle bg-champagne/5 px-3 py-2 text-[11px] leading-relaxed text-text-secondary">
                <strong className="text-champagne">{locale === 'en' ? 'Our forecast' : 'Наш прогноз'}</strong>
                {' — '}{forecastQ.data.model_name}
                {' — '}MASE {Number(forecastQ.data.quality.mase).toFixed(2)}
                <p className="mt-1">{forecastQ.data.methodology}</p>
              </div>
            )}
            {compareSlug && compare.data && (
              <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 px-1 text-[11px] text-text-tertiary" data-no-export="true">
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block h-0.5 w-4 rounded bg-champagne" />
                  {regionName}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block h-0.5 w-4 rounded" style={{ backgroundColor: '#5B7DA8' }} />
                  {compare.data.region.name}
                </span>
                <button type="button" onClick={() => setCompareSlug('')} className="text-text-tertiary underline hover:text-text-secondary">
                  {t('regions.ind.removeCompare')}
                </button>
              </div>
            )}
          </div>

          <div className="mb-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {rankPosition != null && (
              <StatCell label={
                t(
                  rank?.rank_as_achievement
                    ? 'world.regions.rankAchieve'
                    : 'world.regions.rankNeutral',
                  { year: rank?.year || last?.year, kind: countrySlug === 'united-states' && locale === 'ru' ? 'штатов' : kindPlural },
                )
              }
              >
                <span className="inline-flex items-center gap-1.5">
                  {rank?.rank_as_achievement && (
                    <Trophy size={14} className="text-champagne" />
                  )}
                  {rankPosition}
                  {' '}
                  {t('regions.ind.of')}
                  {' '}
                  {rankTotal}
                </span>
              </StatCell>
            )}
            {stats && (
              <>
                <StatCell label={t('regions.ind.max', { year: stats.maxAt })}>
                  {formatSubnationalValue(stats.max, locale)}
                </StatCell>
                <StatCell label={t('regions.ind.min', { year: stats.minAt })}>
                  {formatSubnationalValue(stats.min, locale)}
                </StatCell>
              </>
            )}
            {first && last && (
              <StatCell label={t('regions.ind.period')}>
                {first.year}–{last.year}
              </StatCell>
            )}
          </div>

          {quickYears.length > 0 && (
            <section className="fe-panel mb-6 rounded-xl border border-border-subtle bg-surface p-4">
              <h2 className="mb-2 text-sm font-semibold text-text-primary">{locale === 'en' ? 'By year' : 'По годам'}</h2>
              <div className="flex flex-wrap gap-2">
                {quickYears.map((year) => (
                  <a key={year} href={countryRegionIndicatorYearPath(countrySlug, slug, code, year)} className="rounded-full border border-border-subtle px-3 py-1 text-xs text-text-secondary hover:border-border-champagne hover:text-champagne">{year}</a>
                ))}
              </div>
              {payload.indicator.national_code && last && nationalSeries.some((point) => point.year === last.year) && (
                <a href={indicatorYearPath(countrySlug, payload.indicator.national_code, last.year)} className="mt-3 inline-block text-xs text-champagne hover:underline">
                  {locale === 'en' ? `United States, ${last.year}` : `США в целом, ${last.year}`}
                </a>
              )}
            </section>
          )}

          {rank?.top?.length > 0 && (
            <div data-block="world-region-rating" className="fe-panel mb-6 rounded-xl border border-border-subtle bg-surface p-4">
              <h2 className="mb-3 text-sm font-semibold text-text-primary">
                {t(
                  rank.rank_as_achievement ? 'world.regions.topAchieve' : 'world.regions.topNeutral',
                  { year: rank.year },
                )}
              </h2>
              <ol className="space-y-1.5">
                {rank.top.map((r, i) => (
                  <li key={r.slug}>
                    <Link
                      to={countryRegionIndicatorPath(countrySlug, r.slug, code)}
                      className={`-mx-2 flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-[13px] transition-colors hover:bg-surface-hover ${r.slug === slug ? 'bg-champagne/5' : ''}`}
                    >
                      <span className="flex min-w-0 items-center gap-2">
                        <span className="w-4 shrink-0 text-right font-mono text-text-tertiary">{i + 1}</span>
                        <span className={`truncate ${r.slug === slug ? 'font-medium text-champagne' : 'text-text-primary'}`}>{r.name}</span>
                      </span>
                      <span className="shrink-0 font-mono text-text-secondary">{formatSubnationalValue(r.value, locale)}</span>
                    </Link>
                  </li>
                ))}
              </ol>
              {rankPosition > 5 && (
                <div className="mt-2 flex items-center justify-between border-t border-border-subtle px-2 pt-2 text-[13px]">
                  <span className="flex items-center gap-2">
                    <span className="w-4 text-right font-mono text-text-tertiary">{rankPosition}</span>
                    <span className="font-medium text-champagne">{regionName}</span>
                  </span>
                  <span className="font-mono text-text-secondary">{formatSubnationalValue(last?.value, locale)}</span>
                </div>
              )}
            </div>
          )}

          <div className="fe-panel mb-6 overflow-hidden rounded-xl border border-border-subtle bg-surface">
            <button
              type="button"
              onClick={() => setShowTable((v) => !v)}
              className="flex w-full items-center justify-between px-4 py-3.5 transition-colors hover:bg-surface-hover"
              aria-expanded={showTable}
            >
              <span className="flex items-center gap-2 text-sm font-medium text-text-primary">
                <Table2 size={15} className="text-text-tertiary" />
                {t('regions.ind.tableToggle')}
              </span>
              <ChevronDown size={16} className={`text-text-tertiary transition-transform ${showTable ? 'rotate-180' : ''}`} />
            </button>
            {showTable && (
              <div className="max-h-96 overflow-auto border-t border-border-subtle">
                <table className="w-full min-w-[18rem] text-[13px]">
                  <thead className="sticky top-0 bg-surface">
                    <tr className="text-left text-text-tertiary">
                      <th className="px-3 py-2 font-medium sm:px-4">
                        {isMonthly ? t('regions.ind.colMonth') : t('regions.ind.colYear')}
                      </th>
                      <th className="px-3 py-2 text-right font-medium sm:px-4">{regionName}</th>
                      {nationalSeries.length > 0 && (
                        <th className="px-3 py-2 text-right font-medium sm:px-4">{countryName}</th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {tableRows.map((p) => {
                      const rf = nationalSeries.find((r) => (
                        isMonthly ? r.label === p.label : r.year === p.year
                      ));
                      return (
                        <tr key={p.date || p.label} className="border-t border-border-subtle">
                          <td className="px-3 py-1.5 font-mono text-text-secondary sm:px-4">
                            {pointLabel(p, isMonthly, locale)}
                          </td>
                          <td className="px-3 py-1.5 text-right font-mono text-text-primary sm:px-4">
                            {formatSubnationalValue(p.value, locale)}
                          </td>
                          {nationalSeries.length > 0 && (
                            <td className="px-3 py-1.5 text-right font-mono text-text-tertiary sm:px-4">
                              {rf ? formatSubnationalValue(rf.value, locale) : '—'}
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {(methodologyContent?.description || methodologyContent?.methodology) && (
            <div className="mb-6">
              <IndicatorMethodologyPanel
                indicator={methodologyIndicator}
                content={methodologyContent}
                sourcePath={payload.indicator.source_url || countryRegionIndicatorPath(countrySlug, slug, code)}
              />
            </div>
          )}

          {payload.indicator.national_code && (
            <div className="fe-panel mb-6 rounded-xl border border-border-champagne/40 bg-surface p-4">
              <h2 className="mb-2 text-sm font-semibold text-text-primary">
                {t('world.regions.nationalTitle')}
              </h2>
              <p className="mb-3 text-[13px] leading-relaxed text-text-secondary">
                {t('world.regions.nationalBody')}
              </p>
              <div className="flex flex-wrap gap-2">
                <Link
                  to={indicatorPath(countrySlug, payload.indicator.national_code)}
                  className="inline-flex items-center gap-1 rounded-full bg-champagne/10 px-3 py-1.5 text-[13px] font-medium text-champagne transition-colors hover:bg-champagne/20"
                >
                  {t('world.regions.openNational')} <ArrowUpRight size={13} />
                </Link>
                <Link
                  to={`/compare?codes=w:${countrySlug}:${payload.indicator.national_code},s:${countrySlug}:${slug}:${code}`}
                  className="inline-flex items-center gap-1 rounded-full border border-border-subtle px-3 py-1.5 text-[13px] font-medium text-text-secondary transition-colors hover:border-border-champagne hover:text-champagne"
                >
                  <GitCompare size={13} /> {t('world.regions.compareNational', { country: countryName })}
                </Link>
              </div>
            </div>
          )}

          {payload.siblings?.length > 0 && (
            <div className="mb-6">
              <h2 className="mb-3 text-sm font-semibold text-text-primary">
                {t('regions.ind.moreInSection', { section: payload.indicator.section })}
              </h2>
              <div className="flex flex-wrap gap-2">
                {payload.siblings.map((s) => (
                  <Link
                    key={s.code}
                    to={countryRegionIndicatorPath(countrySlug, slug, s.code)}
                    className="inline-flex items-center gap-1 rounded-full border border-border-subtle bg-surface px-3 py-1.5 text-[13px] text-text-secondary transition-colors hover:border-border-champagne hover:text-champagne"
                  >
                    {s.name.length > 60 ? `${s.name.slice(0, 57)}…` : s.name}
                    <ArrowUpRight size={12} />
                  </Link>
                ))}
              </div>
            </div>
          )}

          <p className="mt-8 flex flex-wrap gap-4 text-sm">
            <Link to={countryRegionPath(countrySlug, slug)} className="text-champagne hover:underline">
              {t('world.regions.backToProfile', { region: regionName })}
            </Link>
            <Link to={countryRegionsPath(countrySlug)} className="text-text-secondary hover:text-champagne">
              {countrySlug === 'united-states' && locale === 'ru'
                ? 'Все штаты'
                : t('world.regions.backToHub', { kind: kindPlural })}
            </Link>
          </p>
        </>
      )}
    </div>
  );
}
