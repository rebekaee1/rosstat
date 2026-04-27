import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, CartesianGrid,
} from 'recharts';
import { ChevronRight, Users, Download, ArrowRight } from 'lucide-react';
import { useDemographicsStructure } from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import { cn } from '../lib/format';
import { SkeletonBox } from '../components/Skeleton';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { track, trackFile, events } from '../lib/track';

const GROUPS = [
  { key: 'pop-under-working-age', color: '#D4A574', colorMuted: '#D4A574', label: 'Моложе трудоспособного', short: 'Дети (0–15)' },
  { key: 'working-age-population', color: '#B8942F', colorMuted: '#B8942F', label: 'Трудоспособные', short: 'Трудоспособные' },
  { key: 'pop-over-working-age', color: '#8B7A6B', colorMuted: '#8B7A6B', label: 'Старше трудоспособного', short: 'Старше (60+/55+)' },
];

function StructureTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((s, p) => s + (p.value || 0), 0);
  return (
    <div className="glass-surface rounded-xl border border-border-subtle px-4 py-3 shadow-2xl min-w-[220px]">
      <p className="text-xs font-mono text-text-tertiary mb-2">{label} г.</p>
      {payload.map((p) => {
        const g = GROUPS.find(g => g.key === p.dataKey);
        return (
          <div key={p.dataKey} className="flex items-center justify-between gap-4 mb-1">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full" style={{ background: g?.color }} />
              <span className="text-xs text-text-secondary">{g?.label}</span>
            </div>
            <span className="text-sm font-mono font-semibold text-text-primary">
              {p.value?.toFixed(1)}
            </span>
          </div>
        );
      })}
      <div className="mt-2 pt-2 border-t border-border-subtle flex justify-between">
        <span className="text-xs text-text-tertiary">Всего</span>
        <span className="text-sm font-mono font-semibold text-text-primary">
          {total.toFixed(1)} млн
        </span>
      </div>
    </div>
  );
}

function PercentTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass-surface rounded-xl border border-border-subtle px-4 py-3 shadow-2xl min-w-[200px]">
      <p className="text-xs font-mono text-text-tertiary mb-2">{label} г.</p>
      {payload.map((p) => {
        const g = GROUPS.find(g => g.key === p.dataKey);
        return (
          <div key={p.dataKey} className="flex items-center justify-between gap-4 mb-1">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full" style={{ background: g?.color }} />
              <span className="text-xs text-text-secondary">{g?.label}</span>
            </div>
            <span className="text-sm font-mono font-semibold text-text-primary">
              {p.value?.toFixed(1)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

function StructureBar({ latest }) {
  if (!latest) return null;
  const total = GROUPS.reduce((s, g) => s + (latest[g.key] || 0), 0);
  if (!total) return null;

  return (
    <div className="space-y-5">
      <div className="flex rounded-xl overflow-hidden h-10 border border-border-subtle">
        {GROUPS.map((g, i) => {
          const pct = ((latest[g.key] || 0) / total) * 100;
          if (pct < 0.5) return null;
          return (
            <div
              key={g.key}
              className={cn(
                'flex items-center justify-center text-[11px] font-mono font-semibold transition-all',
                i > 0 && 'border-l border-white/20',
              )}
              style={{
                width: `${pct}%`,
                background: g.color,
                color: g.key === 'pop-over-working-age' ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.95)',
              }}
            >
              {pct > 10 ? `${pct.toFixed(0)}%` : ''}
            </div>
          );
        })}
      </div>
      <div className="grid grid-cols-3 gap-6">
        {GROUPS.map((g) => {
          const val = latest[g.key] || 0;
          const pct = ((val / total) * 100).toFixed(1);
          return (
            <Link
              key={g.key}
              to={`/indicator/${g.key}`}
              className="group text-center rounded-2xl p-4 -m-1 hover:bg-obsidian-lighter/60 transition-colors"
            >
              <div className="flex items-center justify-center gap-2 mb-2">
                <span className="w-2 h-2 rounded-full" style={{ background: g.color }} />
                <span className="text-[11px] text-text-tertiary uppercase tracking-wider">{g.short}</span>
              </div>
              <p className="text-2xl font-display font-bold text-text-primary tracking-tight">
                {val.toFixed(1)}
              </p>
              <p className="text-xs text-text-tertiary font-mono mt-0.5">млн чел. · {pct}%</p>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function downloadStructureCSV(series) {
  if (!series?.length) return;
  const header = ['Год', ...GROUPS.map(g => g.label), 'Всего'];
  const rows = [header.join(';')];
  for (const row of series) {
    const total = GROUPS.reduce((s, g) => s + (row[g.key] || 0), 0);
    rows.push([
      row.year,
      ...GROUPS.map(g => (row[g.key] ?? '').toString()),
      total.toFixed(2),
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
  const { data, isLoading, isError, refetch, isFetching } = useDemographicsStructure();
  const [chartType, setChartType] = useState('stacked');

  const series = data?.series || [];
  const latest = series.length > 0 ? series[series.length - 1] : null;
  const firstYear = series.length > 0 ? series[0].year : null;

  useDocumentMeta({
    title: 'Возрастная структура населения России — данные Росстата',
    description: `Возрастная структура населения России: трудоспособный возраст, дети, пожилые. Данные Росстата${firstYear ? ` с ${firstYear}` : ''} года.`,
    path: '/demographics',
  });

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 pt-20 pb-24">
      <nav className="flex items-center gap-2 text-sm text-text-tertiary mb-8" aria-label="Хлебные крошки">
        <Link
          to="/"
          className="hover:text-champagne transition-colors rounded-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-champagne/40 focus-visible:ring-offset-2 focus-visible:ring-offset-obsidian"
        >
          Главная
        </Link>
        <ChevronRight className="w-4 h-4 shrink-0 opacity-60" />
        <Link
          to="/category/population"
          className="hover:text-champagne transition-colors rounded-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-champagne/40"
        >
          Население
        </Link>
        <ChevronRight className="w-4 h-4 shrink-0 opacity-60" />
        <span className="text-text-primary font-medium">Возрастная структура</span>
      </nav>

      <header className="mb-10 max-w-3xl">
        <div className="flex items-center gap-3 mb-4">
          <Users className="w-7 h-7 text-champagne" />
          <h1 className="font-display text-3xl md:text-[2.15rem] font-bold text-text-primary tracking-tight">
            Возрастная структура населения
          </h1>
        </div>
        <p className="text-text-secondary leading-relaxed">
          Три возрастные группы по классификации Росстата: моложе трудоспособного возраста (0–15 лет),
          в трудоспособном возрасте (мужчины 16–59, женщины 16–54) и старше трудоспособного.
          {firstYear && <> Источник: данные Росстата с {firstYear} года.</>}
        </p>
      </header>

      {isError && (
        <ApiRetryBanner className="mb-6" onRetry={() => refetch()} isFetching={isFetching}>
          <span className="font-semibold">Данные о возрастной структуре недоступны.</span>{' '}
          Нажмите «Повторить» через пару секунд.
        </ApiRetryBanner>
      )}

      {isLoading && (
        <section
          aria-busy="true"
          aria-label="Загрузка структуры населения"
          className="rounded-[2rem] border border-border-subtle bg-surface p-6 shadow-md ring-1 ring-black/[0.06] md:p-8 mb-8"
        >
          <div className="flex items-center justify-between mb-6">
            <SkeletonBox className="h-3 w-44 rounded-md" />
            <SkeletonBox className="h-3 w-24 rounded-md" />
          </div>
          <SkeletonBox className="h-10 w-full rounded-xl mb-6" />
          <div className="grid grid-cols-3 gap-6">
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
        <section className="rounded-[2rem] border border-border-subtle bg-surface p-6 shadow-md ring-1 ring-black/[0.06] md:p-8 mb-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-text-primary/70">
              Структура на {latest.year} г.
            </h2>
            <span className="text-sm font-mono text-text-tertiary">
              {GROUPS.reduce((s, g) => s + (latest[g.key] || 0), 0).toFixed(1)} млн чел.
            </span>
          </div>
          <StructureBar latest={latest} />
        </section>
      )}

      <section className="rounded-[2rem] border border-border-subtle bg-surface p-6 shadow-md ring-1 ring-black/[0.06] md:p-8 mb-8">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-text-primary/70">
            {firstYear ? `Динамика с ${firstYear} года` : 'Динамика'}
          </h2>
          <div className="flex items-center gap-2">
            {['stacked', 'percent'].map((t) => (
              <button
                key={t}
                onClick={() => { setChartType(t); track(events.DEMOGRAPHICS_CHART_TYPE, { type: t }); }}
                className={cn(
                  'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                  chartType === t
                    ? 'bg-champagne/15 text-champagne'
                    : 'text-text-tertiary hover:text-text-secondary hover:bg-obsidian-lighter',
                )}
              >
                {t === 'stacked' ? 'Абсолютно' : '%'}
              </button>
            ))}
            <button
              onClick={() => downloadStructureCSV(series)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-text-tertiary hover:text-champagne hover:bg-champagne/10 transition-colors"
              title="Скачать CSV"
            >
              <Download className="w-3.5 h-3.5" />
              CSV
            </button>
          </div>
        </div>

        {isLoading ? (
          <SkeletonBox className="h-[360px] w-full rounded-2xl" />
        ) : series.length === 0 ? (
          <p className="text-text-secondary py-12 text-center">Нет данных для отображения</p>
        ) : (
          <div className="h-[360px] w-full overflow-hidden">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={chartType === 'percent' ? series.map(r => {
                  const total = GROUPS.reduce((s, g) => s + (r[g.key] || 0), 0);
                  if (!total) return r;
                  const out = { year: r.year };
                  GROUPS.forEach(g => { out[g.key] = ((r[g.key] || 0) / total) * 100; });
                  return out;
                }) : series}
                margin={{ top: 8, right: 8, left: 4, bottom: 0 }}
              >
                <defs>
                  {GROUPS.map((g) => (
                    <linearGradient key={g.key} id={`grad-${g.key}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={g.color} stopOpacity={0.35} />
                      <stop offset="100%" stopColor={g.color} stopOpacity={0.06} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid stroke="rgba(0,0,0,0.04)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="year"
                  tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.4)', fontFamily: 'JetBrains Mono, monospace' }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: 'rgba(26,26,46,0.4)', fontFamily: 'JetBrains Mono, monospace' }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={v => chartType === 'percent' ? `${v.toFixed(0)}%` : `${v.toFixed(0)}`}
                  width={44}
                  label={chartType !== 'percent' ? { value: 'млн', position: 'top', offset: -4, style: { fontSize: 10, fill: 'rgba(26,26,46,0.35)', fontFamily: 'JetBrains Mono, monospace' } } : undefined}
                />
                <Tooltip content={chartType === 'percent' ? <PercentTooltip /> : <StructureTooltip />} />
                {GROUPS.map((g) => (
                  <Area
                    key={g.key}
                    type="monotone"
                    dataKey={g.key}
                    stackId="1"
                    stroke={g.color}
                    fill={`url(#grad-${g.key})`}
                    strokeWidth={1.5}
                    animationDuration={800}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {!isLoading && series.length > 0 && (
          <div className="flex flex-wrap items-center justify-center gap-6 mt-4 pt-3 border-t border-border-subtle">
            {GROUPS.map((g) => (
              <div key={g.key} className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: g.color }} />
                <span className="text-xs text-text-tertiary">{g.label}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="flex justify-center">
        <Link
          to="/category/population"
          className="inline-flex items-center gap-2 px-6 py-3 rounded-xl border border-border-subtle bg-surface text-text-secondary hover:text-champagne hover:border-champagne/30 transition-colors text-sm font-medium shadow-sm"
        >
          Все демографические индикаторы
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}
