import { useState, useMemo, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  ResponsiveContainer, ComposedChart, Line, XAxis, YAxis,
  Tooltip, CartesianGrid,
} from 'recharts';
import { ArrowLeft, Activity, GitCompare } from 'lucide-react';
import { useIndicators, useIndicatorData } from '../lib/hooks';
import { formatDate, formatAxisTick, formatValueWithUnit, unitSuffix, unitDigits, cn, isCpiIndex } from '../lib/format';
import useDocumentMeta from '../lib/useMeta';
import { SkeletonBox, ChartSkeleton } from '../components/Skeleton';
import { track, events } from '../lib/track';

const RANGE_OPTIONS = [
  { key: '3y', label: '3 года', months: 36 },
  { key: '5y', label: '5 лет', months: 60 },
  { key: '10y', label: '10 лет', months: 120 },
  { key: 'all', label: 'Все', months: null },
];

const COLOR_A = '#d4a574';
const COLOR_B = '#7dd3fc';

function IndicatorSelector({ value, onChange, indicators, label, disabled }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[10px] font-mono uppercase tracking-widest text-text-tertiary">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="bg-surface border border-border-subtle rounded-xl px-4 py-2.5 text-sm text-text-primary font-medium appearance-none cursor-pointer hover:border-champagne/30 transition-colors disabled:opacity-50"
      >
        <option value="">Выберите показатель</option>
        {indicators?.map((ind) => (
          <option key={ind.code} value={ind.code}>
            {ind.name} ({unitSuffix(ind.unit)})
          </option>
        ))}
      </select>
    </div>
  );
}

function CompareTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  return (
    <div className="glass-surface rounded-xl border border-border-subtle px-4 py-3 shadow-2xl min-w-[220px]">
      <p className="text-xs font-mono text-text-tertiary mb-2">{formatDate(label, 'full')}</p>
      {payload.map((p) => (
        p.value != null && (
          <div key={p.dataKey} className="flex items-center justify-between gap-4 mb-1">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
              <span className="text-xs text-text-tertiary truncate max-w-[140px]">{p.name}</span>
            </div>
            <span className="text-sm font-mono font-semibold" style={{ color: p.color }}>
              {formatValueWithUnit(p.value, p.payload?.[`${p.dataKey}_unit`] || '%')}
            </span>
          </div>
        )
      ))}
    </div>
  );
}

export default function ComparePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const codeA = searchParams.get('a') || '';
  const codeB = searchParams.get('b') || '';
  const [range, setRange] = useState('5y');

  useDocumentMeta({
    title: 'Сравнение индикаторов',
    description: 'Сравните два экономических показателя на одном графике с двумя осями Y.',
    path: '/compare',
  });

  const { data: indicators, isLoading: loadingInd } = useIndicators();

  const setCode = useCallback((which, code) => {
    const next = new URLSearchParams(searchParams);
    next.set(which, code);
    setSearchParams(next, { replace: true });
    track(events.COMPARE_CHANGE, { position: which, code });
  }, [searchParams, setSearchParams]);

  const { data: dataA, isLoading: loadA, isError: errorA } = useIndicatorData(codeA);
  const { data: dataB, isLoading: loadB, isError: errorB } = useIndicatorData(codeB);

  const indA = useMemo(() => indicators?.find((i) => i.code === codeA), [indicators, codeA]);
  const indB = useMemo(() => indicators?.find((i) => i.code === codeB), [indicators, codeB]);

  const chartData = useMemo(() => {
    const pointsA = Array.isArray(dataA?.data) ? dataA.data : [];
    const pointsB = Array.isArray(dataB?.data) ? dataB.data : [];

    const adjA = isCpiIndex(codeA);
    const adjB = isCpiIndex(codeB);
    const dateMap = new Map();
    for (const p of pointsA) {
      dateMap.set(p.date, { date: p.date, valA: adjA ? p.value - 100 : p.value, valA_unit: indA?.unit || '%' });
    }
    for (const p of pointsB) {
      const existing = dateMap.get(p.date) || { date: p.date };
      existing.valB = adjB ? p.value - 100 : p.value;
      existing.valB_unit = indB?.unit || '%';
      dateMap.set(p.date, existing);
    }

    const all = [...dateMap.values()].sort((a, b) => a.date.localeCompare(b.date));

    const rangeOpt = RANGE_OPTIONS.find((r) => r.key === range);
    if (!rangeOpt?.months || all.length === 0) return all;

    const last = new Date(all[all.length - 1].date);
    const cutoff = new Date(last);
    cutoff.setUTCMonth(cutoff.getUTCMonth() - rangeOpt.months);
    const cutoffStr = cutoff.toISOString().slice(0, 10);

    return all.filter((p) => p.date >= cutoffStr);
  }, [dataA, dataB, indA, indB, range, codeA, codeB]);

  const hasData = chartData.length > 0 && (codeA || codeB);
  const loading = loadA || loadB;
  const hasError = (codeA && errorA) || (codeB && errorB);

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-24 md:pb-28">
      <div className="mb-12 md:mb-16 max-w-4xl">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-text-tertiary hover:text-champagne transition-colors mb-8 lift-hover group"
        >
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
          Главная
        </Link>

        <div className="flex items-center gap-3 mb-4">
          <span className="px-3 py-1 rounded-full border border-border-subtle bg-obsidian-light text-[10px] font-mono uppercase tracking-widest text-text-secondary flex items-center gap-2">
            <GitCompare className="w-3 h-3 text-champagne" />
            Сравнение
          </span>
        </div>

        <h1 className="text-4xl md:text-5xl lg:text-6xl font-display font-bold tracking-tight mb-4 leading-tight">
          Сравнение показателей
        </h1>
        <p className="text-sm md:text-base text-text-tertiary max-w-2xl">
          Выберите два индикатора для визуального сопоставления на одном графике.
          Каждый показатель получает свою ось Y.
        </p>
      </div>

      <section className="mb-8">
        {loadingInd ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <SkeletonBox className="h-20 rounded-xl" />
            <SkeletonBox className="h-20 rounded-xl" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <IndicatorSelector
              value={codeA}
              onChange={(c) => setCode('a', c)}
              indicators={indicators}
              label="Показатель A"
            />
            <IndicatorSelector
              value={codeB}
              onChange={(c) => setCode('b', c)}
              indicators={indicators}
              label="Показатель B"
            />
          </div>
        )}
      </section>

      {hasError && (
        <div className="mb-6 rounded-2xl border border-champagne/35 bg-warn-surface px-4 py-4 text-sm shadow-md" role="alert">
          <p className="text-text-primary">
            <span className="font-semibold">Не удалось загрузить данные</span>{' '}
            для {errorA && codeA ? `«${indA?.name || codeA}»` : ''}{errorA && errorB ? ' и ' : ''}{errorB && codeB ? `«${indB?.name || codeB}»` : ''}.
            Попробуйте выбрать другие показатели или обновите страницу.
          </p>
        </div>
      )}

      <section className="mb-8">
        <div className="flex items-center gap-4 border-b border-border-subtle pb-4 mb-6 flex-wrap">
          <Activity className="w-4 h-4 text-champagne" />
          <span className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary">Период</span>
          <div className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle">
            {RANGE_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => { setRange(opt.key); track(events.COMPARE_RANGE, { range: opt.key }); }}
                className={cn(
                  'px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
                  range === opt.key
                    ? 'bg-champagne/15 text-champagne'
                    : 'text-text-tertiary hover:text-text-secondary'
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <ChartSkeleton />
        ) : !hasData ? (
          <div className="h-96 rounded-[2rem] bg-surface border border-border-subtle border-dashed flex flex-col items-center justify-center text-text-tertiary p-8">
            <GitCompare className="w-10 h-10 mb-4 opacity-20" />
            <p className="text-sm text-center max-w-md">
              {(!codeA && !codeB)
                ? 'Выберите хотя бы один показатель для построения графика.'
                : 'Данные загружаются или отсутствуют для выбранных индикаторов.'}
            </p>
          </div>
        ) : (
          <div className="rounded-[2rem] bg-surface border border-border-subtle p-4 md:p-6">
            <ResponsiveContainer width="100%" height={480}>
              <ComposedChart data={chartData} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(255,255,255,0.04)"
                  vertical={false}
                />
                <XAxis
                  dataKey="date"
                  tickFormatter={(d) => formatDate(d, 'short')}
                  tick={{ fill: 'rgba(255,255,255,0.35)', fontSize: 10, fontFamily: 'monospace' }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
                  tickLine={false}
                  minTickGap={40}
                />
                {codeA && (
                  <YAxis
                    yAxisId="left"
                    tick={{ fill: COLOR_A, fontSize: 10, fontFamily: 'monospace' }}
                    axisLine={false}
                    tickLine={false}
                    width={60}
                    tickFormatter={(v) => formatAxisTick(v, unitDigits(indA?.unit))}
                  />
                )}
                {codeB && (
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tick={{ fill: COLOR_B, fontSize: 10, fontFamily: 'monospace' }}
                    axisLine={false}
                    tickLine={false}
                    width={60}
                    tickFormatter={(v) => formatAxisTick(v, unitDigits(indB?.unit))}
                  />
                )}
                <Tooltip
                  content={<CompareTooltip />}
                  cursor={{ stroke: 'rgba(255,255,255,0.15)' }}
                />
                {codeA && (
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="valA"
                    name={indA?.name || codeA}
                    stroke={COLOR_A}
                    strokeWidth={2}
                    dot={false}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                )}
                {codeB && (
                  <Line
                    yAxisId={codeA ? 'right' : 'left'}
                    type="monotone"
                    dataKey="valB"
                    name={indB?.name || codeB}
                    stroke={COLOR_B}
                    strokeWidth={2}
                    dot={false}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                )}
              </ComposedChart>
            </ResponsiveContainer>

            <div className="flex items-center justify-center gap-8 mt-4 text-xs font-mono">
              {codeA && indA && (
                <div className="flex items-center gap-2">
                  <span className="w-3 h-0.5 rounded-full" style={{ backgroundColor: COLOR_A }} />
                  <span style={{ color: COLOR_A }}>{indA.name}</span>
                </div>
              )}
              {codeB && indB && (
                <div className="flex items-center gap-2">
                  <span className="w-3 h-0.5 rounded-full" style={{ backgroundColor: COLOR_B }} />
                  <span style={{ color: COLOR_B }}>{indB.name}</span>
                </div>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
