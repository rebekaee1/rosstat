// Детальная страница показателя региона: /region/{slug}/{code}
// График + рейтинг среди регионов + сравнение с РФ + таблица значений +
// выгрузка CSV/Excel/PNG (только для зарегистрированных, PNG — с watermark).
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ChevronRight, Trophy, Table2, ChevronDown, ArrowUpRight,
  Download, Image as ImageIcon, GitCompare,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  useRegionIndicator, useRegionsLanding, formatRegionValue, shortUnit, yearDelta,
} from '../lib/regionsApi';
import RegionAnnualChart from '../components/RegionAnnualChart';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import { useAuth } from '../context/authContext';
import { exportTable } from '../lib/api';
import { exportNodeToPng } from '../lib/chartImage';
import { track, events } from '../lib/track';

// Годовой ряд → изменения год к году, % (кнопка «% г/г», созвон «На правки 13»).
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
    <div className="bg-surface border border-border-subtle rounded-xl p-3.5">
      <div className="text-[11px] text-text-tertiary uppercase tracking-wide">{label}</div>
      <div className="mt-1 font-mono font-semibold text-text-primary text-[15px] leading-tight">
        {children}
      </div>
    </div>
  );
}

const ABORTION_SIBLING = {
  'beremennosti-s-abortivnym-ishodom-na-100-rodov': {
    code: 'beremennosti-s-abortivnym-ishodom-na-1000-zhenschin',
    label: 'на 1000 женщин 15–49 лет',
  },
  'beremennosti-s-abortivnym-ishodom-na-1000-zhenschin': {
    code: 'beremennosti-s-abortivnym-ishodom-na-100-rodov',
    label: 'на 100 родов',
  },
};

export default function RegionIndicatorPage() {
  const { slug, code } = useParams();
  const { data, isLoading, isError, refetch, isFetching } = useRegionIndicator(slug, code);
  const [showTable, setShowTable] = useState(false);
  const [showRussia, setShowRussia] = useState(true);
  const [showYoYRaw, setShowYoY] = useState(false);
  // В-20: для знакопеременных рядов режим «% г/г» недоступен.
  const showYoY = showYoYRaw && !isNegativeCapable(data?.series);
  const [exporting, setExporting] = useState(false);
  const { isAuthed } = useAuth();
  const chartRef = useRef(null);

  // Сравнение с другим регионом: вторая линия на графике.
  const [compareSlug, setCompareSlug] = useState('');
  const landing = useRegionsLanding();
  const compare = useRegionIndicator(compareSlug || null, compareSlug ? code : null);
  const regionOptions = useMemo(() => {
    if (!landing.data) return [];
    return landing.data.districts.flatMap(d => d.regions.map(r => ({ slug: r.slug, name: r.name })))
      .filter(r => r.slug !== slug)
      .sort((a, b) => a.name.localeCompare(b.name, 'ru'));
  }, [landing.data, slug]);

  // Выгрузка данных региона — только для зарегистрированных: гостю показываем
  // гейт регистрации (то же окно, что в макроблоке). PNG — всегда с watermark.
  const requireAuth = (blockedEvent) => {
    if (isAuthed) return true;
    track(blockedEvent, { indicator: `region:${slug}:${code}` });
    window.dispatchEvent(new CustomEvent('fe:download-limit'));
    return false;
  };

  const handleExportTable = async (format) => {
    const evt = format === 'csv' ? events.DOWNLOAD_CSV : events.DOWNLOAD_EXCEL;
    if (!requireAuth(events.DOWNLOAD_LIMIT_HIT) || !data?.series?.length || exporting) return;
    setExporting(true);
    try {
      const filename = `${slug}_${code}.${format}`;
      const { blob } = await exportTable({
        format,
        filename,
        valueLabel: `${data.indicator.name} (${data.indicator.unit})`,
        points: data.series.map(p => ({ date: `${p.year}-01-01`, actual: p.value, forecast: null })),
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
      watermark: true,
    }).catch(() => false);
    setExporting(false);
    if (ok) track(events.CHART_IMAGE_DOWNLOAD, { indicator: `region:${slug}:${code}`, region: slug });
  };

  // First-party просмотр карточки: один раз на связку регион+показатель,
  // чтобы просмотры регионов попадали в «Пульс».
  const viewedRef = useRef('');
  useEffect(() => {
    if (!data?.indicator) return;
    const key = `${slug}:${code}`;
    if (viewedRef.current === key) return;
    viewedRef.current = key;
    track(events.REGION_INDICATOR_VIEW, {
      indicator: `region:${slug}:${code}`,
      region: slug,
      code,
    });
  }, [data?.indicator, slug, code]);

  const regionName = data?.region?.name;
  const indName = data?.indicator?.name;
  const last = data?.series?.[data.series.length - 1];
  const first = data?.series?.[0];

  useDocumentMeta(data ? {
    title: `${indName} — ${regionName}: ${formatRegionValue(last.value)} ${shortUnit(data.indicator.unit)} (${last.year})`,
    description:
      `${indName} в регионе ${regionName}: ${formatRegionValue(last.value)} ${data.indicator.unit} в ${last.year} году. ` +
      `Динамика с ${first.year} года по данным Росстата, график по годам` +
      (data.rank ? `, ${data.rank.position}-е место среди ${data.rank.total} регионов России.` : '.'),
    path: `/region/${slug}/${code}`,
  } : null);

  useEffect(() => {
    if (!data) return;
    const jsonLd = {
      '@context': 'https://schema.org',
      '@type': 'Dataset',
      name: `${indName} — ${regionName}`,
      description: `${indName} (${data.indicator.unit}), ${regionName}, ${first.year}–${last.year}. Источник: Росстат.`,
      temporalCoverage: `${first.year}/${last.year}`,
      spatialCoverage: regionName,
      creator: { '@type': 'Organization', name: 'Росстат' },
      publisher: { '@type': 'Organization', name: 'Forecast Economy', url: 'https://forecasteconomy.com' },
    };
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.id = 'region-dataset-jsonld';
    script.textContent = JSON.stringify(jsonLd);
    document.getElementById('region-dataset-jsonld')?.remove();
    document.head.appendChild(script);
    return () => script.remove();
  }, [data, indName, regionName, first, last]);

  const delta = last && data?.series?.length > 1
    ? yearDelta(last.value, data.series[data.series.length - 2].value)
    : null;

  const stats = useMemo(() => {
    if (!data?.series?.length) return null;
    const values = data.series.map(p => p.value);
    const max = Math.max(...values);
    const min = Math.min(...values);
    return {
      max, maxYear: data.series[values.indexOf(max)].year,
      min, minYear: data.series[values.indexOf(min)].year,
    };
  }, [data]);

  const tableRows = useMemo(
    () => (data?.series ? [...data.series].reverse() : []),
    [data],
  );

  return (
    <div className="max-w-5xl mx-auto px-4 pt-24 pb-20">
      {/* Хлебные крошки */}
      <nav className="flex items-center gap-1.5 text-xs text-text-tertiary mb-4 overflow-hidden" aria-label="Хлебные крошки">
        <Link to="/regions" className="hover:text-champagne transition-colors shrink-0">Регионы</Link>
        <ChevronRight size={12} className="shrink-0" />
        {regionName && (
          <Link to={`/region/${slug}`} className="hover:text-champagne transition-colors shrink-0 truncate max-w-[45%]">
            {regionName}
          </Link>
        )}
        <ChevronRight size={12} className="shrink-0" />
        <span className="text-text-secondary truncate">{indName || '…'}</span>
      </nav>

      {isError && <ApiRetryBanner onRetry={refetch} retrying={isFetching} />}
      {isLoading && (
        <div className="space-y-4">
          <SkeletonBox className="h-9 w-96 max-w-full" />
          <SkeletonBox className="h-72 rounded-xl" />
        </div>
      )}

      {data && (
        <>
          {/* Шапка */}
          <div className="mb-5">
            <div className="text-champagne text-xs font-mono uppercase tracking-widest mb-2">
              {data.indicator.section_name}
            </div>
            <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 mb-1">
              <h1 className="font-display text-2xl sm:text-3xl font-bold text-text-primary leading-tight flex-1 min-w-[12rem]">
                {indName}
              </h1>
              <span className="text-sm text-text-secondary shrink-0 pt-1 sm:pt-1.5">{regionName}</span>
            </div>
            {ABORTION_SIBLING[code] && (
              <p className="mt-1 text-xs text-text-tertiary">
                Другой срез того же показателя Росстата —{' '}
                <Link
                  to={`/region/${slug}/${ABORTION_SIBLING[code].code}`}
                  className="text-champagne hover:underline"
                >
                  {ABORTION_SIBLING[code].label}
                </Link>
                .
              </p>
            )}

            <div className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="font-mono text-3xl font-bold text-text-primary">
                {formatRegionValue(last.value)}
              </span>
              <span className="text-sm text-text-secondary">{data.indicator.unit}</span>
              <span className="font-mono text-sm text-text-tertiary">{last.year}</span>
              {delta && (
                <span className={`font-mono text-sm ${delta.up ? 'text-positive' : delta.down ? 'text-negative' : 'text-text-tertiary'}`}>
                  {delta.up ? '+' : ''}{delta.pct.toFixed(1).replace('.', ',')}% за год
                </span>
              )}
            </div>
          </div>

          {/* График */}
          <div data-block="region-chart" className="bg-surface border border-border-subtle rounded-xl p-4 mb-4" ref={chartRef}>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <div className="text-xs text-text-tertiary font-mono">
                {first.year}–{last.year}, {showYoY ? 'изменение к предыдущему году, %' : data.indicator.unit}
              </div>
              <div className="flex flex-wrap items-center gap-1.5" data-no-export="true">
                <label className="relative inline-flex items-center">
                  <GitCompare size={12} className="absolute left-2 text-text-tertiary pointer-events-none" />
                  <select
                    value={compareSlug}
                    onChange={(e) => {
                      setCompareSlug(e.target.value);
                      if (e.target.value) track(events.REGION_COMPARE_ADD, { region: slug, compare: e.target.value, indicator: code });
                    }}
                    aria-label="Сравнить с другим регионом"
                    className={`text-xs pl-7 pr-2 py-1 rounded-full border bg-transparent max-w-[160px] truncate transition-colors cursor-pointer focus:outline-none ${
                      compareSlug
                        ? 'border-[#5B7DA8] text-[#5B7DA8]'
                        : 'border-border-subtle text-text-tertiary hover:text-text-secondary'
                    }`}
                  >
                    <option value="">Сравнить с регионом</option>
                    {regionOptions.map(r => (
                      <option key={r.slug} value={r.slug}>{r.name}</option>
                    ))}
                  </select>
                </label>
                {data.russia_series?.length > 0 && (
                  <button
                    onClick={() => setShowRussia(v => !v)}
                    className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                      showRussia
                        ? 'border-border-champagne text-champagne bg-champagne/5'
                        : 'border-border-subtle text-text-tertiary hover:text-text-secondary'
                    }`}
                  >
                    {showRussia ? '— Россия' : '+ Россия'}
                  </button>
                )}
                {data.series.length > 2 && !isNegativeCapable(data.series) && (
                  <button
                    onClick={() => setShowYoY(v => !v)}
                    title="Изменения к предыдущему году, в процентах"
                    className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                      showYoY
                        ? 'border-border-champagne text-champagne bg-champagne/5'
                        : 'border-border-subtle text-text-tertiary hover:text-text-secondary'
                    }`}
                  >
                    % г/г
                  </button>
                )}
                <button
                  onClick={() => handleExportTable('csv')}
                  disabled={exporting}
                  title="Скачать CSV"
                  aria-label="Скачать CSV"
                  className="text-xs px-2 py-1 rounded-full border border-border-subtle text-text-tertiary hover:text-champagne hover:border-border-champagne transition-colors inline-flex items-center gap-1 disabled:opacity-50"
                >
                  <Download size={12} /> CSV
                </button>
                <button
                  onClick={() => handleExportTable('xlsx')}
                  disabled={exporting}
                  title="Скачать Excel"
                  aria-label="Скачать Excel"
                  className="text-xs px-2 py-1 rounded-full border border-border-subtle text-text-tertiary hover:text-champagne hover:border-border-champagne transition-colors inline-flex items-center gap-1 disabled:opacity-50"
                >
                  <Download size={12} /> Excel
                </button>
                <button
                  onClick={handleExportPng}
                  disabled={exporting}
                  title="Скачать график картинкой"
                  aria-label="Скачать график картинкой"
                  className="text-xs px-2 py-1 rounded-full border border-border-subtle text-text-tertiary hover:text-champagne hover:border-border-champagne transition-colors inline-flex items-center gap-1 disabled:opacity-50"
                >
                  <ImageIcon size={12} /> PNG
                </button>
              </div>
            </div>
            <RegionAnnualChart
              series={showYoY ? toYoYSeries(data.series) : data.series}
              russiaSeries={showRussia
                ? (showYoY ? toYoYSeries(data.russia_series) : data.russia_series)
                : null}
              compareSeries={compareSlug
                ? (showYoY ? toYoYSeries(compare.data?.series) : (compare.data?.series || null))
                : null}
              compareName={compareSlug ? (compare.data?.region?.name || '') : ''}
              unit={showYoY ? '% г/г' : data.indicator.unit}
              regionName={regionName}
              height={300}
            />
            {compareSlug && compare.data && (
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
                  убрать сравнение
                </button>
              </div>
            )}
          </div>

          {/* Рейтинг + статистика */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-6">
            {data.rank?.position && (
              <StatCell label={`Место в России, ${data.rank.year}`}>
                <span className="inline-flex items-center gap-1.5">
                  <Trophy size={14} className="text-champagne" />
                  {data.rank.position} из {data.rank.total}
                </span>
              </StatCell>
            )}
            {stats && (
              <>
                <StatCell label={`Максимум (${stats.maxYear})`}>
                  {formatRegionValue(stats.max)}
                </StatCell>
                <StatCell label={`Минимум (${stats.minYear})`}>
                  {formatRegionValue(stats.min)}
                </StatCell>
              </>
            )}
            <StatCell label="Период данных">
              {first.year}–{last.year}
            </StatCell>
          </div>

          {/* Верх рейтинга (В-31: не «лидеры» — для смертности/безработицы
              максимум не достижение, нейтральная формулировка) */}
          {data.rank?.top?.length > 0 && (
            <div data-block="region-rating" className="bg-surface border border-border-subtle rounded-xl p-4 mb-6">
              <h2 className="text-sm font-semibold text-text-primary mb-3">
                Наибольшие значения по регионам, {data.rank.year}
              </h2>
              <ol className="space-y-1.5">
                {data.rank.top.map((r, i) => (
                  <li key={r.slug}>
                    <Link
                      to={`/region/${r.slug}/${code}`}
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
              {data.rank.position > 5 && (
                <div className="mt-2 pt-2 border-t border-border-subtle flex items-center justify-between text-[13px] px-2">
                  <span className="flex items-center gap-2">
                    <span className="font-mono text-text-tertiary w-4 text-right">{data.rank.position}</span>
                    <span className="text-champagne font-medium">{regionName}</span>
                  </span>
                  <span className="font-mono text-text-secondary">{formatRegionValue(last.value)}</span>
                </div>
              )}
            </div>
          )}

          {/* Таблица значений */}
          <div className="bg-surface border border-border-subtle rounded-xl overflow-hidden mb-6">
            <button
              onClick={() => setShowTable(v => !v)}
              className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-surface-hover transition-colors"
              aria-expanded={showTable}
            >
              <span className="flex items-center gap-2 text-sm font-medium text-text-primary">
                <Table2 size={15} className="text-text-tertiary" />
                Таблица значений по годам
              </span>
              <ChevronDown size={16} className={`text-text-tertiary transition-transform ${showTable ? 'rotate-180' : ''}`} />
            </button>
            {showTable && (
              <div className="border-t border-border-subtle max-h-96 overflow-y-auto">
                <table className="w-full text-[13px]">
                  <thead className="sticky top-0 bg-surface">
                    <tr className="text-left text-text-tertiary">
                      <th className="px-4 py-2 font-medium">Год</th>
                      <th className="px-4 py-2 font-medium text-right">{regionName}</th>
                      {data.russia_series?.length > 0 && (
                        <th className="px-4 py-2 font-medium text-right">Россия</th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {tableRows.map(p => {
                      const rf = data.russia_series?.find(r => r.year === p.year);
                      return (
                        <tr key={p.year} className="border-t border-border-subtle">
                          <td className="px-4 py-1.5 font-mono text-text-secondary">{p.year}</td>
                          <td className="px-4 py-1.5 font-mono text-right text-text-primary">{formatRegionValue(p.value)}</td>
                          {data.russia_series?.length > 0 && (
                            <td className="px-4 py-1.5 font-mono text-right text-text-tertiary">
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

          {/* Мост в макроблок: общероссийская карточка + сравнение */}
          {data.indicator.macro_code && (
            <div className="bg-surface border border-border-champagne/40 rounded-xl p-4 mb-6">
              <h2 className="text-sm font-semibold text-text-primary mb-2">
                Показатель по России в целом
              </h2>
              <p className="text-[13px] text-text-secondary leading-relaxed mb-3">
                У этого показателя есть общероссийская карточка с более частым
                обновлением и прогнозом, а в разделе сравнения можно наложить
                регион и федеральный уровень на один график.
              </p>
              <div className="flex flex-wrap gap-2">
                <Link
                  to={`/indicator/${data.indicator.macro_code}`}
                  onClick={() => track(events.REGION_CROSSLINK_CLICK, { from: `region:${slug}:${code}`, to: data.indicator.macro_code })}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-champagne/10 text-champagne text-[13px] font-medium hover:bg-champagne/20 transition-colors"
                >
                  Открыть индикатор России <ArrowUpRight size={13} />
                </Link>
                <Link
                  to={`/compare?codes=${data.indicator.macro_code},r:${slug}:${code}`}
                  onClick={() => track(events.REGION_CROSSLINK_CLICK, { from: `region:${slug}:${code}`, to: 'compare' })}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-border-subtle text-text-secondary text-[13px] font-medium hover:text-champagne hover:border-border-champagne transition-colors"
                >
                  <GitCompare size={13} /> Сравнить с Россией
                </Link>
              </div>
            </div>
          )}

          {/* Другие показатели раздела */}
          {data.siblings?.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-text-primary mb-3">
                Ещё в разделе «{data.indicator.section_name}»
              </h2>
              <div className="flex flex-wrap gap-2">
                {data.siblings.map(s => (
                  <Link
                    key={s.code}
                    to={`/region/${slug}/${s.code}`}
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
