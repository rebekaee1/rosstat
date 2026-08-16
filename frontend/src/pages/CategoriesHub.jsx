/**
 * Хаб категорий России: /russia/category
 */
import { useEffect, useMemo } from 'react';
import { useIndicators } from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import { CATEGORIES, countInCategory } from '../lib/categories';
import CategoryBlock from '../components/CategoryBlock';
import Breadcrumbs from '../components/Breadcrumbs';
import { TileSkeleton } from '../components/Skeleton';
import ApiRetryBanner from '../components/ApiRetryBanner';
import IndicatorSearch from '../components/IndicatorSearch';
import { getPageSeo } from '../lib/pageMeta';
import { useLocale } from '../i18n';
import { russiaCategoriesTrail, breadcrumbJsonLd } from '../lib/breadcrumbs';
import { russiaCategoriesPath } from '../lib/sitePaths';

export default function CategoriesHub() {
  const { locale } = useLocale();
  const { data: indicators, isLoading, isError, refetch, isFetching } = useIndicators();
  const seo = getPageSeo('russia-categories', locale);
  const crumbs = useMemo(() => russiaCategoriesTrail(), []);

  const counts = useMemo(() => {
    const m = {};
    CATEGORIES.forEach((c) => {
      m[c.slug] = countInCategory(indicators, c.apiCategory);
    });
    return m;
  }, [indicators]);

  useDocumentMeta(seo ? {
    title: seo.title,
    description: seo.description,
    path: russiaCategoriesPath(),
  } : null);

  useEffect(() => {
    const jsonLd = breadcrumbJsonLd(crumbs);
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.id = 'breadcrumb-jsonld';
    script.textContent = JSON.stringify(jsonLd);
    document.getElementById('breadcrumb-jsonld')?.remove();
    document.head.appendChild(script);
    return () => script.remove();
  }, [crumbs]);

  return (
    <div className="mx-auto max-w-7xl overflow-x-hidden px-4 pb-28 pt-24 md:px-8">
      <Breadcrumbs items={crumbs} className="mb-8" />

      <header className="mb-10 max-w-3xl">
        <h1 className="font-display text-3xl font-bold leading-tight text-text-primary md:text-[2.15rem]">
          {seo?.h1 || 'Категории показателей России'}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-text-secondary md:text-base">
          {seo?.intro
            || 'Разделы макроэкономики России: от цен и валют до ВВП, рынка труда и демографии. Внутри каждой категории — официальные ряды с графиками и таблицами.'}
        </p>
      </header>

      <div className="mb-8">
        <IndicatorSearch
          variant="inline"
          inlinePlaceholder="Искать индикатор по всем категориям — например, инфляция или ВВП"
        />
      </div>

      {isError && (
        <ApiRetryBanner
          className="mb-6"
          onRetry={() => refetch()}
          isFetching={isFetching}
        >
          <span className="font-semibold">Данные о показателях сейчас не подгрузились.</span>{' '}
          Разделы ниже по-прежнему открываются; счётчики обновятся, когда соединение восстановится.
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
              indicatorCount={counts[cat.slug] || 0}
              delay={i * 40}
              countsKnown={!isError}
            />
          ))}
        </div>
      )}
    </div>
  );
}
