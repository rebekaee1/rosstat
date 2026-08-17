/**
 * Карточка страны /russia (ADR-0013).
 * Главная `/` остаётся витриной платформы; здесь — вход в российский контур.
 */
import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, CalendarDays, MapPinned, Users } from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { useLocale, useT } from '../i18n';
import { CATEGORIES, countInCategory } from '../lib/categories';

import CategoryBlock from '../components/CategoryBlock';
import Breadcrumbs from '../components/Breadcrumbs';
import { TileSkeleton } from '../components/Skeleton';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { russiaHomeTrail } from '../lib/breadcrumbs';
import {
  calendarPath,
  demographicsPath,
  regionHubPath,
  russiaCategoriesPath,
  russiaHomePath,
  todayPath,
} from '../lib/sitePaths';

const QUICK_LINK_DEFS = [
  { to: todayPath(), titleKey: 'russia.link.today.title', descKey: 'russia.link.today.desc', icon: ArrowRight },
  { to: regionHubPath(), titleKey: 'russia.link.regions.title', descKey: 'russia.link.regions.desc', icon: MapPinned },
  { to: calendarPath(), titleKey: 'russia.link.calendar.title', descKey: 'russia.link.calendar.desc', icon: CalendarDays },
  { to: demographicsPath(), titleKey: 'russia.link.demographics.title', descKey: 'russia.link.demographics.desc', icon: Users },
];

export default function RussiaHome() {
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

  const russiaSeo = getPageSeo('russia', locale);
  useDocumentMeta({
    title: russiaSeo.title,
    description: russiaSeo.description,
    path: russiaSeo.path || russiaHomePath(),
  });

  const crumbs = russiaHomeTrail();

  return (
    <div className="mx-auto max-w-7xl overflow-x-hidden px-4 pb-28 pt-24 md:px-8">
      <Breadcrumbs items={crumbs} className="mb-6" />
      <header className="mb-10 max-w-3xl">
        <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
          {t('russia.eyebrow')}
        </p>
        <h1 className="mt-2 font-display text-3xl font-bold leading-tight text-text-primary md:text-4xl">
          {russiaSeo?.h1 || t('crumb.russia')}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-text-secondary md:text-base">
          {russiaSeo?.intro}
        </p>
      </header>

      <section className="mb-10" aria-labelledby="russia-quick-title">
        <h2
          id="russia-quick-title"
          className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-text-secondary"
        >
          {t('russia.sections')}
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {QUICK_LINK_DEFS.map((item) => {
            const Icon = item.icon;
            return (
            <Link
              key={item.to}
              to={item.to}
              className="group flex items-start gap-3 rounded-xl border border-border-subtle bg-surface px-4 py-3.5 transition-all hover:border-border-champagne hover:shadow-sm"
            >
              <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-champagne/10 text-champagne">
                <Icon size={15} />
              </div>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-text-primary group-hover:text-champagne">
                  {t(item.titleKey)}
                </div>
                <p className="mt-0.5 text-[12px] leading-snug text-text-secondary">{t(item.descKey)}</p>
              </div>
            </Link>
            );
          })}
        </div>
      </section>

      <section aria-labelledby="russia-categories-title">
        <div className="mb-6 flex flex-wrap items-end gap-x-4 gap-y-2">
          <div className="min-w-0">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
              {t('russia.macro.eyebrow')}
            </div>
            <h2
              id="russia-categories-title"
              className="mt-1 text-xs font-semibold uppercase tracking-[0.2em] text-text-secondary"
            >
              {t('russia.categories.title')}
            </h2>
          </div>
          <Link
            to={russiaCategoriesPath()}
            className="mb-1.5 text-xs font-medium text-champagne hover:underline"
          >
            {t('russia.categories.all')}
          </Link>
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
                indicatorCount={counts[cat.slug] || 0}
                delay={i * 40}
                countsKnown={!isError}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
