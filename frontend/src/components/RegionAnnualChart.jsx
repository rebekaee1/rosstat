// График годового регионального ряда: area + опциональный ряд РФ для сравнения.
// Лёгкий и мобильный: без forecast/view-mode машинерии макроблока.
//
// Ось Y для ряда «Россия»: если масштабы региона и РФ несопоставимы (напр.
// посевные площади Краснодарского края ~500 тыс. га против ~7 млн га по РФ),
// одна общая ось прижимает линию региона к нулю и график перестаёт читаться.
// В этом случае РФ автоматически уводится на правую ось (dual-axis), а под
// графиком появляется подпись, какая линия к какой оси относится.
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis,
  Tooltip, CartesianGrid,
} from 'recharts';
import { formatRegionValue, formatCompactTick, compactTickAxisWidth } from '../lib/regionsApi';
import { pickChartAxisTicks, chartAxisTickBudget } from '../lib/format';
import { useLocale } from '../i18n';

// Порог несопоставимости масштабов: если maxРФ/maxРегион больше — вторая ось.
const DUAL_AXIS_RATIO = 3;

const COMPARE_COLOR = '#5B7DA8';

// Подпись месяца для оси/тултипа: «май 2012» / «May 2012».
function monthTickLabel(p, locale) {
  const loc = locale === 'en' ? 'en' : 'ru';
  const names = loc === 'en'
    ? ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    : ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
  const m = (p.month ?? 1) - 1;
  return `${names[m]} ${p.year}`;
}

function RegionTooltip({ active, payload, label, unit, regionName, compareName, russiaLabel, tickLabel }) {
  if (!active || !payload?.length) return null;
  const region = payload.find(p => p.dataKey === 'value' && p.value != null);
  const compare = payload.find(p => p.dataKey === 'compare' && p.value != null);
  const russia = payload.find(p => p.dataKey === 'russia' && p.value != null);
  const periodLabel = tickLabel ? tickLabel(label) : label;
  return (
    <div className="bg-surface border border-border-subtle rounded-lg px-3 py-2 shadow-lg text-xs">
      <div className="text-text-tertiary font-mono mb-1">{periodLabel}</div>
      {region && (
        <div className="font-mono font-semibold text-champagne">
          {regionName}: {formatRegionValue(region.value)}
        </div>
      )}
      {compare && (
        <div className="font-mono font-semibold mt-0.5" style={{ color: COMPARE_COLOR }}>
          {compareName}: {formatRegionValue(compare.value)}
        </div>
      )}
      {russia && (
        <div className="font-mono text-text-secondary mt-0.5">
          {russiaLabel}: {formatRegionValue(russia.value)}
        </div>
      )}
      {unit ? <div className="mt-1 text-[10px] text-text-tertiary">{unit}</div> : null}
    </div>
  );
}

const tickStyle = { fontSize: 11, fill: 'rgba(26,26,46,0.45)', fontFamily: 'JetBrains Mono, monospace' };

export default function RegionAnnualChart({
  series,
  russiaSeries = null,
  compareSeries = null,
  compareName = '',
  unit = '',
  regionName = '',
  height = 320,
  frequency = 'annual',
}) {
  const { t, locale } = useLocale();
  const wrapRef = useRef(null);
  const [plotWidth, setPlotWidth] = useState(0);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect?.width;
      if (w) setPlotWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const monthly = frequency === 'monthly';
  // Ключ точки: год (annual) или «YYYY-MM» (monthly) — join-ключ рядов РФ/сравнения.
  const periodKey = (p) => (monthly ? (p.label || `${p.year}-${String(p.month).padStart(2, '0')}`) : p.year);

  const data = useMemo(() => {
    const rfByPeriod = new Map((russiaSeries || []).map(p => [periodKey(p), p.value]));
    const cmpByPeriod = new Map((compareSeries || []).map(p => [periodKey(p), p.value]));
    return (series || []).map(p => ({
      period: periodKey(p),
      year: p.year,
      label: monthly ? monthTickLabel(p, locale) : String(p.year),
      value: p.value,
      compare: cmpByPeriod.get(periodKey(p)) ?? null,
      russia: rfByPeriod.get(periodKey(p)) ?? null,
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series, russiaSeries, compareSeries, monthly, locale]);

  const showRussia = useMemo(
    () => data.some(d => d.russia != null),
    [data],
  );

  // Несоразмерные масштабы (регион ≪ Россия или наоборот) → РФ на правую ось.
  const dualAxis = useMemo(() => {
    if (!showRussia) return false;
    const regionMax = Math.max(...data.map(d => Math.abs(d.value ?? 0)));
    const rfMax = Math.max(...data.map(d => Math.abs(d.russia ?? 0)));
    if (!regionMax || !rfMax) return false;
    const ratio = rfMax / regionMax;
    return ratio > DUAL_AXIS_RATIO || ratio < 1 / DUAL_AXIS_RATIO;
  }, [data, showRussia]);

  const isNarrow = plotWidth > 0 && plotWidth < 420;

  // Ширина осей — по самой длинной подписи; на узком экране жёстче клэмп,
  // иначе dual-axis съедает половину plot-area (скрин Белгород/Россия).
  const leftAxisWidth = useMemo(
    () => compactTickAxisWidth(data.flatMap(d => [d.value, d.compare]), { narrow: isNarrow }),
    [data, isNarrow],
  );
  const rightAxisWidth = useMemo(() => {
    if (!dualAxis) return 0;
    return compactTickAxisWidth(data.map(d => d.russia), { narrow: isNarrow });
  }, [data, dualAxis, isNarrow]);

  const xTicks = useMemo(() => {
    const axisW = Math.max(
      0,
      plotWidth - leftAxisWidth - (dualAxis ? rightAxisWidth : 0) - 24,
    );
    let budget = chartAxisTickBudget(axisW, monthly ? 7 : 4);
    // Dual-axis на узком экране: 4 года вместо 6 — иначе подписи года
    // визуально «прыгают» между плотными промежутками.
    if (isNarrow && dualAxis) budget = Math.min(budget, 4);
    else if (isNarrow) budget = Math.min(budget, 5);
    return pickChartAxisTicks(data, budget, {
      dateKey: 'period',
      cadence: monthly ? null : 'annual',
      plotWidthPx: axisW,
      formatLabel: (v) => {
        const d = data.find((x) => String(x.period) === String(v));
        return d ? d.label : String(v);
      },
    });
  }, [data, plotWidth, leftAxisWidth, rightAxisWidth, dualAxis, isNarrow, monthly]);

  if (!data.length) return null;

  const chartMargin = {
    top: 12,
    right: dualAxis ? Math.max(8, rightAxisWidth - 4) : (isNarrow ? 8 : 12),
    bottom: 4,
    left: isNarrow ? 0 : 4,
  };
  const chartHeight = isNarrow ? Math.min(height, 260) : height;
  const russiaLabel = t('regions.ind.russia');

  return (
    <div>
      <div
        ref={wrapRef}
        style={{ width: '100%', height: chartHeight }}
        role="img"
        aria-label={t('regions.ind.chartAria', {
          region: regionName,
          from: data[0].label,
          to: data[data.length - 1].label,
        })}
      >
        <ResponsiveContainer>
          <ComposedChart data={data} margin={chartMargin}>
            <defs>
              <linearGradient id="regionArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#B8942F" stopOpacity={0.28} />
                <stop offset="100%" stopColor="#B8942F" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" vertical={false} />
            <XAxis
              dataKey="period"
              tick={tickStyle}
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
                fontSize: isNarrow ? 10 : 11,
                fill: dualAxis ? 'rgba(184,148,47,0.75)' : tickStyle.fill,
              }}
              tickFormatter={(v) => formatCompactTick(v, { narrow: isNarrow })}
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
                  fontSize: isNarrow ? 10 : 11,
                  fill: 'rgba(58,58,80,0.6)',
                }}
                tickFormatter={(v) => formatCompactTick(v, { narrow: isNarrow })}
                tickLine={false}
                axisLine={false}
                width={rightAxisWidth}
                domain={['auto', 'auto']}
              />
            )}
            <Tooltip
              content={(
                <RegionTooltip
                  unit={unit}
                  regionName={regionName}
                  compareName={compareName}
                  russiaLabel={russiaLabel}
                  tickLabel={(v) => {
                    const d = data.find((x) => String(x.period) === String(v));
                    return d ? d.label : String(v);
                  }}
                />
              )}
            />
            <Area
              yAxisId="region"
              type="monotone"
              dataKey="value"
              stroke="#B8942F"
              strokeWidth={2.2}
              fill="url(#regionArea)"
              dot={false}
              activeDot={{ r: 4, fill: '#B8942F' }}
              isAnimationActive={false}
            />
            {compareSeries?.length > 0 && (
              <Line
                yAxisId="region"
                type="monotone"
                dataKey="compare"
                stroke={COMPARE_COLOR}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3.5, fill: COMPARE_COLOR }}
                isAnimationActive={false}
              />
            )}
            {showRussia && (
              <Line
                yAxisId={dualAxis ? 'rf' : 'region'}
                type="monotone"
                dataKey="russia"
                stroke="#3A3A50"
                strokeWidth={1.6}
                strokeDasharray="5 4"
                dot={false}
                isAnimationActive={false}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {dualAxis && (
        <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-text-tertiary px-1">
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block w-4 h-0.5 rounded bg-champagne" />
            {t('regions.ind.axisRegion', { region: regionName })}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block w-4 border-t-2 border-dashed border-[#3A3A50]" />
            {t('regions.ind.axisRussia')}
          </span>
        </div>
      )}
    </div>
  );
}
