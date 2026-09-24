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

// Shared approved illustrations. They describe a topic, never a data value.
const CATEGORY_ART = {
  prices: 'commodity', rates: 'finance', currencies: 'finance', finance: 'finance',
  indices: 'forecast-glass', commodities: 'commodity', labor: 'population',
  gdp: 'industry', population: 'population', trade: 'trade',
  business: 'industry', science: 'science',
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
        'fe-panel fe-category-card group relative flex flex-col p-6 rounded-[1.5rem] border overflow-hidden',
        category.apiCategory && 'hover:border-champagne/30 lift-hover cursor-pointer',
        !category.apiCategory && 'opacity-50 cursor-not-allowed',
        soon && 'opacity-70'
      )}
    >
      {CATEGORY_ART[category.slug] && (
        <img
          className="fe-category-art"
          src={`/art/quicklinks/${CATEGORY_ART[category.slug]}-320.webp`}
          alt=""
          width="320"
          height="213"
          loading="lazy"
          decoding="async"
          aria-hidden="true"
        />
      )}
      <div className="flex items-start justify-between gap-4 mb-8">
        <div
          className={cn(
            'fe-category-icon p-3 rounded-2xl',
            hasData ? 'text-champagne' : 'text-text-tertiary'
          )}
        >
          <IconComponent className="w-6 h-6" strokeWidth={1.5} />
        </div>
        {category.apiCategory && (
          <span
            className="rounded-full border border-border-subtle bg-surface/90 px-2.5 py-1 text-[10px] font-medium text-text-secondary"
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

      <h3 className="text-xl font-semibold tracking-tight text-text-primary mb-2 pr-4">{title}</h3>
      <p className="text-sm text-text-secondary leading-relaxed line-clamp-3 flex-1">{description}</p>

      <div className="mt-5 flex items-center gap-2 text-xs font-semibold text-text-secondary group-hover:text-champagne transition-colors">
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
