import { useEffect, useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Users, ArrowRight } from 'lucide-react';
import { useIndicators, useInflation } from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import IndicatorTile from '../components/IndicatorTile';
import Breadcrumbs from '../components/Breadcrumbs';
import { TileSkeleton } from '../components/Skeleton';
import { CATEGORIES, getCategoryBySlug, isIndicatorListed } from '../lib/categories';
import ApiRetryBanner from '../components/ApiRetryBanner';
import IndicatorSearch from '../components/IndicatorSearch';
import { track, events } from '../lib/track';
import useScrollDepth from '../lib/useScrollDepth';
import {
  breadcrumbJsonLd,
  russiaCategoryTrail,
} from '../lib/breadcrumbs';
import { getCategorySeo } from '../lib/pageMeta';
import { useLocale } from '../i18n';
import {
  demographicsPath,
  russiaCategoryPath,
} from '../lib/sitePaths';

const CATEGORY_FEATURES = {
  population: {
    to: demographicsPath(),
    icon: Users,
    title: 'Возрастная структура населения',
    description: 'Визуализация трёх возрастных групп: дети, трудоспособные, старше трудоспособного. Данные Росстата.',
  },
};

export default function CategoryPage() {
  const { slug } = useParams();
  const { locale } = useLocale();
  const cat = getCategoryBySlug(slug);
  const catSeo = getCategorySeo(slug, locale);

  const { data: indicators, isLoading, isError, refetch, isFetching } = useIndicators({
    category: cat?.apiCategory ?? undefined,
    includeInactive: false,
    enabled: !!cat?.apiCategory,
  });

  useDocumentMeta(cat && catSeo ? {
    title: catSeo.title,
    description: catSeo.description,
    path: russiaCategoryPath(slug),
  } : null);

  useScrollDepth({ key: `category:${slug}`, page: 'category', category: slug });

  const relatedCategories = useMemo(() => {
    if (!cat?.relatedSlugs?.length) return [];
    return cat.relatedSlugs
      .map((s) => CATEGORIES.find((c) => c.slug === s))
      .filter((c) => c && c.apiCategory);
  }, [cat]);

  const crumbs = useMemo(
    () => (cat ? russiaCategoryTrail(cat.name, slug) : null),
    [cat, slug],
  );

  useEffect(() => {
    if (!crumbs) return undefined;
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.textContent = JSON.stringify(breadcrumbJsonLd(crumbs));
    script.id = 'breadcrumb-jsonld';
    document.getElementById('breadcrumb-jsonld')?.remove();
    document.head.appendChild(script);
    return () => script.remove();
  }, [crumbs]);

  const isPricesCategory = cat?.apiCategory === 'Цены';
  const { data: cpiInflResp } = useInflation('cpi', { enabled: isPricesCategory });
  const { data: foodInflResp } = useInflation('cpi-food', { enabled: isPricesCategory });
  const { data: nonfoodInflResp } = useInflation('cpi-nonfood', { enabled: isPricesCategory });
  const { data: servicesInflResp } = useInflation('cpi-services', { enabled: isPricesCategory });

  const cpiInflationMap = useMemo(() => {
    const map = {};
    const sources = {
      cpi: cpiInflResp,
      'cpi-food': foodInflResp,
      'cpi-nonfood': nonfoodInflResp,
      'cpi-services': servicesInflResp,
    };
    for (const [code, resp] of Object.entries(sources)) {
      const a = resp?.actuals;
      if (a?.length >= 2) {
        const last = a[a.length - 1];
        const prev = a[a.length - 2];
        map[code] = { value: last.value, change: +(last.value - prev.value).toFixed(4) };
      }
    }
    return map;
  }, [cpiInflResp, foodInflResp, nonfoodInflResp, servicesInflResp]);

  if (!cat) {
    return (
      <div className="max-w-2xl mx-auto px-4 pt-32 pb-24 text-center">
        <h1 className="text-6xl font-display font-bold text-text-primary mb-4">404</h1>
        <p className="text-lg text-text-secondary mb-8">Категория не найдена</p>
        <Link to="/" className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-champagne/10 text-champagne font-medium hover:bg-champagne/20 transition-colors">
          На главную
        </Link>
      </div>
    );
  }

  if (!cat.apiCategory) {
    return (
      <div className="max-w-3xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-20 text-center">
        <p className="text-text-secondary mb-6">{cat.description}</p>
        <Link to="/" className="text-champagne hover:underline">
          На главную
        </Link>
      </div>
    );
  }

  const allIndicators = (indicators ?? []).filter(
    (i) => (i.category_ru || i.category) === cat.apiCategory,
  );
  const filtered = allIndicators.filter(isIndicatorListed);

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 pt-20 pb-24">
      <Breadcrumbs items={crumbs} className="mb-8" />

      <header className="mb-12 max-w-3xl">
        <h1 className="font-display text-3xl md:text-[2.15rem] font-bold text-text-primary tracking-tight mb-4">
          {cat.seoH1 || cat.seoTitle}
        </h1>
        <p className="text-text-secondary leading-relaxed text-[1.02rem]">{cat.description}</p>
      </header>

      {CATEGORY_FEATURES[slug] && (() => {
        const feat = CATEGORY_FEATURES[slug];
        const Icon = feat.icon;
        return (
          <Link
            to={feat.to}
            className="group flex items-center gap-5 rounded-[2rem] border border-border-champagne bg-champagne/[0.04] p-6 md:p-8 mb-8 transition-colors hover:bg-champagne/[0.07]"
          >
            <div className="shrink-0 flex items-center justify-center w-12 h-12 rounded-2xl bg-champagne/10">
              <Icon className="w-6 h-6 text-champagne" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-text-primary mb-0.5">{feat.title}</p>
              <p className="text-xs text-text-secondary leading-relaxed">{feat.description}</p>
            </div>
            <ArrowRight className="w-5 h-5 text-champagne shrink-0 opacity-60 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all" />
          </Link>
        );
      })()}

      <div className="mb-8">
        <IndicatorSearch variant="inline" inlinePlaceholder="Искать индикатор по всем категориям — например, инфляция или ВВП" />
      </div>

      <section data-block="category-list" className="rounded-[2rem] border border-border-subtle bg-surface p-3 shadow-md ring-1 ring-black/[0.06] sm:p-6 md:p-8">
        <h2 className="mb-6 text-xs font-semibold uppercase tracking-[0.2em] text-text-primary/70">
          Индикаторы
        </h2>
        {isError && (
          <ApiRetryBanner
            className="mb-6"
            onRetry={() => refetch()}
            isFetching={isFetching}
          >
            <span className="font-semibold">Список индикаторов сейчас недоступен.</span>{' '}
            Чуть позже данные обычно подтягиваются — нажмите «Повторить».
          </ApiRetryBanner>
        )}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[...Array(4)].map((_, i) => (
              <TileSkeleton key={i} />
            ))}
          </div>
        ) : isError ? null : filtered.length === 0 ? (
          <p className="text-text-secondary">В этой категории пока нет показателей в базе.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filtered.map((ind, i) => (
              <IndicatorTile
                key={ind.code}
                indicator={ind}
                delay={i}
                displayOverride={cpiInflationMap[ind.code]}
                surface="category"
              />
            ))}
          </div>
        )}
      </section>

      {relatedCategories.length > 0 && (
        <section data-block="related-categories" className="mt-12">
          <div className="flex items-center gap-4 mb-6">
            <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold">
              Связанные категории
            </h2>
            <div className="h-[1px] flex-1 bg-border-subtle" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {relatedCategories.map((rel) => (
              <Link
                key={rel.slug}
                to={russiaCategoryPath(rel.slug)}
                onClick={() => track(events.RELATED_LINK_CLICK, {
                  from: slug,
                  to: rel.slug,
                  surface: 'category-related',
                })}
                className="group flex items-center justify-between gap-4 p-5 rounded-2xl border border-border-subtle bg-surface hover:border-champagne/30 transition-colors"
              >
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-text-primary mb-1 truncate">
                    {rel.name}
                  </p>
                  <p className="text-xs text-text-tertiary line-clamp-2 leading-relaxed">
                    {rel.description}
                  </p>
                </div>
                <ArrowRight className="w-4 h-4 text-text-tertiary shrink-0 group-hover:text-champagne group-hover:translate-x-0.5 transition-all" />
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
