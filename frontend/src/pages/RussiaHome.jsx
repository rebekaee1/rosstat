/**
 * Карточка страны /russia (ADR-0013).
 *
 * Единый формат страницы страны (эталон — WorldCountry, слой данных другой —
 * российский каталог через useIndicators): hero с картой территории и
 * обзорными чипами, sticky aside категорий, секции с плитками значений.
 */
import { Suspense, lazy, useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  ArrowUpRight, CalendarDays, MapPinned, Newspaper, Scale, Trophy, Users,
} from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import { useRegionsLanding } from '../lib/regionsApi';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { useLocale, useT } from '../i18n';
import { CATEGORIES, categoryLabel } from '../lib/categories';
import { groupRussiaCategories } from '../lib/russiaHomeCards';
import RussiaKeyFigures from '../components/russia/RussiaKeyFigures';
import RussiaCategorySection from '../components/russia/RussiaCategorySection';
import {
  calendarPath,
  comparePath,
  demographicsPath,
  regionHubPath,
  regionRatingHubPath,
  russiaCategoriesPath,
  russiaHomePath,
  todayPath,
} from '../lib/sitePaths';
import Breadcrumbs from '../components/Breadcrumbs';
import ApiRetryBanner from '../components/ApiRetryBanner';
import LoadingNote from '../components/LoadingNote';
import { SkeletonBox } from '../components/Skeleton';
import MobileNavSelect from '../components/MobileNavSelect';
import { breadcrumbJsonLd, russiaHomeTrail } from '../lib/breadcrumbs';
import { mountJsonLd } from '../lib/jsonLd';
import '../styles/platform-pages.css';
import '../styles/indicator-russia.css';
import '../styles/z5-country.css';

const RegionsMap = lazy(() => import('../components/RegionsMap'));

function RussiaMapSkeleton() {
  return (
    <div className="aspect-[984/526] w-full bg-[#191A20]/40">
      <SkeletonBox className="h-full w-full rounded-none bg-white/5" />
    </div>
  );
}

/**
 * Карта территории России в hero /russia — тот же тёмный territory-card,
 * что CountrySilhouette на /denmark: фон #191A20, сетка, шампань-силуэт.
 * Регионы кликабельны (профиль субъекта), hover — имя во всплывашке.
 */
function RussiaTerritoryCard() {
  const t = useT();
  const landing = useRegionsLanding();

  const nameBySlug = useMemo(() => {
    const out = {};
    (landing.data?.districts || []).forEach(
      (d) => d.regions.forEach((r) => { out[r.slug] = r.name; }),
    );
    if (landing.data?.russia?.slug) out[landing.data.russia.slug] = landing.data.russia.name;
    return out;
  }, [landing.data]);

  return (
    <aside
      data-block="russia-territory-card"
      className="relative min-h-[270px] overflow-hidden rounded-2xl bg-[#191A20] shadow-[0_20px_45px_rgba(24,24,31,0.18)]"
      aria-label={t('russia.map.caption')}
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_72%_28%,rgba(207,180,95,0.2),transparent_47%)]" />
      <div
        className="pointer-events-none absolute inset-0 opacity-20"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.08) 1px, transparent 1px)',
          backgroundSize: '32px 32px',
        }}
      />

      <div className="absolute left-4 top-3 z-10 max-w-[60%] pr-2">
        <div className="text-[13px] font-semibold text-white/80">
          {t('world.territory.profile')}
        </div>
        <div className="mt-1 text-xs text-[#d8c58b]">
          {t('russia.map.eyebrow')}
        </div>
      </div>

      <div className="relative pt-9 pb-14">
        <Suspense fallback={<RussiaMapSkeleton />}>
          <RegionsMap
            variant="compact"
            theme="dark"
            valuesBySlug={null}
            nameBySlug={nameBySlug}
            className="bg-transparent"
          />
        </Suspense>
      </div>

      <div className="absolute bottom-3 left-4 right-4 z-10 flex items-start justify-between gap-x-2 gap-y-1 pt-3 sm:items-end sm:gap-3">
        <div className="min-w-0">
          <div className="max-w-[11rem] truncate text-sm font-semibold text-white/90">
            {t('crumb.russia')}
          </div>
        </div>
        <div className="max-w-[14rem] text-right text-xs leading-snug text-white/75">
          {t('russia.map.note')}
        </div>
      </div>
    </aside>
  );
}

const QUICK_LINK_DEFS = [
  { to: todayPath(), titleKey: 'russia.link.today.title', descKey: 'russia.link.today.desc', icon: Newspaper },
  { to: regionHubPath(), titleKey: 'russia.link.regions.title', descKey: 'russia.link.regions.desc', icon: MapPinned },
  { to: regionRatingHubPath(), titleKey: 'russia.link.ratings.title', descKey: 'russia.link.ratings.desc', icon: Trophy },
  { to: calendarPath(), titleKey: 'russia.link.calendar.title', descKey: 'russia.link.calendar.desc', icon: CalendarDays },
  { to: demographicsPath(), titleKey: 'russia.link.demographics.title', descKey: 'russia.link.demographics.desc', icon: Users },
  { to: comparePath(), titleKey: 'z5.ru.link.compare.title', descKey: 'z5.ru.link.compare.desc', icon: Scale },
];

const QUICK_GRID_LG = {
  1: 'lg:grid-cols-1',
  2: 'lg:grid-cols-2',
  3: 'lg:grid-cols-3',
  4: 'lg:grid-cols-4',
  6: 'lg:grid-cols-3',
}[QUICK_LINK_DEFS.length] || 'lg:grid-cols-3';

/**
 * Мобильный вьюпорт: единственная колонка секций + select-навигация.
 * Подписка на media query — ресайз окна через границу lg переключает режим
 * без перезагрузки.
 */
function useIsMobileViewport() {
  const get = () => (typeof window !== 'undefined' && window.matchMedia
    ? !window.matchMedia('(min-width: 1024px)').matches
    : false);
  const [isMobile, setIsMobile] = useState(get);
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)');
    const onChange = (e) => setIsMobile(!e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return isMobile;
}

export default function RussiaHome() {
  const t = useT();
  const { locale } = useLocale();
  const { data: indicators, isLoading, isError, refetch, isFetching } = useIndicators();
  const [activeCategory, setActiveCategory] = useState('');
  const { hash } = useLocation();

  const russiaSeo = getPageSeo('russia', locale);
  useDocumentMeta({
    title: russiaSeo?.title,
    description: russiaSeo?.description,
    path: russiaSeo?.path || russiaHomePath(),
  });

  const grouped = useMemo(
    () => groupRussiaCategories(indicators, CATEGORIES),
    [indicators],
  );

  const totalIndicators = useMemo(
    () => grouped.reduce((n, g) => n + g.indicators.length, 0),
    [grouped],
  );

  // Резолв активной категории для мобильного select: сброс, если категория
  // исчезла из выборки (локаль/обновление данных).
  const resolvedActiveCategory = grouped.some((g) => g.category.slug === activeCategory)
    ? activeCategory
    : (grouped[0]?.category.slug || '');
  // На мобильном показываем только активную секцию (select-навигация),
  // на десктопе — все: sticky aside ведёт по якорям к каждой из них.
  // Реактивно к ресайзу через подписку (matchMedia меняется без ре-рендера).
  const isMobileSingle = useIsMobileViewport();
  const visibleCategories = isMobileSingle
    ? grouped.filter((g) => g.category.slug === resolvedActiveCategory)
    : grouped;

  const crumbs = useMemo(() => russiaHomeTrail(), []);

  // Плавный скролл к секции при переходе по якорю (и прямом заходе с #cat-*).
  useEffect(() => {
    if (!hash.startsWith('#cat-')) return undefined;
    const timer = window.setTimeout(() => {
      const calm = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: calm ? 'auto' : 'smooth', block: 'start' });
    }, 50);
    return () => window.clearTimeout(timer);
  }, [hash, indicators]);
  useEffect(() => {
    return mountJsonLd(breadcrumbJsonLd(crumbs));
  }, [crumbs]);

  return (
    <div className="fe-data-page z5-page mx-auto w-full max-w-7xl overflow-x-clip px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs items={crumbs} />

      <section className="fe-panel relative mb-6 overflow-hidden rounded-[1.5rem] p-4 shadow-[0_22px_70px_rgba(35,30,16,0.06)] sm:mb-8 sm:rounded-[2rem] sm:p-8">
        <div className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 rounded-full bg-champagne/10 blur-3xl" />
        <div className="relative grid gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(300px,0.7fr)] lg:items-center lg:gap-7">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-champagne-ink">
              {t('russia.eyebrow')}
            </p>
            <h1 className="mt-2 font-display text-3xl font-bold leading-tight text-text-primary md:text-5xl">
              {russiaSeo?.h1 || t('crumb.russia')}
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-text-secondary sm:mt-4 md:text-base">
              {russiaSeo?.intro}
            </p>
          </div>
          <RussiaTerritoryCard />
        </div>

        <div className="relative mt-6 pt-5 fe-divider">
          <h2 className="w2-main-title z5-main-title">{t('z5.ru.main.title')}</h2>
          <RussiaKeyFigures indicators={indicators} isLoading={isLoading} />
        </div>
      </section>

      <section className="mb-8" aria-labelledby="russia-quick-title">
        <h2
          id="russia-quick-title"
          className="mb-3 text-xl font-bold tracking-tight text-text-primary"
        >
          {t('russia.sections')}
        </h2>
        <div
          data-testid="russia-sections-grid"
          className={`grid grid-cols-1 gap-3 sm:grid-cols-2 ${QUICK_GRID_LG}`}
        >
          {QUICK_LINK_DEFS.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.to}
                to={item.to}
                className="fe-press group flex items-start gap-3 rounded-[1.5rem] px-4 py-3.5 transition-all hover:shadow-sm fe-glass-lite fe-float"
              >
                <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-champagne/10 text-champagne-ink">
                  <Icon size={15} />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-1 text-sm font-semibold text-text-primary group-hover:text-champagne-ink">
                    <span className="truncate">{t(item.titleKey)}</span>
                    <ArrowUpRight size={12} className="shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-[13px] leading-snug text-text-secondary">
                    {t(item.descKey)}
                  </p>
                </div>
              </Link>
            );
          })}
        </div>
      </section>

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

      {isLoading && (
        <div role="status" aria-busy="true" aria-label={t('common.loading')}>
          <LoadingNote onRefresh={() => refetch()} className="mb-4" />
          <SkeletonBox className="mb-4 h-[78px] w-full rounded-xl lg:hidden" />
          <div className="grid min-w-0 gap-6 lg:grid-cols-[250px_minmax(0,1fr)]">
            <div className="hidden space-y-2 lg:block">
              {Array.from({ length: 8 }).map((_, i) => <SkeletonBox key={i} className="h-11 rounded-xl" />)}
            </div>
            <div className="min-w-0">
              <SkeletonBox className="mb-4 h-[3.25rem] w-64 max-w-full" />
              <div className="grid gap-2 sm:gap-2.5 xl:grid-cols-2">
                {Array.from({ length: 6 }).map((_, i) => <SkeletonBox key={i} className="h-[110px] rounded-xl sm:h-[92px]" />)}
              </div>
            </div>
          </div>
        </div>
      )}

      {!isLoading && (
        <>
          {!isError && grouped.length > 0 && (
            <div className="lg:hidden">
              <MobileNavSelect
                label={t('russia.categories.title')}
                value={resolvedActiveCategory}
                onChange={setActiveCategory}
                options={grouped.map((g) => ({
                  value: g.category.slug,
                  label: categoryLabel(g.category, locale),
                  count: g.indicators.length,
                }))}
              />
              <Link
                to={russiaCategoriesPath()}
                className="fe-tap-inline mb-2 text-xs font-medium text-champagne-ink hover:underline"
              >
                {t('russia.categories.all')}
              </Link>
            </div>
          )}

          <div className="grid min-w-0 gap-6 lg:grid-cols-[250px_minmax(0,1fr)]">
            {grouped.length > 0 && (
              <aside className="hidden min-w-0 lg:sticky lg:top-24 lg:block lg:self-start" data-testid="russia-aside">
                <div className="mb-2 px-2 text-sm font-semibold text-text-primary">
                  {t('russia.categories.title')}
                </div>
                <nav className="flex flex-col gap-2" aria-label={t('russia.categories.title')}>
                  {grouped.map((g) => (
                    <a
                      key={g.category.slug}
                      href={`#cat-${g.category.slug}`}
                      className="fe-tap flex items-center justify-between gap-4 rounded-xl px-3.5 py-2.5 text-left text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
                    >
                      <span className="min-w-0 truncate">{categoryLabel(g.category, locale)}</span>
                      <span className="shrink-0 text-xs tabular-nums">{g.count}</span>
                    </a>
                  ))}
                </nav>
                <Link
                  to={russiaCategoriesPath()}
                  className="fe-tap-inline mt-3 px-3.5 text-xs font-medium text-champagne-ink hover:underline"
                >
                  {t('russia.categories.all')}
                </Link>
              </aside>
            )}

            <div className="min-w-0 space-y-8">
              {totalIndicators === 0 && !isError && (
                <div className="rounded-2xl p-6 text-center text-sm text-text-secondary fe-glass-lite">
                  {t('world.country.emptyCatalog')}
                </div>
              )}

              {visibleCategories.map((g) => (
                <RussiaCategorySection key={g.category.slug} group={g} label={categoryLabel(g.category, locale)} />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
