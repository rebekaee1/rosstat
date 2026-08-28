/**
 * Карточка страны /russia (ADR-0013).
 *
 * Единый формат страницы страны (эталон — WorldCountry, слой данных другой —
 * российский каталог через useIndicators): hero с картой территории и
 * обзорными чипами, sticky aside категорий, секции с плитками значений.
 * Главная `/` остаётся витриной платформы; здесь — вход в российский контур.
 */
import { Suspense, lazy, useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  ArrowRight, ArrowUpRight, CalendarDays, MapPinned, TrendingUp, Users,
} from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import { useRegionsLanding } from '../lib/regionsApi';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { useLocale, useT } from '../i18n';
import { CATEGORIES } from '../lib/categories';
import {
  groupRussiaCategories,
  russiaIndicatorChange,
  russiaIndicatorDisplay,
  russiaOverviewChips,
} from '../lib/russiaHomeCards';
import { formatChange, formatDate, resolveDateFormat } from '../lib/format';
import {
  calendarPath,
  demographicsPath,
  regionHubPath,
  russiaCategoriesPath,
  russiaHomePath,
  russiaIndicatorPath,
  todayPath,
} from '../lib/sitePaths';
import Breadcrumbs from '../components/Breadcrumbs';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import MobileNavSelect from '../components/MobileNavSelect';
import { breadcrumbJsonLd, russiaHomeTrail } from '../lib/breadcrumbs';

const RegionsMap = lazy(() => import('../components/RegionsMap'));

function RussiaMapSkeleton() {
  return (
    <div className="aspect-[1000/538] w-full rounded-2xl border border-border-subtle bg-surface">
      <SkeletonBox className="h-full w-full rounded-2xl" />
    </div>
  );
}

/**
 * Карта территории России в hero /russia — в едином формате со страницей
 * страны (WorldCountry): рамка-подпись сверху, подвал с брендом снизу.
 * Силуэт из локальной геометрии (variant="compact" — без зум-контролов);
 * клик по субъекту ведёт в его профиль.
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
      className="relative overflow-hidden rounded-2xl border border-border-subtle bg-surface shadow-[0_22px_70px_rgba(35,30,16,0.06)]"
      aria-label={t('russia.map.caption')}
    >
      <div className="flex items-center justify-between gap-3 border-b border-border-subtle px-4 py-3">
        <div>
          <div className="text-[9px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
            {t('russia.map.eyebrow')}
          </div>
          <div className="mt-0.5 text-xs font-medium text-text-primary">
            {t('russia.map.caption')}
          </div>
        </div>
        <span className="shrink-0 rounded-md border border-border-subtle bg-obsidian-light px-2 py-1 font-mono text-[10px] text-text-secondary">
          RU
        </span>
      </div>

      <Suspense fallback={<RussiaMapSkeleton />}>
        <RegionsMap
          variant="compact"
          valuesBySlug={null}
          nameBySlug={nameBySlug}
          className="aspect-[1000/538] bg-obsidian-light/40"
        />
      </Suspense>

      <div className="border-t border-border-subtle px-4 py-3">
        <p className="flex items-center gap-1.5 text-[11px] leading-snug text-text-secondary">
          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-champagne" aria-hidden="true" />
          {t('russia.map.note')}
        </p>
        <div className="mt-2 text-right text-[9px] uppercase tracking-[0.18em] text-text-tertiary/70">
          forecasteconomy.com
        </div>
      </div>
    </aside>
  );
}

const QUICK_LINK_DEFS = [
  { to: todayPath(), titleKey: 'russia.link.today.title', descKey: 'russia.link.today.desc', icon: ArrowRight },
  { to: regionHubPath(), titleKey: 'russia.link.regions.title', descKey: 'russia.link.regions.desc', icon: MapPinned },
  { to: calendarPath(), titleKey: 'russia.link.calendar.title', descKey: 'russia.link.calendar.desc', icon: CalendarDays },
  { to: demographicsPath(), titleKey: 'russia.link.demographics.title', descKey: 'russia.link.demographics.desc', icon: Users },
];

function indicatorDate(dateStr, frequency, locale) {
  if (!dateStr) return '—';
  return formatDate(dateStr, resolveDateFormat({ frequency }), locale);
}

function formatNumberRu(value, locale) {
  return value.toLocaleString(locale === 'en' ? 'en-US' : 'ru-RU', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

/** Частота плитки: официальная подпись из словаря, при отсутствии — сырой код. */
function FreqBadge({ item, t }) {
  if (!item.frequency) return null;
  const key = `world.freq.${item.frequency}`;
  const label = t(key);
  return (
    <span className="rounded-full bg-obsidian-light px-2 py-0.5 font-mono">
      {label !== key ? label : item.frequency}
    </span>
  );
}

/**
 * Плитка показателя секции — аналог IndicatorRow страницы страны, но на
 * российском слое данных (hero-семантика IndicatorTile, ссылки в /russia).
 */
function RussiaIndicatorTile({ indicator }) {
  const t = useT();
  const { locale } = useLocale();
  const display = russiaIndicatorDisplay(indicator);
  const changeNum = russiaIndicatorChange(indicator);

  return (
    <Link
      to={russiaIndicatorPath(indicator.code)}
      className="group flex flex-col gap-2 rounded-xl border border-border-subtle bg-white px-3.5 py-3 transition-all hover:border-border-champagne hover:shadow-[0_12px_30px_rgba(35,30,16,0.06)] sm:min-h-[92px] sm:flex-row sm:items-center sm:gap-3 sm:px-4 sm:py-3.5"
    >
      <div className="min-w-0 flex-1">
        <div className="text-[13px] leading-snug text-text-primary transition-colors group-hover:text-champagne sm:text-[14px]">
          {indicator.name}
        </div>
        <div className="mt-1 flex min-w-0 flex-wrap items-center gap-1.5 text-[10px] text-text-tertiary sm:mt-1.5">
          <FreqBadge item={indicator} t={t} />
          {indicator.unit && <span className="line-clamp-1 break-all">{indicator.unit}</span>}
        </div>
      </div>
      <div className="flex items-baseline justify-between gap-3 border-t border-border-subtle/60 pt-2 sm:w-[7.5rem] sm:shrink-0 sm:flex-col sm:items-end sm:justify-center sm:border-0 sm:pt-0 sm:text-right">
        <div className="font-mono text-[15px] font-semibold tabular-nums text-text-primary sm:text-[14px] sm:font-medium">
          {display ? formatNumberRu(display.value, locale) : '—'}
        </div>
        <div className="flex items-center gap-1.5">
          {changeNum != null && (
            <span className={`font-mono text-[10px] tabular-nums ${changeNum > 0 ? 'text-positive' : 'text-negative'}`}>
              {formatChange(changeNum, locale)}
            </span>
          )}
          {indicator.current_date && (
            <span className="font-mono text-[10px] text-text-tertiary">
              {indicatorDate(indicator.current_date, indicator.frequency, locale)}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

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

  const chips = useMemo(() => russiaOverviewChips(indicators), [indicators]);

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
      document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
    return () => window.clearTimeout(timer);
  }, [hash, indicators]);
  useEffect(() => {
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.id = 'russia-home-jsonld';
    script.textContent = JSON.stringify(breadcrumbJsonLd(crumbs));
    document.getElementById('russia-home-jsonld')?.remove();
    document.head.appendChild(script);
    return () => script.remove();
  }, [crumbs]);

  return (
    <div className="mx-auto w-full max-w-7xl overflow-x-clip px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs items={crumbs} />

      <section className="relative mb-6 overflow-hidden rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-[0_22px_70px_rgba(35,30,16,0.06)] sm:mb-8 sm:rounded-[2rem] sm:p-8">
        <div className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 rounded-full bg-champagne/10 blur-3xl" />
        <div className="relative grid gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(300px,0.7fr)] lg:items-center lg:gap-7">
          <div className="min-w-0">
            <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
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

        <div className="relative mt-6 grid gap-2 border-t border-border-subtle pt-5 sm:grid-cols-3 sm:gap-4" data-testid="russia-overview-chips">
          {chips.map((chip) => (
            <Link
              key={chip.code}
              to={russiaIndicatorPath(chip.code)}
              className="group min-w-0 rounded-xl bg-obsidian-light/65 px-3 py-3 transition-colors hover:bg-champagne/[0.08]"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="font-mono text-lg font-semibold tabular-nums text-text-primary">
                  {chip.value.toLocaleString(locale === 'en' ? 'en-US' : 'ru-RU', {
                    minimumFractionDigits: 0,
                    maximumFractionDigits: 2,
                  })}
                  <span className="ml-1 text-xs font-normal text-text-secondary">
                    {chip.unit}
                  </span>
                </div>
                <TrendingUp size={13} className="mt-1 shrink-0 text-champagne" />
              </div>
              <div className="mt-1 line-clamp-1 text-[10px] text-text-secondary group-hover:text-text-primary">
                {chip.indicator.name}
              </div>
              <div className="mt-1 truncate font-mono text-[9px] text-text-tertiary">
                {indicatorDate(chip.indicator.current_date, chip.indicator.frequency, locale)}
              </div>
            </Link>
          ))}
          {isLoading && (
            <div className="sm:col-span-3 grid gap-2 sm:grid-cols-3 sm:gap-4">
              {[0, 1, 2].map((i) => (
                <SkeletonBox key={i} className="h-[86px] rounded-xl" />
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="mb-8" aria-labelledby="russia-quick-title">
        <h2
          id="russia-quick-title"
          className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-text-secondary"
        >
          {t('russia.sections')}
        </h2>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {QUICK_LINK_DEFS.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.to}
                to={item.to}
                className="group flex items-start gap-3 rounded-xl border border-border-subtle bg-surface px-3.5 py-3 transition-all hover:border-border-champagne hover:shadow-sm"
              >
                <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-champagne/10 text-champagne">
                  <Icon size={15} />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-1 text-sm font-semibold text-text-primary group-hover:text-champagne">
                    <span className="truncate">{t(item.titleKey)}</span>
                    <ArrowUpRight size={12} className="shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-[12px] leading-snug text-text-secondary">
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
        <div className="space-y-4">
          <SkeletonBox className="h-9 w-64 max-w-full" />
          <SkeletonBox className="h-10 w-full rounded-xl" />
          <SkeletonBox className="h-40 rounded-xl" />
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
                  label: g.category.name,
                  count: g.indicators.length,
                }))}
              />
              <Link
                to={russiaCategoriesPath()}
                className="mb-4 inline-block text-xs font-medium text-champagne hover:underline"
              >
                {t('russia.categories.all')}
              </Link>
            </div>
          )}

          <div className="grid min-w-0 gap-6 lg:grid-cols-[250px_minmax(0,1fr)]">
            {grouped.length > 0 && (
              <aside className="hidden min-w-0 lg:sticky lg:top-24 lg:block lg:self-start" data-testid="russia-aside">
                <div className="mb-2 px-2 text-[10px] font-mono uppercase tracking-[0.18em] text-text-tertiary">
                  {t('russia.categories.title')}
                </div>
                <nav className="flex flex-col gap-2" aria-label={t('russia.categories.title')}>
                  {grouped.map((g) => (
                    <a
                      key={g.category.slug}
                      href={`#cat-${g.category.slug}`}
                      className="flex items-center justify-between gap-4 rounded-xl px-3.5 py-2.5 text-left text-sm text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
                    >
                      <span className="min-w-0 truncate">{g.category.name}</span>
                      <span className="shrink-0 font-mono text-[10px] opacity-60">{g.count}</span>
                    </a>
                  ))}
                </nav>
                <Link
                  to={russiaCategoriesPath()}
                  className="mt-3 block px-3.5 text-xs font-medium text-champagne hover:underline"
                >
                  {t('russia.categories.all')}
                </Link>
              </aside>
            )}

            <div className="min-w-0 space-y-8">
              {totalIndicators === 0 && !isError && (
                <div className="rounded-2xl border border-border-subtle bg-surface p-6 text-center text-sm text-text-secondary">
                  {t('world.country.emptyCatalog')}
                </div>
              )}

              {visibleCategories.map((g) => (
                <section key={g.category.slug} id={`cat-${g.category.slug}`} className="scroll-mt-24" data-testid="russia-section">
                  <div className="mb-3 flex items-end justify-between gap-3 sm:mb-4 sm:gap-4">
                    <div className="min-w-0">
                      <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-champagne">
                        {t('world.country.indicators')}
                      </div>
                      <h2 className="mt-1 font-display text-xl font-bold leading-snug text-text-primary sm:text-2xl">
                        {g.category.name}
                      </h2>
                    </div>
                    <span className="shrink-0 font-mono text-xs text-text-tertiary">{g.count}</span>
                  </div>
                  <div className="grid gap-2 sm:gap-2.5 xl:grid-cols-2">
                    {g.indicators.map((ind) => (
                      <RussiaIndicatorTile key={ind.code} indicator={ind} />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
