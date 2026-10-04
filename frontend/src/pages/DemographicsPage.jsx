import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, CartesianGrid,
} from 'recharts';
import { Users, Download, ArrowRight } from 'lucide-react';
import { useDemographicsStructure } from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { cn } from '../lib/format';
import { SkeletonBox } from '../components/Skeleton';
import ApiRetryBanner from '../components/ApiRetryBanner';
import ChartBrandCaption from '../components/ChartBrandCaption';
import { CHART_THEME, GRID_PROPS, TOOLTIP_STYLES, axisTick } from '../lib/chartTheme';
import { usePrefersReducedMotion, useTouchTooltip } from '../lib/chartHooks';
import Chip from '../components/Chip';
import ChipGroup from '../components/ChipGroup';
import Button from '../components/Button';
import { demographicTotal, latestCompleteStructure, demographicChartRows } from '../lib/demographicStructure';
import Breadcrumbs from '../components/Breadcrumbs';
import { track, trackFile, events } from '../lib/track';
import { demographicsTrail } from '../lib/breadcrumbs';
import {
  russiaCategoryPath,
  russiaIndicatorPath,
} from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import '../styles/indicator-russia.css';

const GROUPS = [
  // В-30: границы трудоспособного возраста менялись (пенсионная реформа
  // 2019–2028 поэтапно сдвигает верхнюю границу) — в коротких подписях
  // конкретные возрасты не фиксируем — группы определяются методологией
  // Росстата на каждый год.
  {
    key: 'pop-under-working-age',
    color: CHART_THEME.champagne,
    colorMuted: CHART_THEME.champagne,
    labelKey: 'demo.group.underWorking',
    shortKey: 'demo.group.underWorkingShort',
  },
  {
    key: 'working-age-population',
    color: CHART_THEME.blue,
    colorMuted: CHART_THEME.blue,
    labelKey: 'demo.group.working',
    shortKey: 'demo.group.workingShort',
  },
  {
    key: 'pop-over-working-age',
    color: CHART_THEME.ink,
    colorMuted: CHART_THEME.ink,
    labelKey: 'demo.group.overWorking',
    shortKey: 'demo.group.overWorkingShort',
  },
];

function StructureTooltip({ active, payload, label }) {
  const t = useT();
  if (!active || !payload?.length) return null;
  const total = payload.reduce((s, p) => s + (p.value || 0), 0);
  return (
    <div className="glass-surface w-[min(280px,calc(100vw-72px))] rounded-xl border border-border-subtle px-3 py-3 shadow-2xl">
      <p className="text-xs text-text-secondary mb-2">{t('demo.tooltip.year', { year: label })}</p>
      {payload.map((p) => {
        const g = GROUPS.find(g => g.key === p.dataKey);
        return (
          <div key={p.dataKey} className="flex items-center justify-between gap-3 mb-2">
            <div className="flex min-w-0 items-center gap-2">
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: g?.color }} />
              <span className="min-w-0 whitespace-normal text-xs leading-snug text-text-secondary">{g ? t(g.labelKey) : p.dataKey}</span>
            </div>
            <span className="shrink-0 whitespace-nowrap text-sm font-semibold tabular-nums text-text-primary">
              {p.value?.toFixed(1).replace('.', ',')} {t('demo.tooltip.mln')}
            </span>
          </div>
        );
      })}
      <div className="mt-2 pt-2 border-t border-border-subtle flex justify-between gap-3">
        <span className="text-xs text-text-secondary">{t('demo.tooltip.total')}</span>
        <span className="shrink-0 whitespace-nowrap text-sm font-semibold tabular-nums text-text-primary">
          {total.toFixed(1).replace('.', ',')} {t('demo.tooltip.mln')}
        </span>
      </div>
    </div>
  );
}

function PercentTooltip({ active, payload, label }) {
  const t = useT();
  if (!active || !payload?.length) return null;
  return (
    <div className="glass-surface w-[min(280px,calc(100vw-72px))] rounded-xl border border-border-subtle px-3 py-3 shadow-2xl">
      <p className="text-xs text-text-secondary mb-2">{t('demo.tooltip.year', { year: label })}</p>
      {payload.map((p) => {
        const g = GROUPS.find(g => g.key === p.dataKey);
        return (
          <div key={p.dataKey} className="flex items-center justify-between gap-3 mb-2">
            <div className="flex min-w-0 items-center gap-2">
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: g?.color }} />
              <span className="min-w-0 whitespace-normal text-xs leading-snug text-text-secondary">{g ? t(g.labelKey) : p.dataKey}</span>
            </div>
            <span className="shrink-0 whitespace-nowrap text-sm font-semibold tabular-nums text-text-primary">
              {p.value?.toFixed(1).replace('.', ',')}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

function StructureBar({ latest }) {
  const t = useT();
  if (!latest) return null;
  const total = GROUPS.reduce((s, g) => s + (latest[g.key] || 0), 0);
  if (!total) return null;

  return (
    <div className="space-y-5">
      <div className="flex rounded-xl overflow-hidden h-10 border border-border-subtle" aria-hidden="true">
        {GROUPS.map((g, i) => {
          const pct = ((latest[g.key] || 0) / total) * 100;
          if (pct < 0.5) return null;
          return (
            <div
              key={g.key}
              className={cn(
                'flex items-center justify-center text-xs font-semibold transition-all',
                i > 0 && 'border-l border-white/20',
              )}
              style={{
                width: `${pct}%`,
                background: g.color,
              }}
            >
              {pct > 10 && <span className="rounded bg-white/95 px-1.5 py-0.5 text-text-primary tabular-nums">{pct.toFixed(0)}%</span>}
            </div>
          );
        })}
      </div>
      <ul className="fe-demo-legend">
        {GROUPS.map((g) => {
          const val = latest[g.key] || 0;
          const pct = ((val / total) * 100).toFixed(1).replace('.', ',');
          return (
            <li key={g.key}>
              <Link to={russiaIndicatorPath(g.key)} className="fe-demo-item fe-press">
                <span className="fe-demo-item__dot" style={{ background: g.color }} aria-hidden="true" />
                <span className="fe-demo-item__label">{t(g.labelKey)}</span>
                <span className="fe-demo-item__num">
                  {val.toFixed(1).replace('.', ',')}
                  <span className="fe-demo-item__unit">{t('w3.demo.mln')}</span>
                </span>
                <span className="fe-demo-item__pct">{t('w3.demo.share', { pct })}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function downloadStructureCSV(series, t) {
  if (!series?.length) return;
  const header = [t('demo.csv.year'), ...GROUPS.map(g => t(g.labelKey)), t('demo.csv.total')];
  const rows = [header.join(';')];
  for (const row of series) {
    const total = demographicTotal(row);
    rows.push([
      row.year,
      ...GROUPS.map(g => (row[g.key] ?? '').toString()),
      total === null ? '' : total.toFixed(2),
    ].join(';'));
  }
  const bom = '\uFEFF';
  const blob = new Blob([bom + rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'demographics_structure.csv';
  a.click();
  URL.revokeObjectURL(url);
  trackFile('demographics_structure.csv');
  track(events.DEMOGRAPHICS_CSV);
}

export default function DemographicsPage() {
  const t = useT();
  const { locale } = useLocale();
  const { data, isLoading, isError, refetch, isFetching } = useDemographicsStructure();
  const [chartType, setChartType] = useState('stacked');
  const [chartWidth, setChartWidth] = useState(0);
  const reducedMotion = usePrefersReducedMotion();
  const chartBoxRef = useRef(null);
  const touchTip = useTouchTooltip(chartBoxRef);

  const series = data?.series || [];
  const latest = latestCompleteStructure(series);
  const firstYear = series.length > 0 ? series[0].year : null;

  const demoSeo = getPageSeo('demographics', locale);
  useDocumentMeta({
    title: demoSeo?.title,
    description: demoSeo?.description,
    path: demoSeo?.path,
  });

  // Равные шаги по оси времени: годы, кратные 5 (а при короткой истории кратные 2).
  const yearTicks = (() => {
    const years = series.map((row) => row.year);
    if (years.length < 2) return undefined;
    const step = years.length > 12 ? 5 : 2;
    const ticks = years.filter((y) => y % step === 0);
    return ticks.length >= 2 ? ticks : undefined;
  })();

  const totalLatest = latest
    ? GROUPS.reduce((s, g) => s + (latest[g.key] || 0), 0).toFixed(1).replace('.', ',')
    : null;

  return (
    <div className="fe-data-page max-w-7xl mx-auto px-4 md:px-8 pt-20 pb-24">
      <Breadcrumbs items={demographicsTrail()} className="mb-8" />

      <header className="mb-8 max-w-3xl">
        <div className="flex items-start gap-3 mb-4">
          <span className="fe-demo-icon" aria-hidden="true"><Users className="h-6 w-6" /></span>
          <h1 className="font-display text-3xl md:text-[2.15rem] font-bold text-text-primary tracking-tight min-w-0">
            {t('demo.title')}
          </h1>
        </div>
        <p className="text-text-secondary leading-relaxed">{t('w3.demo.lead')}</p>
        <details className="fe-more mt-2">
          <summary className="fe-more__summary">{t('w3.demo.more')}</summary>
          <p className="fe-more__body">
            {t('demo.intro')}
            {firstYear && t('demo.sourceFrom', { year: firstYear })}
          </p>
        </details>
      </header>

      {isError && (
        <ApiRetryBanner className="mb-6" onRetry={() => refetch()} isFetching={isFetching}>
          <span className="font-semibold">{t('demo.errorTitle')}</span>{' '}
          {t('demo.errorBody')}
        </ApiRetryBanner>
      )}

      {isLoading && (
        <section
          aria-busy="true"
          aria-label={t('demo.loadingAria')}
          className="rounded-[2rem] border border-border-subtle bg-surface p-6 shadow-md ring-1 ring-black/[0.06] md:p-8 mb-8"
        >
          <div className="flex items-center justify-between mb-6">
            <SkeletonBox className="h-3 w-44 rounded-md" />
            <SkeletonBox className="h-3 w-24 rounded-md" />
          </div>
          <SkeletonBox className="h-10 w-full rounded-xl mb-6" />
          <div className="grid grid-cols-3 gap-2 sm:gap-6">
            {[0, 1, 2].map(i => (
              <div key={i} className="space-y-3 text-center">
                <SkeletonBox className="h-3 w-2/3 mx-auto rounded-md" />
                <SkeletonBox className="h-8 w-24 mx-auto rounded-md" />
                <SkeletonBox className="h-3 w-24 mx-auto rounded-md" />
              </div>
            ))}
          </div>
        </section>
      )}

      {!isLoading && latest && (
        <section className="fe-panel p-4 md:p-8 mb-8">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between mb-6">
            <h2 className="fe-demo-h2">
              {t('demo.structureYear', { year: latest.year })}
            </h2>
            <span className="text-sm text-text-secondary tabular-nums">
              {t('demo.totalMln', { n: totalLatest })}
            </span>
          </div>
          <StructureBar latest={latest} />
          <ChartBrandCaption />
        </section>
      )}

      <section id="chart" className="fe-panel scroll-mt-28 p-4 md:p-8 mb-8">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <h2 className="fe-demo-h2">
            {firstYear ? t('demo.dynamicsFrom', { year: firstYear }) : t('demo.dynamics')}
          </h2>
          <div className="flex flex-wrap items-center gap-2">
            <ChipGroup label={t('w3.demo.showAs')} className="fe-chip-row--tight">
              {['stacked', 'percent'].map((mode) => (
                <Chip
                  key={mode}
                  active={chartType === mode}
                  onClick={() => { setChartType(mode); track(events.DEMOGRAPHICS_CHART_TYPE, { type: mode }); }}
                >
                  {mode === 'stacked' ? t('w3.demo.modeAbs') : t('w3.demo.modePct')}
                </Chip>
              ))}
            </ChipGroup>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => downloadStructureCSV(series, t)}
              title={t('demo.downloadCsv')}
            >
              <Download className="w-3.5 h-3.5" aria-hidden="true" />
              {t('demo.downloadCsv')}
            </Button>
          </div>
        </div>

        {isLoading ? (
          <div role="status" aria-busy="true">
            <span className="sr-only">{t('demo.loadingAria')}</span>
            <SkeletonBox className="h-[300px] w-full rounded-2xl sm:h-[360px]" />
          </div>
        ) : series.length === 0 ? (
          <p className="text-text-secondary py-12 text-center">{t('demo.noData')}</p>
        ) : (
          <div ref={chartBoxRef} onPointerDownCapture={touchTip.onPointerDownCapture} className="h-[300px] w-full sm:h-[360px]">
            <ResponsiveContainer width="100%" height="100%" onResize={(width) => setChartWidth(width)}>
              <AreaChart
                data={demographicChartRows(series, chartType === 'percent')}
                margin={{ top: chartType === 'percent' ? 8 : 24, right: 8, left: 4, bottom: 0 }}
              >
                <defs>
                  {GROUPS.map((g) => (
                    <linearGradient key={g.key} id={`grad-${g.key}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={g.color} stopOpacity={0.35} />
                      <stop offset="100%" stopColor={g.color} stopOpacity={0.06} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid {...GRID_PROPS} vertical />
                <XAxis
                  dataKey="year"
                  tick={axisTick()}
                  axisLine={false}
                  tickLine={false}
                  ticks={yearTicks}
                  interval={0}
                />
                <YAxis
                  tick={axisTick()}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={v => chartType === 'percent' ? `${v.toFixed(0)}%` : `${v.toFixed(0)}`}
                  width={44}
                  label={chartType !== 'percent' ? { value: t('demo.axis.mln'), position: 'top', offset: 12, style: axisTick() } : undefined}
                />
                {/* Narrow tooltips also need the Y-axis space: Recharts' own
                    horizontal clamp only knows the smaller data area. */}
                <Tooltip
                  content={chartType === 'percent' ? <PercentTooltip /> : <StructureTooltip />}
                  allowEscapeViewBox={{ x: false, y: true }}
                  position={chartWidth < 280 + 44 + 4 + 8 ? { x: 0 } : undefined}
                  wrapperStyle={{ zIndex: 20 }}
                  cursor={TOOLTIP_STYLES.cursor}
                  {...touchTip.tooltipProps}
                />
                {GROUPS.map((g) => (
                  <Area
                    key={g.key}
                    type="monotone"
                    dataKey={g.key}
                    stackId="1"
                    stroke={g.color}
                    fill={`url(#grad-${g.key})`}
                    strokeWidth={1.5}
                    isAnimationActive={!reducedMotion}
                    animationDuration={600}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {!isLoading && series.length > 0 && (
          <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 mt-4 pt-3 border-t border-border-subtle">
            {GROUPS.map((g) => (
              <div key={g.key} className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: g.color }} aria-hidden="true" />
                <span className="text-sm text-text-secondary">{t(g.labelKey)}</span>
              </div>
            ))}
          </div>
        )}
        <ChartBrandCaption />
      </section>

      <div className="flex justify-center">
        <Link
          to={russiaCategoryPath('population')}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-xl border border-border-subtle bg-surface text-text-secondary hover:text-champagne hover:border-champagne/30 transition-colors text-sm font-medium shadow-sm"
        >
          {t('demo.allIndicators')}
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}
