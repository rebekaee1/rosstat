import { useMemo } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { ChevronRight, Trophy } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useRegionsHeatmap, formatRegionValue, shortUnit } from '../lib/regionsApi';
import RegionsMap from '../components/RegionsMap';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';

export default function RegionRatingPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch, isFetching } = useRegionsHeatmap(code);

  const ranked = useMemo(() => {
    if (!data?.values?.length) return [];
    return [...data.values]
      .sort((a, b) => (b.raw ?? b.value) - (a.raw ?? a.value))
      .map((row, i) => ({ ...row, rank: i + 1 }));
  }, [data]);

  const top = ranked[0];
  const bottom = ranked[ranked.length - 1];
  const mapValues = useMemo(() => {
    if (!data?.values) return null;
    return new Map(data.values.map((v) => [v.slug, v.raw ?? v.value]));
  }, [data]);
  const nameBySlug = useMemo(() => {
    if (!data?.values) return {};
    return Object.fromEntries(data.values.map((v) => [v.slug, v.name]));
  }, [data]);

  useDocumentMeta(data ? {
    title: `Рейтинг регионов России: ${data.indicator.name} (${data.year})`,
    description:
      `${data.indicator.name} по регионам России за ${data.year} год: рейтинг всех `
      + `${ranked.length} субъектов РФ.`
      + (top ? ` Лидер — ${top.name}.` : '')
      + ' Полная таблица, данные Росстата.',
    path: `/region-rating/${code}`,
  } : null);

  return (
    <div className="max-w-5xl mx-auto px-4 pt-24 pb-20">
      <nav className="flex items-center gap-1.5 text-xs text-text-tertiary mb-4 overflow-hidden" aria-label="Хлебные крошки">
        <Link to="/" className="hover:text-champagne transition-colors shrink-0">Главная</Link>
        <ChevronRight size={12} className="shrink-0" />
        <Link to="/regions" className="hover:text-champagne transition-colors shrink-0">Регионы</Link>
        <ChevronRight size={12} className="shrink-0" />
        <span className="text-text-secondary truncate">Рейтинг: {data?.indicator?.name || '…'}</span>
      </nav>

      {isError && <ApiRetryBanner onRetry={refetch} retrying={isFetching} />}

      {isLoading && (
        <div className="space-y-4">
          <SkeletonBox className="h-10 w-96 max-w-full" />
          <SkeletonBox className="h-64 rounded-xl" />
        </div>
      )}

      {data && ranked.length >= 10 && (
        <>
          <p className="text-champagne text-xs font-mono uppercase tracking-widest mb-2">
            Рейтинг регионов · {data.year} год
          </p>
          <h1 className="font-display text-2xl sm:text-3xl font-bold text-text-primary mb-3">
            {data.indicator.name}: рейтинг регионов России
          </h1>
          <p className="text-text-secondary mb-6 max-w-3xl">
            Рейтинг {ranked.length} субъектов Российской Федерации по показателю «{data.indicator.name}»
            за {data.year} год. Лидирует {top.name} — {formatRegionValue(top.raw ?? top.value)}{' '}
            {shortUnit(data.indicator.unit)}.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-8">
            <div className="bg-surface border border-border-subtle rounded-xl p-3.5">
              <div className="text-[11px] text-text-tertiary uppercase tracking-wide flex items-center gap-1">
                <Trophy size={12} className="text-champagne" /> Лидер
              </div>
              <div className="mt-1 font-semibold text-text-primary">{top.name}</div>
              <div className="font-mono text-sm text-text-secondary">
                {formatRegionValue(top.raw ?? top.value)} {shortUnit(data.indicator.unit)}
              </div>
            </div>
            <div className="bg-surface border border-border-subtle rounded-xl p-3.5">
              <div className="text-[11px] text-text-tertiary uppercase tracking-wide">Минимум</div>
              <div className="mt-1 font-semibold text-text-primary">{bottom.name}</div>
              <div className="font-mono text-sm text-text-secondary">
                {formatRegionValue(bottom.raw ?? bottom.value)} {shortUnit(data.indicator.unit)}
              </div>
            </div>
            <div className="bg-surface border border-border-subtle rounded-xl p-3.5">
              <div className="text-[11px] text-text-tertiary uppercase tracking-wide">Данные за</div>
              <div className="mt-1 font-mono font-semibold text-text-primary">{data.year} год</div>
            </div>
          </div>

          <div className="bg-surface border border-border-subtle rounded-xl p-4 mb-8">
            <RegionsMap
              valuesBySlug={mapValues}
              unit={data.indicator.unit}
              nameBySlug={nameBySlug}
              onSelect={(slug) => navigate(`/region/${slug}/${code}`)}
            />
          </div>

          <section className="mb-8">
            <h2 className="font-display text-lg font-semibold text-text-primary mb-3">
              Полный рейтинг ({ranked.length} регионов)
            </h2>
            <div className="overflow-x-auto rounded-xl border border-border-subtle max-h-[32rem]">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-obsidian-light/95 backdrop-blur-sm z-10">
                  <tr className="text-left text-[11px] uppercase tracking-wide text-text-tertiary">
                    <th className="px-4 py-2.5 font-medium w-16">Место</th>
                    <th className="px-4 py-2.5 font-medium">Регион</th>
                    <th className="px-4 py-2.5 font-medium text-right">{data.indicator.unit || 'Значение'}</th>
                  </tr>
                </thead>
                <tbody>
                  {ranked.map((row) => (
                    <tr key={row.slug} className="border-t border-border-subtle hover:bg-surface-hover">
                      <td className="px-4 py-2 font-mono text-text-tertiary">{row.rank}</td>
                      <td className="px-4 py-2">
                        <Link
                          to={`/region/${row.slug}/${code}`}
                          className="text-text-primary hover:text-champagne transition-colors"
                        >
                          {row.name}
                        </Link>
                      </td>
                      <td className="px-4 py-2 text-right font-mono text-text-primary">
                        {formatRegionValue(row.raw ?? row.value)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="bg-surface border border-border-subtle rounded-xl p-5">
            <h2 className="font-display text-base font-semibold text-text-primary mb-2">Источник данных</h2>
            <p className="text-sm text-text-secondary">
              Сборник Росстата «Регионы России. Социально-экономические показатели».
              Значения за {data.year} год. По каждому региону — страница с полной динамикой с 1990 года.
            </p>
          </section>
        </>
      )}

      {!isLoading && !isError && data && ranked.length < 10 && (
        <p className="text-text-secondary">Недостаточно данных для рейтинга по этому показателю.</p>
      )}
    </div>
  );
}
