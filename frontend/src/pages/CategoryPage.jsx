import { Link, useParams, Navigate } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import IndicatorTile from '../components/IndicatorTile';
import { TileSkeleton } from '../components/Skeleton';
import { getCategoryBySlug } from '../lib/categories';

export default function CategoryPage() {
  const { slug } = useParams();
  const cat = getCategoryBySlug(slug);

  const { data: indicators, isLoading } = useIndicators({
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
      <div className="max-w-3xl mx-auto px-4 pt-32 pb-20 text-center">
        <p className="text-text-secondary mb-6">{cat.description}</p>
        <Link to="/" className="text-champagne hover:underline">
          На главную
        </Link>
      </div>
    );
  }

  const filtered = (indicators ?? []).filter((i) => i.category === cat.apiCategory);

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 pt-24 pb-20">
      <nav className="flex items-center gap-2 text-sm text-text-tertiary mb-8">
        <Link to="/" className="hover:text-champagne transition-colors">
          Главная
        </Link>
        <ChevronRight className="w-4 h-4" />
        <span className="text-text-primary">{cat.name}</span>
      </nav>

      <header className="mb-10 max-w-3xl">
        <h1 className="text-3xl md:text-4xl font-bold text-text-primary mb-4">{cat.name}</h1>
        <p className="text-text-secondary leading-relaxed">{cat.description}</p>
      </header>

      <section>
        <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-6">
          Индикаторы
        </h2>
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[...Array(4)].map((_, i) => (
              <TileSkeleton key={i} />
            ))}
          </div>
        ) : filtered.length === 0 ? (
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
