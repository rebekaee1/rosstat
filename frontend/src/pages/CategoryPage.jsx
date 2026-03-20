import { Link, useParams, Navigate } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import IndicatorTile from '../components/IndicatorTile';
import { TileSkeleton } from '../components/Skeleton';
import { getCategoryBySlug } from '../lib/categories';
import ApiRetryBanner from '../components/ApiRetryBanner';

export default function CategoryPage() {
  const { slug } = useParams();
  const cat = getCategoryBySlug(slug);

  const { data: indicators, isLoading, isError, refetch, isFetching } = useIndicators({
    category: cat?.apiCategory ?? undefined,
    includeInactive: true,
    enabled: !!cat?.apiCategory,
  });

  useDocumentMeta({
    title: cat ? `${cat.name} — индикаторы и данные` : 'Категория',
    description: cat ? `${cat.description} Бесплатно, официальные источники.` : '',
    path: `/category/${slug || ''}`,
  });

  if (!cat) {
    return <Navigate to="/" replace />;
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

  const filtered = (indicators ?? []).filter((i) => i.category === cat.apiCategory);

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
              <IndicatorTile key={ind.code} indicator={ind} delay={i} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
