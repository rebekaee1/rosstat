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
  CircleDollarSign,
  Banknote,
  LineChart,
  Boxes,
} from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING_SURFACE } from '../lib/uiTokens';
import { track, events } from '../lib/track';
import {
  russiaCategoryPath,
} from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';

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
  CircleDollarSign,
  Banknote,
  LineChart,
  Boxes,
};

export default function CategoryBlock({
  category,
  indicatorCount = 0,
  delay = 0,
  /** false, если список индикаторов с API не загрузился — не показываем «0 показ.» */
  countsKnown = true,
}) {
  const t = useT();
  const { locale } = useLocale();
  const IconComponent = CATEGORY_ICONS[category.icon] || LayoutGrid;
  const isPlanned = category.status === 'planned' && !category.apiCategory;
  const hasData = category.apiCategory && indicatorCount > 0;
  const soon = category.apiCategory && indicatorCount === 0 && countsKnown;
  const title = locale === 'en' && category.nameEn ? category.nameEn : category.name;
  const description = locale === 'en' && category.descriptionEn
    ? category.descriptionEn
    : category.description;

  return (
    <Link
      to={category.apiCategory ? russiaCategoryPath(category.slug) : '#'}
      onClick={(e) => {
        if (!category.apiCategory) {
          e.preventDefault();
          return;
        }
        track(events.HOME_CATEGORY_CLICK, {
          category: category.slug,
          indicatorCount,
        });
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
            title={!countsKnown ? t('category.countsUnavailable') : undefined}
          >
            {!countsKnown
              ? '—'
              : hasData || soon
                ? t('category.count', { n: indicatorCount })
                : isPlanned
                  ? t('common.soonCap')
                  : ''}
          </span>
        )}
        {isPlanned && (
          <span className="text-xs font-mono text-champagne/80">{t('common.soonCap')}</span>
        )}
      </div>

      <h3 className="text-lg font-semibold text-text-primary mb-2 pr-6">{title}</h3>
      <p className="text-sm text-text-secondary leading-relaxed line-clamp-3 flex-1">{description}</p>

      <div className="mt-4 flex items-center gap-2 text-sm font-medium text-champagne opacity-0 group-hover:opacity-100 transition-opacity">
        {category.apiCategory ? (
          <>
            <span>{t('common.open')}</span>
            <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </>
        ) : (
          <span className="text-text-tertiary">{t('common.inDevelopment')}</span>
        )}
      </div>
    </Link>
  );
}
