import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { MapPin, ArrowRight } from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import { CATEGORIES, countInCategory } from '../lib/categories';
import CategoryBlock from '../components/CategoryBlock';
import { TileSkeleton } from '../components/Skeleton';
import ApiRetryBanner from '../components/ApiRetryBanner';
import IndicatorSearch from '../components/IndicatorSearch';

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
    title: 'Forecast Economy — экономические данные и прогнозы по России',
    description:
      'Бесплатная аналитическая платформа: ВВП, цены, ставка ЦБ, курсы валют, рынок труда, население и торговля — официальные данные России с прогнозами.',
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

      {/* Вход в региональный блок — отдельное представление платформы */}
      <Link
        to="/regions"
        className="group flex items-center justify-between gap-4 mb-10 md:mb-12 rounded-2xl border border-border-champagne bg-gradient-to-r from-champagne/8 to-transparent px-5 py-4 md:px-6 md:py-5 hover:from-champagne/14 transition-all"
      >
        <div className="flex items-start gap-3.5 min-w-0">
          <div className="shrink-0 mt-0.5 w-9 h-9 rounded-xl bg-champagne/15 flex items-center justify-center">
            <MapPin size={17} className="text-champagne" />
          </div>
          <div className="min-w-0">
            <div className="font-semibold text-text-primary text-[15px] md:text-base group-hover:text-champagne transition-colors">
              Регионы России
            </div>
            <div className="mt-0.5 text-[13px] text-text-secondary leading-snug">
              Статистика всех 85 субъектов РФ: население, зарплаты, ВРП, цены — 450+ показателей с 1990 года
            </div>
          </div>
        </div>
        <ArrowRight size={18} className="shrink-0 text-text-tertiary group-hover:text-champagne group-hover:translate-x-0.5 transition-all" />
      </Link>

      <section>
        <div className="flex items-center gap-4 mb-6">
          <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold">
            Категории
          </h2>
          <div className="h-[1px] flex-1 bg-border-subtle" />
        </div>

        <div className="mb-8">
          <IndicatorSearch variant="inline" />
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
