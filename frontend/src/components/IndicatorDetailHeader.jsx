import { useParams } from 'react-router-dom';
import { Activity } from 'lucide-react';
import { displayCategoryLabel, findCategoryByApiLabel } from '../lib/categories';
import { indicatorDetailHeaderMobileLines } from '../lib/indicatorVariants';
import { SkeletonBox } from './Skeleton';
import '../styles/ui-detail-nav-calendar.css';
import '../styles/indicator-russia.css';
import Breadcrumbs from './Breadcrumbs';
import {
  globalMarketIndicatorTrail,
  globalMarketIndicatorYearTrail,
  russiaIndicatorTrail,
  russiaIndicatorYearTrail,
} from '../lib/breadcrumbs';
import { isGlobalMarketIndicator } from '../lib/globalMarketIndicators';
import { useLocale } from '../i18n';
import { localizeViewModeLabel } from '../i18n/viewModeLabels';
import AccentTitle from './K5Accent';
import CabinetActionsSlot from './CabinetActionsSlot';
import '../styles/z4-indicator.css';
import '../styles/k5-pages.css';

const FREQ_MAP = {
  monthly: 'Помесячно',
  quarterly: 'Ежеквартально',
  annual: 'Ежегодно',
  weekly: 'Еженедельно',
  irregular: 'Нерегулярно',
  daily: 'По дням',
};

function MobileTitle({ title }) {
  const lines = indicatorDetailHeaderMobileLines(title);
  if (!lines) {
    return <span className="md:hidden text-pretty"><AccentTitle text={title} /></span>;
  }
  return (
    <span className="md:hidden flex flex-col gap-0.5">
      {lines.map((line, index) => (
        <span key={line} className="block">
          {index === lines.length - 1 ? <AccentTitle text={line} /> : line}
        </span>
      ))}
    </span>
  );
}

const REVEAL = 'fe-reveal fe-reveal--free fe-reveal--stagger';
// Вход шапки: каскад по 40 мс, всего ≤ 160 мс; начальное состояние задаёт CSS (без мигания и без JS-твина).
const revealStyle = (i) => ({ '--i': i, '--fe-duration': '0.4s', '--fe-rise': '12px' });

/**
 * Хедер страницы карточки индикатора:
 *   хлебные крошки + бейдж периодичности + название; справа (`aside`) главное число с мини-графиком (на компьютере).
 */
export default function IndicatorDetailHeader({
  indicator,
  code,
  loading,
  displayFrequency,
  children = null,
  aside = null,
  subject = null,
  renderActions = null,
}) {
  const { locale } = useLocale();
  const { year } = useParams();
  const effectiveFrequency = displayFrequency ?? indicator?.frequency;
  const apiCategory = indicator?.category_ru || indicator?.category;
  const shownCategory = displayCategoryLabel(code, apiCategory);
  const category = findCategoryByApiLabel(shownCategory);
  const categoryCrumbName = locale === 'en'
    ? (category?.nameEn || category?.name)
    : category?.name;
  // Пока настоящее название не пришло, в крошках серая заглушка: ни внутренний код, ни раздел (страна, категория) не показываются.
  const nameKnown = Boolean(indicator?.name);
  const title = indicator?.name || '';
  const globalMarket = isGlobalMarketIndicator(code);
  const fullCrumbs = year
    ? (globalMarket
      ? globalMarketIndicatorYearTrail(
        categoryCrumbName,
        category?.slug,
        title,
        code,
        year,
      )
      : russiaIndicatorYearTrail(
        categoryCrumbName,
        category?.slug,
        title,
        code,
        year,
      ))
    : (globalMarket
      ? globalMarketIndicatorTrail(categoryCrumbName, category?.slug, title, code)
      : russiaIndicatorTrail(categoryCrumbName, category?.slug, title, code));
  const crumbs = nameKnown
    ? fullCrumbs
    : fullCrumbs.map((item, index) => (index === 0 ? item : { ...item, name: '' }));
  const freqLabel = localizeViewModeLabel(
    FREQ_MAP[effectiveFrequency] || effectiveFrequency,
    locale,
  );

  return (
    <div className="fe-data-header fe-indicator-header z4-hero fe-cursor-light" data-has-value={aside ? 'true' : 'false'}>
      <div className="z4-hero__main">
        <div className={REVEAL} style={revealStyle(0)}>
          <Breadcrumbs items={crumbs} variant="mono" />
        </div>

        {loading ? (
          <div className="space-y-4">
            <SkeletonBox className="h-4 w-24" />
            <SkeletonBox className="h-14 w-3/4" />
            <SkeletonBox className="h-6 w-1/2" />
          </div>
        ) : (
          <>
            <div className={`${REVEAL} fe-ind-meta`} style={revealStyle(1)}>
              {freqLabel ? (
                <span className="fe-ind-badge">
                  <Activity className="h-3.5 w-3.5 text-champagne-ink" aria-hidden="true" />
                  {freqLabel}
                </span>
              ) : null}
              <CabinetActionsSlot className="z4-hero__actions" subject={subject} renderActions={renderActions} />
            </div>

            <h1
              style={revealStyle(2)}
              className="fe-reveal fe-reveal--free fe-reveal--stagger z4-hero__title text-pretty font-display font-bold tracking-tight"
            >
              <MobileTitle title={title || code} />
              <span className="hidden md:inline"><AccentTitle text={title || code} /></span>
            </h1>
            {children ? <div className="z4-hero__line">{children}</div> : null}
          </>
        )}
      </div>
      {aside ? <div className="z4-hero__aside">{aside}</div> : null}
    </div>
  );
}
