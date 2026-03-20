import { Link, useParams, Navigate } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import IndicatorTile from '../components/IndicatorTile';
import { TileSkeleton } from '../components/Skeleton';
import { getCategoryBySlug } from '../lib/categories';
import { FOCUS_RING } from '../lib/uiTokens';
import { cn } from '../lib/format';

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

      <section className="rounded-[2rem] border border-border-subtle bg-surface/80 p-6 md:p-8 shadow-sm">
        <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-6">
          Индикаторы
        </h2>
        {isError && (
          <div
            className="mb-6 flex flex-col gap-3 rounded-xl border border-champagne/25 bg-warn-surface px-4 py-3.5 text-sm text-warn-text sm:flex-row sm:items-center sm:justify-between"
            role="alert"
          >
            <p className="text-warn-muted">
              <span className="font-semibold text-text-primary">Список индикаторов сейчас недоступен.</span>{' '}
              Чуть позже всё обычно подтягивается — можно обновить попытку.
            </p>
            <button
              type="button"
              onClick={() => refetch()}
              disabled={isFetching}
              className={cn(
                FOCUS_RING,
                'shrink-0 rounded-xl border border-champagne/30 bg-surface px-4 py-2 text-sm font-medium text-champagne-muted transition-colors hover:bg-champagne/5 hover:border-champagne/45 disabled:opacity-60'
              )}
            >
              {isFetching ? 'Загрузка…' : 'Повторить'}
            </button>
          </div>
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
