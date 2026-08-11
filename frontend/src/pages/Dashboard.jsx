import { useMemo } from 'react';
import { useIndicators } from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import { CATEGORIES, countInCategory } from '../lib/categories';
import CategoryBlock from '../components/CategoryBlock';
import { TileSkeleton } from '../components/Skeleton';
import ApiRetryBanner from '../components/ApiRetryBanner';
import HomeHero from '../components/home/HomeHero';
import HomeRussiaToday from '../components/home/HomeRussiaToday';
import HomeWorkbench from '../components/home/HomeWorkbench';
import HomeTools from '../components/home/HomeTools';

export default function Dashboard() {
  const { data: indicators, isLoading, isError, refetch, isFetching } = useIndicators();

  const counts = useMemo(() => {
    const m = {};
    CATEGORIES.forEach((c) => {
      m[c.slug] = countInCategory(indicators, c.apiCategory);
    });
    return m;
  }, [indicators]);

  useDocumentMeta({
    title: 'Forecast Economy — экономика России, регионов и стран',
    description:
      'Официальные экономические данные России, регионов и доступных стран: графики, таблицы, сравнения и статистические прогнозы.',
    path: '/',
  });

  return (
    <div className="mx-auto max-w-7xl px-4 pb-20 pt-20 md:px-8">
      <HomeHero />
      <HomeRussiaToday indicators={indicators} isLoading={isLoading} />
      <HomeWorkbench indicators={indicators} indicatorsLoading={isLoading} />
      <HomeTools />

      <section data-block="categories">
        <div className="mb-6 flex items-center gap-4">
          <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-text-secondary">
            Категории
          </h2>
          <div className="h-px flex-1 bg-border-subtle" />
        </div>

        {isError && (
          <ApiRetryBanner
            className="mb-6"
            onRetry={() => refetch()}
            isFetching={isFetching}
          >
            <span className="font-semibold">Данные о показателях сейчас не подгрузились.</span>{' '}
            Разделы ниже по-прежнему открываются; счётчики обновятся, когда соединение с сервером восстановится.
          </ApiRetryBanner>
        )}

        {isLoading ? (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {[...Array(9)].map((_, i) => (
              <TileSkeleton key={i} />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {CATEGORIES.map((cat, i) => (
              <CategoryBlock
                key={cat.slug}
                category={cat}
                indicatorCount={counts[cat.slug] ?? 0}
                countsKnown={!isError}
                delay={i}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
