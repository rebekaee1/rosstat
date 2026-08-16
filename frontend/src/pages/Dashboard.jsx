import { useEffect, useMemo } from 'react';
import { useIndicators } from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { CATEGORIES, countInCategory } from '../lib/categories';
import CategoryBlock from '../components/CategoryBlock';
import { TileSkeleton } from '../components/Skeleton';
import ApiRetryBanner from '../components/ApiRetryBanner';
import HomeHero from '../components/home/HomeHero';
import HomeWorkbench from '../components/home/HomeWorkbench';
import HomeTools from '../components/home/HomeTools';
import { useLocale, useT } from '../i18n';

export default function Dashboard() {
  const t = useT();
  const { locale } = useLocale();
  const { data: indicators, isLoading, isError, refetch, isFetching } = useIndicators();

  const counts = useMemo(() => {
    const m = {};
    CATEGORIES.forEach((c) => {
      m[c.slug] = countInCategory(indicators, c.apiCategory);
    });
    return m;
  }, [indicators]);

  const homeSeo = getPageSeo('home', locale);
  useDocumentMeta({
    title: homeSeo.title,
    description: homeSeo.description,
    path: homeSeo.path,
  });

  useEffect(() => {
    if (window.location.hash !== '#russia-categories') return undefined;
    const t = window.setTimeout(() => {
      document.getElementById('russia-categories')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
    return () => window.clearTimeout(t);
  }, []);

  return (
    <div className="mx-auto max-w-7xl overflow-x-hidden px-4 pb-28 pt-24 md:px-8">
      <HomeHero indicators={indicators} isLoading={isLoading} />
      <HomeWorkbench indicators={indicators} />
      <HomeTools />

      <section
        id="russia-categories"
        data-block="categories"
        className="scroll-mt-28"
        aria-labelledby="russia-categories-title"
      >
        <div className="mb-6 flex flex-wrap items-end gap-x-4 gap-y-2">
          <div className="min-w-0">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
              {t('home.categories.eyebrow')}
            </div>
            <h2
              id="russia-categories-title"
              className="mt-1 text-xs font-semibold uppercase tracking-[0.2em] text-text-secondary"
            >
              {t('home.categories.title')}
            </h2>
          </div>
          <div className="mb-1.5 h-px min-w-[4rem] flex-1 bg-border-subtle" />
        </div>

        {isError && (
          <ApiRetryBanner
            className="mb-6"
            onRetry={() => refetch()}
            isFetching={isFetching}
          >
            <span className="font-semibold">{t('home.categories.errorTitle')}</span>{' '}
            {t('home.categories.errorBody')}
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
