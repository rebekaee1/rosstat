import { useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ChevronRight, Users, ArrowRight } from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import IndicatorTile from '../components/IndicatorTile';
import { TileSkeleton } from '../components/Skeleton';
import { getCategoryBySlug } from '../lib/categories';
import ApiRetryBanner from '../components/ApiRetryBanner';

const CATEGORY_FEATURES = {
  population: {
    to: '/demographics',
    icon: Users,
    title: 'Возрастная структура населения',
    description: 'Визуализация трёх возрастных групп: дети, трудоспособные, старше трудоспособного. Данные Росстата.',
  },
};

export default function CategoryPage() {
  const { slug } = useParams();
  const cat = getCategoryBySlug(slug);

  const { data: indicators, isLoading, isError, refetch, isFetching } = useIndicators({
    category: cat?.apiCategory ?? undefined,
    includeInactive: false,
    enabled: !!cat?.apiCategory,
  });

  useDocumentMeta({
    title: cat ? `${cat.name} — индикаторы и данные` : 'Категория',
    description: cat ? `${cat.description} Бесплатно, официальные источники.` : '',
    path: `/category/${slug || ''}`,
  });

  useEffect(() => {
    if (!cat) return;
    const jsonLd = {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Главная', item: 'https://forecasteconomy.com/' },
        { '@type': 'ListItem', position: 2, name: cat.name, item: `https://forecasteconomy.com/category/${slug}` },
      ],
    };
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.textContent = JSON.stringify(jsonLd);
    script.id = 'breadcrumb-jsonld';
    const old = document.getElementById('breadcrumb-jsonld');
    if (old) old.remove();
    document.head.appendChild(script);
    return () => script.remove();
  }, [cat, slug]);

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

  const HIDDEN_CODES = new Set(['inflation-annual', 'inflation-quarterly', 'inflation-weekly']);
  const allIndicators = (indicators ?? []).filter((i) => i.category === cat.apiCategory);
  const annualInflation = allIndicators.find((i) => i.code === 'inflation-annual');
  const filtered = allIndicators.filter((i) => !HIDDEN_CODES.has(i.code));

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 pt-20 pb-24">
      <nav
        className="flex items-center gap-2 text-sm text-text-tertiary mb-8"
        aria-label="Хлебные крошки"
      >
        <Link
          to="/"
          className="hover:text-champagne transition-colors rounded-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-champagne/40 focus-visible:ring-offset-2 focus-visible:ring-offset-obsidian"
        >
          Главная
        </Link>
        <ChevronRight className="w-4 h-4 shrink-0 opacity-60" />
        <span className="text-text-primary font-medium">{cat.name}</span>
      </nav>

      <header className="mb-12 max-w-3xl">
        <h1 className="font-display text-3xl md:text-[2.15rem] font-bold text-text-primary tracking-tight mb-4">
          {cat.name}
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

      <section className="rounded-[2rem] border border-border-subtle bg-surface p-6 shadow-md ring-1 ring-black/[0.06] md:p-8">
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
                displayOverride={
                  ind.code === 'cpi' && annualInflation
                    ? { value: annualInflation.current_value, change: annualInflation.change }
                    : undefined
                }
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
