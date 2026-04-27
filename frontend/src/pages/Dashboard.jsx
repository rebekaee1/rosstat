import { useMemo } from 'react';
import { useIndicators } from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import { CATEGORIES, countInCategory } from '../lib/categories';
import CategoryBlock from '../components/CategoryBlock';
import { TileSkeleton } from '../components/Skeleton';
import ApiRetryBanner from '../components/ApiRetryBanner';

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
    title: 'Прогноз инфляции и экономические данные России — бесплатно',
    description:
      'Forecast Economy — бесплатная аналитическая платформа экономических данных России. ' +
      'Официальные данные Росстата и ЦБ, индекс потребительских цен (ИПЦ), прогноз. Без регистрации.',
    path: '/',
  });

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 pt-20 pb-20">
      <header className="mb-10 md:mb-12">
        <p className="text-[10px] uppercase tracking-[0.3em] text-champagne font-semibold mb-3">
          Бесплатная аналитическая платформа экономических данных России
        </p>
        <h1 className="text-xl md:text-2xl font-semibold text-text-primary tracking-tight leading-snug max-w-4xl">
          Анализируйте и скачивайте прогнозы и фактические данные по 100+ макроэкономическим индикаторам Российской Федерации
        </h1>
      </header>

      <section>
        <div className="flex items-center gap-4 mb-6">
          <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold">
            Категории
          </h2>
          <div className="h-[1px] flex-1 bg-border-subtle" />
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
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {[...Array(9)].map((_, i) => (
              <TileSkeleton key={i} />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
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
