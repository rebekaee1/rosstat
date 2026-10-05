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
import '../styles/k5-pages.css';

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

/**
 * Мини-график: линия факта, прогноз градиентом прозрачности (без пунктира), коридор-«призма» (тёплое слева,
 * холодное справа) и луч света на отметке «сейчас». Все линии и заливки задают градиенты SVG, фильтров нет.
 */
function MiniChart({ item, label }) {
  const uid = useId().replace(/:/g, '');
  const geo = useMemo(() => chartGeometry(item), [item]);
  if (!geo) return null;
  const bandId = `${uid}-band`;
  const foreId = `${uid}-fore`;
  const rayId = `${uid}-ray`;
  const glowId = `${uid}-glow`;
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
          <linearGradient id={bandId} x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor="#E9CD8E" stopOpacity="0.52" />
            <stop offset="1" stopColor="#BCD4EC" stopOpacity="0.32" />
          </linearGradient>
          <linearGradient id={foreId} gradientUnits="userSpaceOnUse" x1={geo.now.x} x2={geo.end.x + 0.01} y1="0" y2="0">
            <stop offset="0" stopColor="#B08A3E" stopOpacity="1" />
            <stop offset="1" stopColor="#C9A24D" stopOpacity="0.4" />
          </linearGradient>
          <linearGradient id={rayId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#E9CD8E" stopOpacity="0" />
            <stop offset="0.5" stopColor="#FFF6DA" stopOpacity="0.95" />
            <stop offset="1" stopColor="#E9CD8E" stopOpacity="0" />
          </linearGradient>
          <linearGradient id={glowId} x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor="#F3E4B8" stopOpacity="0" />
            <stop offset="0.5" stopColor="#F3E4B8" stopOpacity="0.5" />
            <stop offset="1" stopColor="#F3E4B8" stopOpacity="0" />
          </linearGradient>
        </defs>
        <rect className="zb-fc__zone" x={geo.zone.x} y="0" width={geo.zone.width} height={geo.height} rx="6" />
        {geo.bandPath ? (
          <path className="zb-fc__band" d={geo.bandPath} style={{ fill: `url(#${bandId})` }} />
        ) : null}
        <rect className="zb-fc__ray-glow" x={geo.splitX - 8} y="0" width="16" height={geo.height} fill={`url(#${glowId})`} />
        <rect className="zb-fc__ray" x={geo.splitX - 0.9} y="2" width="1.8" height={geo.height - 4} rx="0.9" fill={`url(#${rayId})`} />
        <path className="zb-fc__hist" d={geo.histPath} />
        <path className="zb-fc__fore" d={geo.forePath} stroke={`url(#${foreId})`} />
        <circle className="zb-fc__dot-now" cx={geo.now.x} cy={geo.now.y} r="4.5" />
        <circle className="zb-fc__dot-end" cx={geo.end.x} cy={geo.end.y} r="5.5" />
        <circle className="zb-fc__dot-spark" cx={geo.end.x - 1.8} cy={geo.end.y - 1.8} r="1.7" />
      </svg>
    </div>
  );
}

/** Стрелка-грань между «Сейчас» и «Через год»: золотой ромб с шевроном, без контура. */
function FacetArrow() {
  const gid = useId().replace(/:/g, '');
  return (
    <svg className="zb-fc__arrow" viewBox="0 0 30 30" width="30" height="30" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={`${gid}-d`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#F7EBC8" />
          <stop offset="0.55" stopColor="#C9A24D" />
          <stop offset="1" stopColor="#8F6B24" />
        </linearGradient>
      </defs>
      <path d="M15 1.5 L28.5 15 L15 28.5 L1.5 15 Z" fill={`url(#${gid}-d)`} />
      <path d="M15 1.5 L28.5 15 L15 15 L1.5 15 Z" fill="#fff" opacity="0.28" />
      <path d="M12.2 10.6 L17.4 15 L12.2 19.4" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
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
    <article className="fe-glass-lite zb-fc__card fe-reveal" data-testid="forecast-card" data-theme-id={item.theme}>
      <div className="zb-fc__card-head">
        <h3 className="zb-fc__card-title">{item.title}</h3>
        <span className="zb-fc__badge" data-verified={item.verified ? 'true' : 'false'}>
          {item.verified ? t('zb.fc.badge.checked') : t('zb.fc.badge.official')}
        </span>
      </div>

      <div className="zb-fc__nums">
        <div className="zb-fc__num">
          <span className="zb-fc__num-label">{t('zb.fc.now')}</span>
          <span className="zb-fc__num-value">{nowText}</span>
          <span className="zb-fc__num-date">{formatDate(item.last_actual.date, dateFormat, locale)}</span>
        </div>
        <FacetArrow />
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
        <div key={i} className="fe-glass-lite zb-fc__card" aria-hidden="true">
          <SkeletonBox className="h-5 w-3/4 rounded-md" />
          <div className="zb-fc__nums zb-fc__nums--skel">
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

      <div className="zb-fc__top">
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
      <div className="zb-fc__ribbon" aria-hidden="true">
        <img
          src="/brand/ribbon.webp"
          width="1114"
          height="631"
          alt=""
          loading="lazy"
          decoding="async"
          className="zb-fc__ribbon-img fe-drift"
          style={{ '--fe-drift-dur': '6s', '--fe-drift-y': '8px', '--fe-drift-r': '0.7deg' }}
        />
      </div>
      </div>

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
        <div className="fe-glass-lite zb-fc__note">
          <h2>{t('zb.fc.read.title')}</h2>
          <p>{t('zb.fc.read.body')}</p>
        </div>
        <div className="fe-glass-lite zb-fc__note">
          <h2>{t('zb.fc.notHere.title')}</h2>
          <p>{t('zb.fc.notHere.body')}</p>
        </div>
      </section>
    </div>
  );
}
