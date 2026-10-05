import { useId, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowDownRight, ArrowRight, ArrowUpRight, Minus } from 'lucide-react';
import api from '../lib/api';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { formatDate, formatValue, cn } from '../lib/format';
import { toolTrail } from '../lib/breadcrumbs';
import {
  changeMessageKey,
  chartGeometry,
  digitsFor,
  percentSign,
} from '../lib/forecastShowcase';
import { useLocale, useT } from '../i18n';
import Breadcrumbs from '../components/Breadcrumbs';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Chip from '../components/Chip';
import ChipGroup from '../components/ChipGroup';
import { SkeletonBox } from '../components/Skeleton';
import '../styles/zb-forecasts.css';

const FREQUENCY_FORMAT = { monthly: 'full', quarterly: 'quarterly', annual: 'annual' };

function useForecastShowcase() {
  const { locale } = useLocale();
  return useQuery({
    queryKey: ['forecast-showcase', locale],
    queryFn: ({ signal }) => api.get('/forecasts/showcase', { signal }).then((r) => r.data),
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
}

function valueText(item, value, locale) {
  return `${formatValue(value, digitsFor(item, value), locale)}${percentSign(item.unit)}`;
}

function ChangeIcon({ direction }) {
  if (direction === 'up') return <ArrowUpRight className="h-4 w-4" aria-hidden="true" />;
  if (direction === 'down') return <ArrowDownRight className="h-4 w-4" aria-hidden="true" />;
  return <Minus className="h-4 w-4" aria-hidden="true" />;
}

/** Мини-график: сплошная линия факта, пунктир прогноза, полоса коридора. */
function MiniChart({ item, label }) {
  const gradientId = useId().replace(/:/g, '');
  const geo = useMemo(() => chartGeometry(item), [item]);
  if (!geo) return null;
  return (
    <div className="zb-fc__plot">
      <svg
        className="zb-fc__svg"
        viewBox={`0 0 ${geo.width} ${geo.height}`}
        role="img"
        aria-label={label}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#ad8a48" stopOpacity="0.32" />
            <stop offset="1" stopColor="#ad8a48" stopOpacity="0.1" />
          </linearGradient>
        </defs>
        <rect className="zb-fc__zone" x={geo.zone.x} y="0" width={geo.zone.width} height={geo.height} rx="6" />
        <line className="zb-fc__split" x1={geo.splitX} x2={geo.splitX} y1="4" y2={geo.height - 4} />
        {geo.bandPath ? (
          <path className="zb-fc__band" d={geo.bandPath} style={{ fill: `url(#${gradientId})` }} />
        ) : null}
        <path className="zb-fc__hist" d={geo.histPath} />
        <path className="zb-fc__fore" d={geo.forePath} />
        <circle className="zb-fc__dot-now" cx={geo.now.x} cy={geo.now.y} r="4.5" />
        <circle className="zb-fc__dot-end" cx={geo.end.x} cy={geo.end.y} r="5" />
      </svg>
    </div>
  );
}

function ForecastCard({ item, locale, t }) {
  const dateFormat = FREQUENCY_FORMAT[item.frequency] || 'short';
  const nowText = valueText(item, item.last_actual.value, locale);
  const endText = valueText(item, item.forecast_end.value, locale);
  const n = formatValue(Math.abs(item.change.value), 1, locale);
  const changeText = t(changeMessageKey(item.change), { n });
  const { lower, upper } = item.forecast_end;
  const hasRange = Number.isFinite(lower) && Number.isFinite(upper);
  const rangeText = hasRange
    ? t('zb.fc.range', { low: valueText(item, lower, locale), high: valueText(item, upper, locale) })
    : '';
  const chartLabel = t('zb.fc.chartAria', {
    title: item.title,
    now: nowText,
    end: endText,
    change: changeText,
  });

  return (
    <article className="fe-panel zb-fc__card fe-reveal" data-testid="forecast-card" data-theme-id={item.theme}>
      <div className="zb-fc__card-head">
        <h3 className="zb-fc__card-title">{item.title}</h3>
        <span className="zb-fc__badge">
          {item.verified ? t('zb.fc.badge.checked') : t('zb.fc.badge.official')}
        </span>
      </div>

      <div className="zb-fc__nums">
        <div className="zb-fc__num">
          <span className="zb-fc__num-label">{t('zb.fc.now')}</span>
          <span className="zb-fc__num-value">{nowText}</span>
          <span className="zb-fc__num-date">{formatDate(item.last_actual.date, dateFormat, locale)}</span>
        </div>
        <div className="zb-fc__num zb-fc__num--end">
          <span className="zb-fc__num-label">{t('zb.fc.inYear')}</span>
          <span className="zb-fc__num-value">{endText}</span>
          <span className="zb-fc__num-date">{formatDate(item.forecast_end.date, dateFormat, locale)}</span>
        </div>
      </div>

      <span className={cn('zb-fc__change', `is-${item.change.direction}`)}>
        <ChangeIcon direction={item.change.direction} />
        {changeText}
      </span>

      <MiniChart item={item} label={chartLabel} />

      <p className="zb-fc__meta">
        {rangeText ? <>{rangeText}. </> : null}
        {item.unit ? <>{t('zb.fc.unit', { unit: item.unit })}</> : null}
      </p>

      <div className="zb-fc__foot">
        <span>{t('zb.fc.source', { source: item.source })}</span>
        <Link to={item.path} className="zb-fc__open">
          {t('zb.fc.open')}
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Link>
      </div>
    </article>
  );
}

function CardsSkeleton({ label }) {
  return (
    <div className="zb-fc__grid" aria-busy="true" aria-label={label} role="status">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="fe-panel zb-fc__card" aria-hidden="true">
          <SkeletonBox className="h-5 w-3/4 rounded-md" />
          <div className="zb-fc__nums">
            <SkeletonBox className="h-12 w-full rounded-lg" />
            <SkeletonBox className="h-12 w-full rounded-lg" />
          </div>
          <SkeletonBox className="h-[132px] w-full rounded-2xl" />
          <SkeletonBox className="h-4 w-2/3 rounded-md" />
        </div>
      ))}
    </div>
  );
}

/**
 * «Прогнозы»: только то, что платформа реально прогнозирует (Россия и страны, где прогноз
 * прошёл проверку на прошлых данных). Данные и тексты из той же витрины, что и серверная
 * страница; методология остаётся второй ссылкой «Как мы считаем».
 */
export default function ForecastsPage() {
  const t = useT();
  const { locale } = useLocale();
  const seo = getPageSeo('forecasts', locale);
  const [theme, setTheme] = useState('all');
  const { data, isLoading, isError, refetch, isFetching } = useForecastShowcase();

  useDocumentMeta({
    title: seo?.title,
    description: seo?.description,
    path: seo?.path,
  });

  const items = data?.items || [];
  const themes = data?.themes || [];
  const visible = theme === 'all' ? items : items.filter((item) => item.theme === theme);

  return (
    <div className="fe-data-page fe-gutter zb-fc mx-auto pt-20 pb-12 sm:pb-16">
      <Breadcrumbs items={toolTrail(seo?.h1 || t('zb.fc.title'), seo?.path || '/forecasts')} className="mb-6" />

      <header className="zb-fc__head fe-reveal">
        <p className="zb-fc__eyebrow">{t('zb.fc.eyebrow')}</p>
        <h1 className="zb-fc__title font-display">{seo?.h1 || t('zb.fc.title')}</h1>
        <p className="zb-fc__lead">{seo?.intro}</p>
        <div className="zb-fc__links">
          <Link to="/methodology#read" className="zb-fc__link">
            {t('zb.fc.method')}
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
      </header>

      {isError && (
        <ApiRetryBanner className="mb-6" onRetry={() => refetch()} isFetching={isFetching}>
          <span className="font-semibold">{t('zb.fc.errorTitle')}</span>{' '}
          {t('zb.fc.errorBody')}
        </ApiRetryBanner>
      )}

      {!isError && (
        <div className="zb-fc__bar">
          {themes.length > 1 ? (
            <ChipGroup label={t('zb.fc.filterAria')}>
              <Chip active={theme === 'all'} onClick={() => setTheme('all')}>{t('zb.fc.filterAll')}</Chip>
              {themes.map((row) => (
                <Chip key={row.id} active={theme === row.id} onClick={() => setTheme(row.id)}>
                  {row.name}
                </Chip>
              ))}
            </ChipGroup>
          ) : <span />}
          <ul className="zb-fc__legend" aria-label={t('zb.fc.legendAria')}>
            <li><span className="zb-fc__key" aria-hidden="true" />{t('zb.fc.legendFact')}</li>
            <li><span className="zb-fc__key zb-fc__key--forecast" aria-hidden="true" />{t('zb.fc.legendForecast')}</li>
            <li><span className="zb-fc__key zb-fc__key--range" aria-hidden="true" />{t('zb.fc.legendRange')}</li>
          </ul>
        </div>
      )}

      {isLoading && <CardsSkeleton label={t('zb.fc.loadingAria')} />}

      {!isLoading && !isError && visible.length > 0 && (
        <div className="zb-fc__grid">
          {visible.map((item) => (
            <ForecastCard key={item.id} item={item} locale={locale} t={t} />
          ))}
        </div>
      )}

      {!isLoading && !isError && items.length === 0 && (
        <p className="zb-fc__empty">{t('zb.fc.empty')}</p>
      )}

      <section className="zb-fc__notes" aria-label={t('zb.fc.notesAria')}>
        <div className="fe-panel-soft zb-fc__note">
          <h2>{t('zb.fc.read.title')}</h2>
          <p>{t('zb.fc.read.body')}</p>
        </div>
        <div className="fe-panel-soft zb-fc__note">
          <h2>{t('zb.fc.notHere.title')}</h2>
          <p>{t('zb.fc.notHere.body')}</p>
        </div>
      </section>
    </div>
  );
}
