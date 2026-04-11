import { Link } from 'react-router-dom';
import {
  ArrowRight,
  TrendingUp,
  Percent,
  Wallet,
  Users,
  Landmark,
  UserCircle,
  Globe,
  Factory,
  GraduationCap,
  LayoutGrid,
  ShoppingCart,
  Briefcase,
  BarChart3,
} from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING_SURFACE } from '../lib/uiTokens';
import Sparkline, { SparklineSkeleton } from './Sparkline';

const CATEGORY_ICONS = {
  TrendingUp,
  Percent,
  Wallet,
  Users,
  Landmark,
  UserCircle,
  Globe,
  Factory,
  GraduationCap,
  ShoppingCart,
  Briefcase,
  BarChart3,
};

export default function CategoryBlock({
  category,
  indicatorCount = 0,
  delay = 0,
  countsKnown = true,
  sparkline = null,
  sparklineLoading = false,
}) {
  const IconComponent = CATEGORY_ICONS[category.icon] || LayoutGrid;
  const isPlanned = category.status === 'planned' && !category.apiCategory;
  const hasData = category.apiCategory && indicatorCount > 0;
  const soon = category.apiCategory && indicatorCount === 0 && countsKnown;

  const hasSparkline = sparkline?.points?.length >= 2;

  return (
    <Link
      to={category.apiCategory ? `/category/${category.slug}` : '#'}
      onClick={(e) => {
        if (!category.apiCategory) e.preventDefault();
      }}
      style={{ animationDelay: `${delay * 50}ms` }}
      className={cn(
        FOCUS_RING_SURFACE,
        'group relative flex flex-col p-6 rounded-[2rem] border transition-all duration-500 overflow-hidden',
        'bg-surface border-border-subtle',
        category.apiCategory && 'hover:border-champagne/30 lift-hover cursor-pointer',
        !category.apiCategory && 'opacity-50 cursor-not-allowed',
        soon && 'opacity-70'
      )}
    >
      <div className="flex items-start justify-between gap-4 mb-4">
        <div
          className={cn(
            'p-3 rounded-2xl',
            hasData ? 'bg-champagne/10 text-champagne' : 'bg-obsidian-lighter text-text-tertiary'
          )}
        >
          <IconComponent className="w-6 h-6" strokeWidth={1.5} />
        </div>
        {category.apiCategory && (
          <span
            className="text-xs font-mono text-text-tertiary"
            title={!countsKnown ? 'Число показателей не обновилось — нет ответа от сервера данных' : undefined}
          >
            {!countsKnown
              ? '—'
              : hasData || soon
                ? `${indicatorCount} показ.`
                : isPlanned
                  ? 'Скоро'
                  : ''}
          </span>
        )}
        {isPlanned && <span className="text-xs font-mono text-champagne/80">Скоро</span>}
      </div>

      <h3 className="text-lg font-semibold text-text-primary mb-2 pr-6">{category.name}</h3>
      <p className="text-sm text-text-secondary leading-relaxed line-clamp-2 flex-1">{category.description}</p>

      {/* Sparkline — visual trend hint, no numbers */}
      {sparklineLoading && !sparkline && (
        <div className="mt-3">
          <SparklineSkeleton height={32} />
        </div>
      )}
      {hasSparkline && (
        <div className="mt-3">
          <Sparkline
            points={sparkline.points}
            trend={sparkline.trend}
            sentiment={category.sentiment || 'positive'}
            height={32}
            staggerMs={delay * 80}
          />
        </div>
      )}

      <div className="mt-4 flex items-center gap-2 text-sm font-medium text-champagne opacity-0 group-hover:opacity-100 transition-opacity">
        {category.apiCategory ? (
          <>
            <span>Открыть</span>
            <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </>
        ) : (
          <span className="text-text-tertiary">В разработке</span>
        )}
      </div>
    </Link>
  );
}
