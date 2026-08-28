// Детальная страница показателя региона: /russia/region/{slug}/{code}
// График + рейтинг среди регионов + сравнение с РФ + таблица значений +
// выгрузка CSV/Excel/PNG (только для зарегистрированных, PNG — без watermark,
// см. правило 2026-07-08 в IndicatorChartSection.jsx).
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams, useLocation } from 'react-router-dom';
import {
  Trophy, Table2, ChevronDown, ArrowUpRight,
  Download, Image as ImageIcon, GitCompare,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { getSiteOrigin } from '../lib/siteOrigin';
import {
  useRegionIndicator, useRegionIndicatorMonthly, useRegionsLanding,
  formatRegionValue, shortUnit, yearDelta,
} from '../lib/regionsApi';
import RegionAnnualChart from '../components/RegionAnnualChart';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import { useAuth } from '../context/authContext';
import { exportTable } from '../lib/api';
import { exportNodeToPng } from '../lib/chartImage';
import { track, events } from '../lib/track';
import { regionIndicatorTrail } from '../lib/breadcrumbs';
import {
  regionIndicatorPath,
  russiaIndicatorPath,
} from '../lib/sitePaths';
import { useLocale } from '../i18n';

// Годовой ряд → изменения год к году, % (кнопка YoY / «% г/г»).
function toYoYSeries(series) {
  if (!series?.length) return [];
  const byYear = new Map(series.map(p => [p.year, p.value]));
  return series
    .filter(p => {
      const prev = byYear.get(p.year - 1);
      return prev != null && prev !== 0;
    })
    .map(p => {
      const prev = byYear.get(p.year - 1);
      return { year: p.year, value: +(((p.value - prev) / Math.abs(prev)) * 100).toFixed(2) };
    });
}

// В-20 (CTO-аудит 2026-07-06): для знакопеременных рядов (сальдо миграции
// и т.п.) «% г/г» от базы, переходящей через ноль, — нечитаемый процент
// (тысячи % и перевороты знака). Тоггл для таких рядов не показываем.
function isNegativeCapable(series) {
  return Array.isArray(series) && series.some(p => p?.value != null && p.value < 0);
}

function StatCell({ label, children }) {
  return (
    <div className="bg-surface border border-border-subtle rounded-xl p-3 sm:p-3.5 min-w-0">
      <div className="text-[10px] sm:text-[11px] text-text-tertiary uppercase tracking-wide truncate">{label}</div>
      <div className="mt-1 font-mono font-semibold text-text-primary text-sm sm:text-[15px] leading-tight break-words">
        {children}
      </div>
    </div>
  );
}

const MONTH_NAMES_RU = [
  'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
  'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь',
];

const ABORTION_SIBLING = {  'beremennosti-s-abortivnym-ishodom-na-100-rodov': {
    code: 'beremennosti-s-abortivnym-ishodom-na-1000-zhenschin',
    labelKey: 'regions.ind.abortionPer1000',
  },
  'beremennosti-s-abortivnym-ishodom-na-1000-zhenschin': {
    code: 'beremennosti-s-abortivnym-ishodom-na-100-rodov',
    labelKey: 'regions.ind.abortionPer100',
  },
};

export default function RegionIndicatorPage() {
  const { t, locale } = useLocale();
  const { slug, code } = useParams();
  // Месячный ряд тянется только для показателей, у которых он есть: годовой
  // запрос отдаёт 404 «Нет месячных данных» — по нему и выключаем повторные попытки.
  const monthly = useRegionIndicatorMonthly(slug, code);
  const isMonthly = monthly.data?.frequency === 'monthly' && monthly.data?.series?.length > 0;
  const { data, isLoading, isError, refetch, isFetching } = useRegionIndicator(slug, code);
  const [showTable, setShowTable] = useState(false);
  const [showRussia, setShowRussia] = useState(true);
  const [showYoYRaw, setShowYoY] = useState(false);
  // В-20: для знакопеременных рядов режим «% г/г» недоступен.
  const showYoY = showYoYRaw && !isNegativeCapable(data?.series);
  const [exporting, setExporting] = useState(false);
  const { isAuthed } = useAuth();
  const chartRef = useRef(null);
  // SSR-карточка-график ведёт на /russia/region/{slug}/{code}#chart: плавный
  // скролл после загрузки данных, по эталону IndicatorChartSection.
  const { hash } = useLocation();
  useEffect(() => {
    if (hash !== '#chart' || isLoading) return;
    document.getElementById('chart')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [hash, isLoading]);

  // Сравнение с другим регионом: вторая линия на графике.
  const [compareSlug, setCompareSlug] = useState('');
  const landing = useRegionsLanding();
  const compare = useRegionIndicator(compareSlug || null, compareSlug ? code : null);
  const compareMonthly = useRegionIndicatorMonthly(
    compareSlug || null, compareSlug ? code : null, !!compareSlug && isMonthly,
  );
  const regionOptions = useMemo(() => {
    if (!landing.data) return [];
    return landing.data.districts.flatMap(d => d.regions.map(r => ({ slug: r.slug, name: r.name })))
      .filter(r => r.slug !== slug)
      .sort((a, b) => a.name.localeCompare(b.name, locale === 'en' ? 'en' : 'ru'));
  }, [landing.data, slug, locale]);

  // Выгрузка данных региона — только для зарегистрированных: гостю показываем
  // гейт регистрации (то же окно, что в макроблоке). PNG — без watermark.
  const requireAuth = (blockedEvent) => {
    if (isAuthed) return true;
    track(blockedEvent, { indicator: `region:${slug}:${code}` });
    window.dispatchEvent(new CustomEvent('fe:download-limit'));
    return false;
  };

  const handleExportTable = async (format) => {
    const evt = format === 'csv' ? events.DOWNLOAD_CSV : events.DOWNLOAD_EXCEL;
    if (!requireAuth(events.DOWNLOAD_LIMIT_HIT) || !activeSeries.length || exporting) return;
    setExporting(true);
    try {
      const filename = `${slug}_${code}.${format}`;
      const { blob } = await exportTable({
        format,
        filename,
        valueLabel: `${active.indicator.name} (${active.indicator.unit})`,
        points: activeSeries.map(p => ({
          date: isMonthly ? `${p.year}-${String(p.month).padStart(2, '0')}-01` : `${p.year}-01-01`,
          actual: p.value,
          forecast: null,
        })),
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 100);
      track(evt, { indicator: `region:${slug}:${code}`, region: slug });
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
    if (ok) track(events.CHART_IMAGE_DOWNLOAD, { indicator: `region:${slug}:${code}`, region: slug });
  };

  // Активный ряд: месячный, если по показателю он пришёл; иначе годовой.
  // Годовой запрос для месячных показателей отдаёт 404 — ждать его нельзя,
  // карточка рендерится от активного ряда. Все производные — только ниже.
  const active = isMonthly ? monthly.data : data;
  const activeSeries = active?.series || [];
  const regionName = active?.region?.name;
  const indName = active?.indicator?.name;
  const last = activeSeries[activeSeries.length - 1];
  const first = activeSeries[0];
  const lastLabel = last
    ? (isMonthly ? `${MONTH_NAMES_RU[last.month - 1]} ${last.year}` : String(last.year))
    : '';

  // Карточка рендерится от активного ряда (месячного или годового).
  const cardReady = isMonthly ? !!active : !!data;
  const viewTrackedRef = useRef('');
  useEffect(() => {
    if (!active?.indicator) return;
    const key = `${slug}:${code}`;
    if (viewTrackedRef.current === key) return;
    viewTrackedRef.current = key;
    track(events.REGION_INDICATOR_VIEW, {
      indicator: `region:${slug}:${code}`,
      region: slug,
      code,
    });
  }, [active?.indicator, slug, code]);

  useDocumentMeta(active ? {
    title: t(isMonthly ? 'regions.ind.metaTitleMonthly' : 'regions.ind.metaTitle', {
      name: indName,
      region: regionName,
      value: formatRegionValue(last.value),
      unit: shortUnit(active.indicator.unit),
      year: isMonthly ? lastLabel : last.year,
    }),
    description: t(isMonthly ? 'regions.ind.metaDescMonthly' : 'regions.ind.metaDesc', {
      name: indName,
      region: regionName,
      value: formatRegionValue(last.value),
      unit: active.indicator.unit,
      year: isMonthly ? lastLabel : last.year,
      from: first.year,
      rank: active.rank
        ? t(
          active.rank.rank_as_achievement
            ? 'regions.ind.metaRankAchieve'
            : 'regions.ind.metaRankNeutral',
          { position: active.rank.position, total: active.rank.total },
        )
        : '.',
    }),
    path: regionIndicatorPath(slug, code),
  } : null);

  useEffect(() => {
    if (!active) return;
    const jsonLd = {
      '@context': 'https://schema.org',
      '@type': 'Dataset',
      name: `${indName} — ${regionName}`,
      description: t('regions.ind.jsonLdDesc', {
        name: indName,
        unit: active.indicator.unit,
        region: regionName,
        from: first.year,
        to: last.year,
      }),
      temporalCoverage: `${first.year}/${last.year}`,
      spatialCoverage: regionName,
      creator: { '@type': 'Organization', name: t('regions.ind.creatorRosstat') },
      publisher: { '@type': 'Organization', name: 'Forecast Economy', url: getSiteOrigin() },
    };
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.id = 'region-dataset-jsonld';
    script.textContent = JSON.stringify(jsonLd);
    document.getElementById('region-dataset-jsonld')?.remove();
    document.head.appendChild(script);
    return () => script.remove();
  }, [active, indName, regionName, first, last, t]);

  const delta = last && activeSeries.length > 1
    ? yearDelta(last.value, activeSeries[activeSeries.length - 2].value)
    : null;

  const stats = useMemo(() => {
    if (!activeSeries.length) return null;
    const values = activeSeries.map(p => p.value);
    const max = Math.max(...values);
    const min = Math.min(...values);
    const at = (idx) => {
      const p = activeSeries[idx];
      return isMonthly ? MONTH_NAMES_RU[p.month - 1] + ' ' + p.year : p.year;
    };
    return {
      max, maxAt: at(values.indexOf(max)),
      min, minAt: at(values.indexOf(min)),
    };
  }, [activeSeries, isMonthly]);

  const tableRows = useMemo(
    () => (activeSeries.length ? [...activeSeries].reverse() : []),
    [activeSeries],
  );

  const abortion = ABORTION_SIBLING[code];

  return (
    <div className="mx-auto w-full max-w-7xl px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs
        items={regionIndicatorTrail(
          regionName || '…',
          slug,
          indName || '…',
          code,
        )}
      />

      {isError && !cardReady && <ApiRetryBanner onRetry={refetch} retrying={isFetching} />}
      {!cardReady && (
        <div className="space-y-4">
          <SkeletonBox className="h-9 w-96 max-w-full" />
          <SkeletonBox className="h-72 rounded-xl" />
        </div>
      )}

      {cardReady && active && (
        <>
          <div className="mb-5">
            <div className="text-champagne text-xs font-mono uppercase tracking-widest mb-2">
              {active.indicator.section_name}
            </div>
            <div className="mb-5 flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
              <h1 className="min-w-0 flex-1 font-display text-[1.35rem] font-bold leading-tight text-text-primary sm:text-3xl">
                {indName}
              </h1>
              <span className="shrink-0 pt-0.5 text-sm text-text-secondary sm:pt-1.5">{regionName}</span>
            </div>
            {abortion && (
              <p className="mt-1 text-xs text-text-tertiary">
                {t('regions.ind.abortionLead')}
                {' '}
                <Link
                  to={regionIndicatorPath(slug, abortion.code)}
                  className="text-champagne hover:underline"
                >
                  {t(abortion.labelKey)}
                </Link>
                .
              </p>
            )}

            <div className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="font-mono text-2xl font-bold text-text-primary sm:text-3xl">
                {formatRegionValue(last.value)}
              </span>
              <span className="text-sm text-text-secondary">{active.indicator.unit}</span>
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

          <div id="chart" data-block="region-chart" className="bg-surface border border-border-subtle rounded-xl p-3 sm:p-4 mb-4 scroll-mt-24" ref={chartRef}>
            <div className="flex flex-col gap-2 mb-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
              <div className="text-xs text-text-tertiary font-mono">
                {isMonthly
                  ? `${first.year}–${last.year}, помесячно — ${active.indicator.unit}`
                  : `${first.year}–${last.year}, ${showYoY ? t('regions.ind.yoyUnit') : active.indicator.unit}`}
              </div>
              <div className="flex flex-wrap items-center gap-1.5" data-no-export="true">
                <label
                  className={`inline-flex items-center gap-1.5 min-w-0 max-w-full rounded-full border px-2.5 py-1 transition-colors ${
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
                      if (e.target.value) track(events.REGION_COMPARE_ADD, { region: slug, compare: e.target.value, indicator: code });
                    }}
                    aria-label={t('regions.ind.compareOther')}
                    className="min-w-0 flex-1 bg-transparent text-xs text-inherit border-0 p-0 pr-0.5 cursor-pointer focus:outline-none appearance-auto"
                  >
                    <option value="">{t('regions.ind.comparePlaceholder')}</option>
                    {regionOptions.map(r => (
                      <option key={r.slug} value={r.slug}>{r.name}</option>
                    ))}
                  </select>
                </label>
                {active.russia_series?.length > 0 && (
                  <button
                    onClick={() => setShowRussia(v => !v)}
                    className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                      showRussia
                        ? 'border-border-champagne text-champagne bg-champagne/5'
                        : 'border-border-subtle text-text-tertiary hover:text-text-secondary'
                    }`}
                  >
                    {showRussia ? t('regions.ind.vsRussia') : t('regions.ind.addRussia')}
                  </button>
                )}
                {!isMonthly && data.series.length > 2 && !isNegativeCapable(data.series) && (
                  <button
                    onClick={() => setShowYoY(v => !v)}
                    title={t('regions.ind.yoyTitle')}
                    className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                      showYoY
                        ? 'border-border-champagne text-champagne bg-champagne/5'
                        : 'border-border-subtle text-text-tertiary hover:text-text-secondary'
                    }`}
                  >
                    {t('regions.ind.yoyBtn')}
                  </button>
                )}
                <button
                  onClick={() => handleExportTable('csv')}
                  disabled={exporting}
                  title={t('regions.ind.downloadCsv')}
                  aria-label={t('regions.ind.downloadCsv')}
                  className="text-xs px-2 py-1 rounded-full border border-border-subtle text-text-tertiary hover:text-champagne hover:border-border-champagne transition-colors inline-flex items-center gap-1 disabled:opacity-50"
                >
                  <Download size={12} /> CSV
                </button>
                <button
                  onClick={() => handleExportTable('xlsx')}
                  disabled={exporting}
                  title={t('regions.ind.downloadExcel')}
                  aria-label={t('regions.ind.downloadExcel')}
                  className="text-xs px-2 py-1 rounded-full border border-border-subtle text-text-tertiary hover:text-champagne hover:border-border-champagne transition-colors inline-flex items-center gap-1 disabled:opacity-50"
                >
                  <Download size={12} /> Excel
                </button>
                <button
                  onClick={handleExportPng}
                  disabled={exporting}
                  title={t('regions.ind.downloadPng')}
                  aria-label={t('regions.ind.downloadPng')}
                  className="text-xs px-2 py-1 rounded-full border border-border-subtle text-text-tertiary hover:text-champagne hover:border-border-champagne transition-colors inline-flex items-center gap-1 disabled:opacity-50"
                >
                  <ImageIcon size={12} /> PNG
                </button>
              </div>
            </div>
            <RegionAnnualChart
              frequency={isMonthly ? 'monthly' : 'annual'}
              series={isMonthly ? activeSeries : (showYoY ? toYoYSeries(data.series) : data.series)}
              russiaSeries={showRussia
                ? (isMonthly
                  ? active.russia_series
                  : (showYoY ? toYoYSeries(data.russia_series) : data.russia_series))
                : null}
              compareSeries={compareSlug
                ? (isMonthly
                  ? (compareMonthly.data?.series || null)
                  : (showYoY ? toYoYSeries(compare.data?.series) : (compare.data?.series || null)))
                : null}
              compareName={compareSlug ? (compare.data?.region?.name || '') : ''}
              unit={showYoY ? t('regions.ind.yoyShort') : active.indicator.unit}
              regionName={regionName}
              height={300}
            />
            {compareSlug && isMonthly && compareMonthly.data && (
              <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-text-tertiary px-1" data-no-export="true">
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block w-4 h-0.5 rounded bg-champagne" />
                  {regionName}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block w-4 h-0.5 rounded" style={{ backgroundColor: '#5B7DA8' }} />
                  {compareMonthly.data.region.name}
                </span>
                <button onClick={() => setCompareSlug('')} className="text-text-tertiary underline hover:text-text-secondary">
                  {t('regions.ind.removeCompare')}
                </button>
              </div>
            )}
            {compareSlug && !isMonthly && compare.data && (
              <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-text-tertiary px-1" data-no-export="true">
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block w-4 h-0.5 rounded bg-champagne" />
                  {regionName}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block w-4 h-0.5 rounded" style={{ backgroundColor: '#5B7DA8' }} />
                  {compare.data.region.name}
                </span>
                <button onClick={() => setCompareSlug('')} className="text-text-tertiary underline hover:text-text-secondary">
                  {t('regions.ind.removeCompare')}
                </button>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-6">
            {active.rank?.position && (
              <StatCell label={
                t(
                  active.rank.rank_as_achievement
                    ? 'regions.ind.rankAchieve'
                    : 'regions.ind.rankNeutral',
                  { year: active.rank.year },
                )
              }
              >
                <span className="inline-flex items-center gap-1.5">
                  {active.rank.rank_as_achievement && (
                    <Trophy size={14} className="text-champagne" />
                  )}
                  {active.rank.position}
                  {' '}
                  {t('regions.ind.of')}
                  {' '}
                  {active.rank.total}
                </span>
              </StatCell>
            )}
            {stats && (
              <>
                <StatCell label={t('regions.ind.max', { year: stats.maxAt })}>
                  {formatRegionValue(stats.max)}
                </StatCell>
                <StatCell label={t('regions.ind.min', { year: stats.minAt })}>
                  {formatRegionValue(stats.min)}
                </StatCell>
              </>
            )}
            <StatCell label={t('regions.ind.period')}>
              {first.year}–{last.year}
            </StatCell>
          </div>

          {active.rank?.top?.length > 0 && (
            <div data-block="region-rating" className="bg-surface border border-border-subtle rounded-xl p-4 mb-6">
              <h2 className="text-sm font-semibold text-text-primary mb-3">
                {t(
                  active.rank.rank_as_achievement
                    ? 'regions.ind.topAchieve'
                    : 'regions.ind.topNeutral',
                  { year: active.rank.year },
                )}
              </h2>
              <ol className="space-y-1.5">
                {active.rank.top.map((r, i) => (
                  <li key={r.slug}>
                    <Link
                      to={regionIndicatorPath(r.slug, code)}
                      className={`flex items-center justify-between gap-2 text-[13px] rounded-lg px-2 py-1.5 -mx-2 hover:bg-surface-hover transition-colors ${r.slug === slug ? 'bg-champagne/5' : ''}`}
                    >
                      <span className="flex items-center gap-2 min-w-0">
                        <span className="font-mono text-text-tertiary w-4 text-right shrink-0">{i + 1}</span>
                        <span className={`truncate ${r.slug === slug ? 'text-champagne font-medium' : 'text-text-primary'}`}>{r.name}</span>
                      </span>
                      <span className="font-mono text-text-secondary shrink-0">{formatRegionValue(r.value)}</span>
                    </Link>
                  </li>
                ))}
              </ol>
              {active.rank.position > 5 && (
                <div className="mt-2 pt-2 border-t border-border-subtle flex items-center justify-between text-[13px] px-2">
                  <span className="flex items-center gap-2">
                    <span className="font-mono text-text-tertiary w-4 text-right">{active.rank.position}</span>
                    <span className="text-champagne font-medium">{regionName}</span>
                  </span>
                  <span className="font-mono text-text-secondary">{formatRegionValue(last.value)}</span>
                </div>
              )}
            </div>
          )}

          <div className="bg-surface border border-border-subtle rounded-xl overflow-hidden mb-6">
            <button
              onClick={() => setShowTable(v => !v)}
              className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-surface-hover transition-colors"
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
                      {active.russia_series?.length > 0 && (
                        <th className="px-3 py-2 text-right font-medium sm:px-4">{t('regions.ind.russia')}</th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {tableRows.map(p => {
                      const pKey = isMonthly ? p.label : p.year;
                      const rf = active.russia_series?.find(r => (isMonthly ? r.label === p.label : r.year === p.year));
                      return (
                        <tr key={pKey} className="border-t border-border-subtle">
                          <td className="px-3 py-1.5 font-mono text-text-secondary sm:px-4">
                            {isMonthly ? `${MONTH_NAMES_RU[p.month - 1]} ${p.year}` : p.year}
                          </td>
                          <td className="px-3 py-1.5 text-right font-mono text-text-primary sm:px-4">{formatRegionValue(p.value)}</td>
                          {active.russia_series?.length > 0 && (
                            <td className="px-3 py-1.5 text-right font-mono text-text-tertiary sm:px-4">
                              {rf ? formatRegionValue(rf.value) : '—'}
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

          {active.indicator.macro_code && (
            <div className="bg-surface border border-border-champagne/40 rounded-xl p-4 mb-6">
              <h2 className="text-sm font-semibold text-text-primary mb-2">
                {t('regions.ind.macroTitle')}
              </h2>
              <p className="text-[13px] text-text-secondary leading-relaxed mb-3">
                {t('regions.ind.macroBody')}
              </p>
              <div className="flex flex-wrap gap-2">
                <Link
                  to={russiaIndicatorPath(active.indicator.macro_code)}
                  onClick={() => track(events.REGION_CROSSLINK_CLICK, { from: `region:${slug}:${code}`, to: active.indicator.macro_code })}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-champagne/10 text-champagne text-[13px] font-medium hover:bg-champagne/20 transition-colors"
                >
                  {t('regions.ind.openRussia')} <ArrowUpRight size={13} />
                </Link>
                <Link
                  to={`/compare?codes=${active.indicator.macro_code},r:${slug}:${code}`}
                  onClick={() => track(events.REGION_CROSSLINK_CLICK, { from: `region:${slug}:${code}`, to: 'compare' })}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-border-subtle text-text-secondary text-[13px] font-medium hover:text-champagne hover:border-border-champagne transition-colors"
                >
                  <GitCompare size={13} /> {t('regions.ind.compareRussia')}
                </Link>
              </div>
            </div>
          )}

          {active.siblings?.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-text-primary mb-3">
                {t('regions.ind.moreInSection', { section: active.indicator.section_name })}
              </h2>
              <div className="flex flex-wrap gap-2">
                {active.siblings.map(s => (
                  <Link
                    key={s.code}
                    to={regionIndicatorPath(slug, s.code)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-surface border border-border-subtle text-[13px] text-text-secondary hover:text-champagne hover:border-border-champagne transition-colors"
                  >
                    {s.name.length > 60 ? `${s.name.slice(0, 57)}…` : s.name}
                    <ArrowUpRight size={12} />
                  </Link>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
