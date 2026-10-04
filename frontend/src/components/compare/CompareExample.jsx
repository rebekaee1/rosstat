// Готовый пример на пустой странице «Сравнения»: «Германия и Франция — безработица».
// Данные настоящие (официальные ряды каталога), линии «рисуются» один раз слева направо;
// по кнопке пример становится рабочим сравнением, которое можно менять.
import { useMemo } from 'react';
import { useQueries } from '@tanstack/react-query';
import { ArrowRight, RefreshCw } from 'lucide-react';
import Button from '../Button';
import { SkeletonBox } from '../Skeleton';
import { fetchWorldCompareOrCard } from '../../lib/worldApi';
import { formatValueWithUnit } from '../../lib/format';
import { CHART_THEME } from '../../lib/chartTheme';
import { flagForSlug } from '../../lib/slugFlags';
import { useLocale } from '../../i18n';
import '../../styles/regions-w4.css';

const EXAMPLE_COUNTRIES = ['germany', 'france'];
const EXAMPLE_CONCEPT = 'unemployment-rate';
const EXAMPLE_CODES = EXAMPLE_COUNTRIES.map((slug) => `w:${slug}:${EXAMPLE_CONCEPT}`);

const W = 320;
const H = 150;
const PAD = { top: 10, right: 10, bottom: 22, left: 34 };
const MAX_POINTS = 72;

function lastYears(rows, years = 10) {
  const valid = (rows || []).filter((p) => p?.date && Number.isFinite(Number(p.value)));
  if (!valid.length) return [];
  const end = new Date(valid[valid.length - 1].date);
  end.setUTCFullYear(end.getUTCFullYear() - years);
  const cutoff = end.toISOString().slice(0, 10);
  const part = valid.filter((p) => p.date >= cutoff);
  const step = Math.max(1, Math.ceil(part.length / MAX_POINTS));
  const thinned = part.filter((_, i) => i % step === 0);
  const tail = part[part.length - 1];
  if (thinned[thinned.length - 1] !== tail) thinned.push(tail);
  return thinned.map((p) => ({ t: new Date(p.date).getTime(), v: Number(p.value), date: p.date }));
}

function niceRange(values) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = (max - min || 1) * 0.12;
  return [Math.max(0, min - pad), max + pad];
}

export default function CompareExample({ onOpen }) {
  const { locale, t } = useLocale();
  const results = useQueries({
    queries: EXAMPLE_COUNTRIES.map((slug) => ({
      queryKey: ['compare-example', slug, EXAMPLE_CONCEPT],
      queryFn: ({ signal }) => fetchWorldCompareOrCard(slug, EXAMPLE_CONCEPT, { signal }),
      retry: false,
      staleTime: 60 * 60 * 1000,
    })),
  });
  const loading = results.some((r) => r.isLoading);
  const failed = results.some((r) => r.isError);
  const ready = results.every((r) => r.data);

  const lines = useMemo(() => {
    if (!ready) return [];
    return results.map((r, i) => {
      const meta = r.data.meta || {};
      const name = locale === 'en' ? (meta.country_name_en || meta.country_name) : meta.country_name;
      return {
        slug: EXAMPLE_COUNTRIES[i],
        name: name || EXAMPLE_COUNTRIES[i],
        unit: meta.unit || '%',
        color: CHART_THEME.series[i % CHART_THEME.series.length],
        points: lastYears(r.data.data),
      };
    });
  // results — новый массив на каждый рендер; зависим от готовности и данных.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, results[0]?.data, results[1]?.data, locale]);

  const geometry = useMemo(() => {
    const all = lines.flatMap((l) => l.points);
    if (all.length < 4) return null;
    const [yMin, yMax] = niceRange(all.map((p) => p.v));
    const tMin = Math.min(...all.map((p) => p.t));
    const tMax = Math.max(...all.map((p) => p.t));
    const x = (tt) => PAD.left + ((tt - tMin) / (tMax - tMin || 1)) * (W - PAD.left - PAD.right);
    const y = (v) => PAD.top + (1 - (v - yMin) / (yMax - yMin || 1)) * (H - PAD.top - PAD.bottom);
    const paths = lines.map((l) => l.points.map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)} ${y(p.v).toFixed(1)}`).join(' '));
    const ticks = [yMin, (yMin + yMax) / 2, yMax].map((v) => ({ v, y: y(v) }));
    return { paths, ticks, fromYear: new Date(tMin).getUTCFullYear(), toYear: new Date(tMax).getUTCFullYear(), x, y };
  }, [lines]);

  const title = t('w4.compare.example.title');

  if (loading) {
    return (
      <div role="status" aria-busy="true" className="fe-panel mt-4 rounded-3xl border border-border-subtle bg-surface p-4 text-left sm:p-5" data-testid="compare-example-skeleton">
        <span className="sr-only">{t('compare.loadingSeries')}</span>
        <SkeletonBox className="mb-3 h-5 w-2/3" />
        <SkeletonBox className="h-[150px] w-full rounded-2xl" />
        <SkeletonBox className="mt-3 h-11 w-full rounded-xl" />
      </div>
    );
  }

  if (failed || !geometry) {
    return (
      <div className="mt-4 rounded-3xl border border-dashed border-border-subtle bg-surface p-5 text-center" data-testid="compare-example-error">
        <p className="text-sm text-text-secondary">{t('w4.compare.example.error')}</p>
        <Button
          variant="secondary"
          size="sm"
          className="mt-3"
          onClick={() => results.forEach((r) => r.refetch())}
        >
          <RefreshCw size={14} aria-hidden="true" />
          {t('common.retry')}
        </Button>
      </div>
    );
  }

  return (
    <section
      className="fe-panel fe-reveal mt-4 rounded-3xl border border-border-subtle bg-surface p-4 text-left sm:p-5"
      aria-label={title}
      data-testid="compare-example"
    >
      <h3 className="font-display text-lg font-bold leading-snug text-text-primary">{title}</h3>
      <p className="mt-0.5 text-sm text-text-secondary">
        {t('w4.compare.example.sub', { from: geometry.fromYear, to: geometry.toYear })}
      </p>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="mt-3 h-auto w-full"
        role="img"
        aria-label={t('w4.compare.example.aria', { a: lines[0].name, b: lines[1].name })}
      >
        {geometry.ticks.map((tick) => (
          <g key={tick.v}>
            <line x1={PAD.left} x2={W - PAD.right} y1={tick.y} y2={tick.y} stroke={CHART_THEME.grid || 'rgba(68,87,115,0.14)'} strokeWidth="1" />
            <text x={PAD.left - 6} y={tick.y + 3.5} textAnchor="end" fontSize="11" fill={CHART_THEME.axis}>
              {Math.round(tick.v * 10) / 10}
            </text>
          </g>
        ))}
        <text x={PAD.left} y={H - 5} fontSize="11" fill={CHART_THEME.axis}>{geometry.fromYear}</text>
        <text x={W - PAD.right} y={H - 5} fontSize="11" textAnchor="end" fill={CHART_THEME.axis}>{geometry.toYear}</text>
        {lines.map((line, i) => (
          <path
            key={line.slug}
            d={geometry.paths[i]}
            pathLength="1"
            fill="none"
            stroke={line.color}
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={i ? 'fe-draw-line fe-draw-line--late' : 'fe-draw-line'}
          />
        ))}
      </svg>

      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1.5">
        {lines.map((line) => {
          const last = line.points[line.points.length - 1];
          return (
            <li key={line.slug} className="flex items-center gap-2 text-sm text-text-primary">
              <span className="h-[3px] w-4 shrink-0 rounded-full" style={{ backgroundColor: line.color }} aria-hidden="true" />
              <span aria-hidden="true">{flagForSlug(line.slug)}</span>
              <span>{line.name}</span>
              <span className="fe-num whitespace-nowrap font-semibold">{formatValueWithUnit(last.v, line.unit)}</span>
            </li>
          );
        })}
      </ul>

      <Button variant="primary" className="mt-4 w-full sm:w-auto" onClick={() => onOpen(EXAMPLE_CODES)}>
        {t('w4.compare.example.open')}
        <ArrowRight size={16} aria-hidden="true" />
      </Button>
    </section>
  );
}
