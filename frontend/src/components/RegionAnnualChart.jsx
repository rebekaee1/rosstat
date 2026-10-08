// График годового регионального ряда: area + опциональный ряд РФ для сравнения.
// Лёгкий и мобильный: без forecast/view-mode машинерии макроблока.
//
// Ось Y для ряда «Россия»: если масштабы региона и РФ несопоставимы (напр.
// посевные площади Краснодарского края ~500 тыс. га против ~7 млн га по РФ),
// одна общая ось прижимает линию региона к нулю и график перестаёт читаться.
// В этом случае обе линии пересчитываются в «Россия = 100» и рисуются на одной оси: две разные
// шкалы в одном поле (волна 6) заставляли новичка сравнивать высоту линий, которая ничего не значит.
// Старый вариант с правой осью остался только для графика с нашим прогнозом (у него нет ряда РФ).
import { useCallback, useMemo, useRef } from 'react';
import {
  ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis,
  Tooltip, CartesianGrid,
} from 'recharts';
import { formatRegionValue, axisScaleFor, formatScaledTick } from '../lib/regionsApi';
import { pickChartAxisTicks, chartAxisTickBudget } from '../lib/format';
import { useLocale } from '../i18n';
import {
  CHART_THEME, GRID_PROPS, NARROW_CHART_WIDTH, TOOLTIP_STYLES, axisTick, axisSampleValues, axisWidthForLabels,
} from '../lib/chartTheme';
import { useChartGlassIds, useElementWidth, useTouchTooltip } from '../lib/chartHooks';
import ChartBrandCaption from './ChartBrandCaption';
import ChartGlassDefs from './ChartGlassDefs';
import '../styles/k4-charts.css';

// Порог несопоставимости масштабов: если maxРФ/maxРегион больше — вторая ось.
const DUAL_AXIS_RATIO = 3;

const COMPARE_COLOR = CHART_THEME.sapphire;

/** Линия «рисуется» один раз; у тех, кто просил меньше движения, сразу готовый график. */
function chartMayAnimate() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

// Подпись месяца для оси/тултипа: «май 2012» / «May 2012».
function monthTickLabel(p, locale) {
  const loc = locale === 'en' ? 'en' : 'ru';
  const names = loc === 'en'
    ? ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    : ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
  const m = (p.month ?? 1) - 1;
  return `${names[m]} ${p.year}`;
}

function RegionTooltip({ active, payload, label, unit, regionName, compareName, russiaLabel, forecastLabel, tickLabel, indexNote }) {
  if (!active || !payload?.length) return null;
  const region = payload.find(p => p.dataKey === 'value' && p.value != null);
  const compare = payload.find(p => p.dataKey === 'compare' && p.value != null);
  const russia = payload.find(p => p.dataKey === 'russia' && p.value != null);
  const forecast = payload.find(p => p.dataKey === 'forecast' && p.value != null);
  const periodLabel = tickLabel ? tickLabel(label) : label;
  // Короткая единица («₽», «%») стоит рядом с числом, а не отдельной строкой внизу: раньше «₽» оставался сам по себе на второй строке.
  const inlineUnit = !indexNote && unit && String(unit).length <= 6 ? `\u00A0${unit}` : '';
  const fmt = (v) => `${formatRegionValue(v)}${inlineUnit}`;
  return (
    <div className="fe-chart-tooltip fe-chart-tooltip--stack text-xs max-w-[calc(100vw-48px)]">
      <div className="text-text-secondary mb-1">{periodLabel}</div>
      {region && (
        <div className="font-semibold tabular-nums text-champagne-ink">
          {regionName}: {fmt(region.value)}
        </div>
      )}
      {compare && (
        <div className="font-semibold tabular-nums mt-0.5 text-text-primary">
          {compareName}: {fmt(compare.value)}
        </div>
      )}
      {russia && (
        <div className="tabular-nums text-text-secondary mt-0.5">
          {russiaLabel}: {fmt(russia.value)}
        </div>
      )}
      {forecast && (
        <div className="tabular-nums text-champagne-ink mt-0.5">
          {forecastLabel}: {fmt(forecast.value)}
        </div>
      )}
      {indexNote
        ? <div className="mt-1 text-[11px] text-text-secondary">{indexNote}</div>
        : (unit && !inlineUnit ? <div className="mt-1 text-[11px] text-text-secondary">{unit}</div> : null)}
    </div>
  );
}

const tickStyle = axisTick();

export default function RegionAnnualChart({
  series,
  russiaSeries = null,
  compareSeries = null,
  compareName = '',
  unit = '',
  regionName = '',
  height = 320,
  frequency = 'annual',
  nationalLabel = null,
  forecastSeries = null,
}) {
  const { t, locale } = useLocale();
  const wrapRef = useRef(null);
  const [setWidthNode, plotWidth] = useElementWidth();
  const touchTip = useTouchTooltip(wrapRef);
  const setWrap = useCallback((node) => { wrapRef.current = node; setWidthNode(node); }, [setWidthNode]);
  const glass = useChartGlassIds('k4r');
  const animate = chartMayAnimate();

  const monthly = frequency === 'monthly';
  const quarterly = frequency === 'quarterly';
  const dated = monthly || quarterly;
  const periodKey = (p) => {
    if (monthly) return p.label || `${p.year}-${String(p.month).padStart(2, '0')}`;
    if (quarterly) return p.label || `${p.year}-Q${p.quarter || Math.ceil((p.month || 1) / 3)}`;
    return p.year;
  };

  const data = useMemo(() => {
    const rfByPeriod = new Map((russiaSeries || []).map(p => [periodKey(p), p.value]));
    const cmpByPeriod = new Map((compareSeries || []).map(p => [periodKey(p), p.value]));
    const observed = (series || []).map(p => ({
      period: periodKey(p),
      year: p.year,
      label: monthly
        ? monthTickLabel(p, locale)
        : quarterly
          ? (locale === 'en' ? `${p.year} Q${p.quarter || 1}` : `${p.quarter || 1} кв. ${p.year}`)
          : String(p.year),
      value: p.value,
      compare: cmpByPeriod.get(periodKey(p)) ?? null,
      russia: rfByPeriod.get(periodKey(p)) ?? null,
      forecast: null,
    }));
    if (forecastSeries?.length && observed.length) {
      observed[observed.length - 1].forecast = observed[observed.length - 1].value;
      for (const p of forecastSeries) {
        observed.push({
          period: periodKey(p), year: p.year,
          label: monthly ? monthTickLabel(p, locale)
            : quarterly ? (locale === 'en' ? `${p.year} Q${p.quarter || 1}` : `${p.quarter || 1} кв. ${p.year}`)
              : String(p.year),
          value: null, compare: null, russia: null, forecast: p.value,
        });
      }
    }
    return observed;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series, russiaSeries, compareSeries, forecastSeries, monthly, quarterly, locale]);

  const showRussia = useMemo(
    () => data.some(d => d.russia != null),
    [data],
  );

  // Несоразмерные масштабы (регион ≪ Россия или наоборот) → РФ на правую ось.
  const scalesDiffer = useMemo(() => {
    if (!showRussia) return false;
    const regionMax = Math.max(...data.map(d => Math.abs(d.value ?? 0)));
    const rfMax = Math.max(...data.map(d => Math.abs(d.russia ?? 0)));
    if (!regionMax || !rfMax) return false;
    const ratio = rfMax / regionMax;
    return ratio > DUAL_AXIS_RATIO || ratio < 1 / DUAL_AXIS_RATIO;
  }, [data, showRussia]);

  // Несопоставимые масштабы: честнее всего «Россия = 100» на одной оси (регион в процентах от России).
  // Индекс имеет смысл только для положительных величин (у изменений за год бывают минусы — там остаётся вторая ось).
  const positiveOnly = useMemo(
    () => data.every((d) => (d.russia == null || d.russia > 0) && (d.value == null || d.value >= 0) && (d.compare == null || d.compare >= 0)),
    [data],
  );
  const indexMode = scalesDiffer && !forecastSeries?.length && positiveOnly;
  const dualAxis = scalesDiffer && !indexMode;
  const plotData = useMemo(() => {
    if (!indexMode) return data;
    const idx = (v, rf) => (v != null && rf ? (Number(v) / Number(rf)) * 100 : null);
    return data.map((d) => ({
      ...d,
      value: idx(d.value, d.russia),
      compare: idx(d.compare, d.russia),
      russia: d.russia ? 100 : null,
    }));
  }, [data, indexMode]);

  const isNarrow = plotWidth > 0 && plotWidth < NARROW_CHART_WIDTH;

  // Ширина осей — по самой длинной подписи; на узком экране жёстче клэмп,
  // иначе dual-axis съедает половину plot-area (скрин Белгород/Россия).
  const leftValues = useMemo(() => plotData.flatMap(d => [d.value, d.compare, d.forecast]), [plotData]);
  const rightValues = useMemo(() => (dualAxis ? data.map(d => d.russia) : []), [data, dualAxis]);
  const leftScale = useMemo(() => axisScaleFor(leftValues), [leftValues]);
  const rightScale = useMemo(() => axisScaleFor(rightValues), [rightValues]);
  const leftAxisWidth = useMemo(() => axisWidthForLabels(
    axisSampleValues(leftValues).map((v) => formatScaledTick(v, leftScale)),
    { min: isNarrow ? 36 : 44, max: 96, perChar: 6.8, pad: 10 },
  ), [leftValues, leftScale, isNarrow]);
  const rightAxisWidth = useMemo(() => (dualAxis ? axisWidthForLabels(
    axisSampleValues(rightValues).map((v) => formatScaledTick(v, rightScale)),
    { min: isNarrow ? 36 : 44, max: 96, perChar: 6.8, pad: 10 },
  ) : 0), [dualAxis, rightValues, rightScale, isNarrow]);

  const xTicks = useMemo(() => {
    const axisW = Math.max(
      0,
      plotWidth - leftAxisWidth - (dualAxis ? rightAxisWidth : 0) - 24,
    );
    let budget = chartAxisTickBudget(axisW, dated ? 7 : 4);
    // Dual-axis на узком экране: 4 года вместо 6 — иначе подписи года
    // визуально «прыгают» между плотными промежутками.
    if (isNarrow && dualAxis) budget = Math.min(budget, 4);
    else if (isNarrow) budget = Math.min(budget, 5);
    return pickChartAxisTicks(data, budget, {
      dateKey: 'period',
      cadence: dated ? null : 'annual',
      plotWidthPx: axisW,
      formatLabel: (v) => {
        const d = data.find((x) => String(x.period) === String(v));
        return d ? d.label : String(v);
      },
    });
  }, [data, plotWidth, leftAxisWidth, rightAxisWidth, dualAxis, isNarrow, dated]);

  if (!data.length) return null;

  const chartMargin = {
    top: 12,
    right: dualAxis ? Math.max(8, rightAxisWidth - 4) : (isNarrow ? 8 : 12),
    bottom: 4,
    left: isNarrow ? 0 : 4,
  };
  const chartHeight = isNarrow ? Math.min(height, 260) : height;
  const russiaLabel = nationalLabel || t('regions.ind.russia');

  return (
    <div>
      <div
        ref={setWrap}
        onPointerDownCapture={touchTip.onPointerDownCapture}
        style={{ width: '100%', height: chartHeight }}
        role="img"
        aria-label={t('regions.ind.chartAria', {
          region: regionName,
          from: data[0].label,
          to: data[data.length - 1].label,
        })}
      >
        <ResponsiveContainer>
          <ComposedChart data={plotData} margin={chartMargin}>
            <defs>
              <ChartGlassDefs ids={glass} width={Math.max(plotWidth, 320)} />
            </defs>
            <CartesianGrid {...GRID_PROPS} />
            <XAxis
              dataKey="period"
              tick={({ x, y, payload }) => {
                const key = String(payload.value);
                const label = data.find((point) => String(point.period) === key)?.label || key;
                const anchor = xTicks.length < 2 ? 'middle'
                  : key === String(xTicks[0]) ? 'start'
                    : key === String(xTicks[xTicks.length - 1]) ? 'end' : 'middle';
                return <text x={x} y={y} dy={12} textAnchor={anchor} {...tickStyle}>{label}</text>;
              }}
              tickLine={false}
              axisLine={false}
              ticks={xTicks}
              interval={0}
              tickMargin={6}
              padding={{ left: 4, right: 4 }}
            />
            <YAxis
              yAxisId="region"
              tick={{
                ...tickStyle,
                fill: dualAxis ? CHART_THEME.ink : tickStyle.fill,
              }}
              tickFormatter={(v) => formatScaledTick(v, leftScale)}
              tickLine={false}
              axisLine={false}
              width={leftAxisWidth}
              domain={['auto', 'auto']}
            />
            {dualAxis && (
              <YAxis
                yAxisId="rf"
                orientation="right"
                tick={{
                  ...tickStyle,
                  fill: CHART_THEME.axis,
                }}
                tickFormatter={(v) => formatScaledTick(v, rightScale)}
                tickLine={false}
                axisLine={false}
                width={rightAxisWidth}
                domain={['auto', 'auto']}
              />
            )}
            <Tooltip
              cursor={TOOLTIP_STYLES.cursor}
              {...touchTip.tooltipProps}
              content={(
                <RegionTooltip
                  unit={unit}
                  regionName={regionName}
                  compareName={compareName}
                  russiaLabel={russiaLabel}
                  forecastLabel={locale === 'en' ? 'Our forecast' : 'Наш прогноз'}
                  indexNote={indexMode ? t('w6f.reg.indexNote') : null}
                  tickLabel={(v) => {
                    const d = data.find((x) => String(x.period) === String(v));
                    return d ? d.label : String(v);
                  }}
                />
              )}
            />
            <Area
              className="k4-ribbon"
              yAxisId="region"
              type="linear"
              dataKey="value"
              stroke={`url(#${glass.ribbon})`}
              strokeWidth={3}
              strokeLinecap="round"
              strokeLinejoin="round"
              fill={`url(#${glass.area})`}
              dot={false}
              activeDot={{ r: 5, fill: CHART_THEME.gold, stroke: '#FFFFFF', strokeWidth: 2 }}
              isAnimationActive={animate}
              animationDuration={900}
              animationEasing="ease-out"
            />
            {compareSeries?.length > 0 && (
              <Line
                className="k4-ribbon k4-ribbon--sapphire"
                yAxisId="region"
                type="linear"
                dataKey="compare"
                stroke={`url(#${glass.sapphire})`}
                strokeWidth={2.5}
                strokeLinecap="round"
                dot={false}
                activeDot={{ r: 4, fill: COMPARE_COLOR, stroke: '#FFFFFF', strokeWidth: 2 }}
                isAnimationActive={false}
              />
            )}
            {showRussia && (
              <Line
                className="k4-ribbon k4-ribbon--plain"
                yAxisId={dualAxis ? 'rf' : 'region'}
                type="linear"
                dataKey="russia"
                stroke={CHART_THEME.axis}
                strokeOpacity={0.7}
                strokeWidth={1.8}
                strokeLinecap="round"
                dot={false}
                isAnimationActive={false}
              />
            )}
            {forecastSeries?.length > 0 && (
              <Line
                className="k4-forecast"
                yAxisId="region"
                type="linear"
                dataKey="forecast"
                stroke={`url(#${glass.forecast})`}
                strokeWidth={3}
                strokeLinecap="round"
                dot={false}
                activeDot={{ r: 4.5, fill: CHART_THEME.champagneInk, stroke: '#FFFFFF', strokeWidth: 2 }}
                isAnimationActive={false}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {showRussia && !dualAxis && (
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 px-1 text-sm text-text-secondary">
          <span className="inline-flex items-center gap-1.5">
            <span className="k4-swatch k4-swatch--ribbon" aria-hidden="true" />
            {regionName}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="k4-swatch" style={{ background: CHART_THEME.axis, opacity: 0.7 }} aria-hidden="true" />
            {indexMode ? t('w6f.reg.russia100', { name: russiaLabel }) : russiaLabel}
          </span>
          {indexMode && (
            <span className="basis-full text-xs" data-testid="index-note">{t('w6f.reg.indexExplain', { region: regionName })}</span>
          )}
        </div>
      )}
      {dualAxis && (
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 px-1 text-sm text-text-secondary">
          <span className="inline-flex items-center gap-1.5">
            <span className="k4-swatch k4-swatch--ribbon" aria-hidden="true" />
            {t('regions.ind.axisRegion', { region: regionName })}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="k4-swatch" style={{ background: CHART_THEME.axis, opacity: 0.7 }} aria-hidden="true" />
            {nationalLabel || t('regions.ind.axisRussia')}
          </span>
        </div>
      )}
      <ChartBrandCaption />
    </div>
  );
}
