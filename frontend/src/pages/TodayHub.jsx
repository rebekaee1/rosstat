import { Link } from 'react-router-dom';
import { ArrowUpRight, Info } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useIndicator, useIndicatorData } from '../lib/hooks';
import { TODAY_CODES, TODAY_SPECS } from '../lib/todaySpecs';
import { formatValue, formatDate, resolveDateFormat, unitDigits, unitSuffix } from '../lib/format';
import { indicatorPolarity } from '../lib/deltaTone';
import { formatDeltaWithUnit } from '../lib/deltaText';
import { glueDate, periodPhrase } from '../lib/periodPhrase';
import DeltaBadge from '../components/DeltaBadge';
import Sparkline, { SparklineSkeleton } from '../components/Sparkline';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import Button from '../components/Button';
import { todayTrail } from '../lib/breadcrumbs';
import {
  calendarPath,
  regionHubPath,
  todayPath,
} from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import '../styles/platform-pages.css';
import '../styles/indicator-russia.css';
import '../styles/x2-indicator.css';
import '../styles/w6f-pages.css';

function todayLabel(code, t) {
  const key = `today.spec.${code}`;
  const translated = t(key);
  if (translated && translated !== key) return translated;
  return TODAY_SPECS[code]?.query || code;
}

function formatTodayDate(d, locale) {
  try {
    return new Intl.DateTimeFormat(locale === 'en' ? 'en-GB' : 'ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    }).format(d);
  } catch {
    return d.toISOString().slice(0, 10);
  }
}

// «процентного пункта» не должно рваться на три строки в узкой карточке: слова пункта держим вместе, а между числом
// и единицей оставляем обычный пробел, чтобы подпись переносилась как «+0,34» и «процентного пункта».
function keepUnitWordsTogether(delta) {
  if (!delta || delta.flat) return delta;
  return { ...delta, text: delta.text.replace('\u00a0процентного пункта', ' процентного\u00a0пункта') };
}

const CBR_RATE_CODES = new Set(['usd-rub', 'eur-rub', 'cny-rub']);
// Биржевые индексы измеряются в «пунктах»: людям понятнее изменение в процентах.
const INDEX_UNITS = new Set(['пунктов', 'пункт', 'points', 'pts']);

// Сколько последних значений брать для мини-графика. Ключевая ставка меняется раз в 1–2 месяца:
// за 30 дней это ровная линия-«заплатка», поэтому показываем около года.
const SPARK_LIMIT = { 'key-rate': 365 };

function TodayCard({ code, index }) {
  const t = useT();
  const { locale } = useLocale();
  const spec = TODAY_SPECS[code];
  const seriesCode = spec.series || code;
  const { data: indicator } = useIndicator(seriesCode);
  const {
    data: rows, isLoading, isError, refetch, isFetching,
  } = useIndicatorData(seriesCode, { limit: SPARK_LIMIT[code] || 30 });
  const query = todayLabel(code, t);

  const series = rows?.data || [];
  const last = series[series.length - 1];
  const prev = series.length > 1 ? series[series.length - 2] : null;
  const change = last && prev ? last.value - prev.value : null;
  const unit = indicator?.unit || '';
  const polarity = indicatorPolarity(query, indicator?.name, indicator?.code);
  const isIndexUnit = INDEX_UNITS.has(unit);
  const pctChange = isIndexUnit && change != null && prev && Number(prev.value) !== 0
    ? (change / Number(prev.value)) * 100
    : null;
  const delta = change == null ? null
    : isIndexUnit
      ? (pctChange == null ? null : formatDeltaWithUnit(pctChange, unit, { pct: true, locale }))
      : keepUnitWordsTogether(formatDeltaWithUnit(change, unit, { locale, plain: true }));
  const dateFmt = resolveDateFormat({ frequency: indicator?.frequency });
  const dateText = last ? glueDate(formatDate(last.date, dateFmt, locale)) : '';
  const meta = !last ? null : (CBR_RATE_CODES.has(code)
    ? t('w3.today.cbrRate', { date: dateText })
    : periodPhrase(t, last.date, dateFmt, locale));
  const perKey = ['daily', 'weekly', 'monthly', 'quarterly', 'annual'].includes(indicator?.frequency)
    ? `w3.tile.per.${indicator.frequency}`
    : 'w3.tele.delta.prevValue';
  const sparkValues = series.map((row) => Number(row.value)).filter(Number.isFinite);
  // Цвет графика — по тому же изменению, что показывает значок рядом: зелёный график при красной дельте сбивает с толку.
  const trend = change == null || Math.abs(change) < 1e-12 ? 'flat' : change > 0 ? 'up' : 'down';
  // Ровный график без оценки «хорошо/плохо»: золотая линия, а не бледно-серая.
  const sentiment = trend === 'flat' ? 'neutral'
    : polarity === 'up-good' ? 'positive' : polarity === 'up-bad' ? 'inverse' : 'neutral';

  if (isError && !last) {
    return (
      <div className="fe-today-card fe-today-card--error" role="alert">
        <p className="fe-today-card__label">{query}</p>
        <p className="fe-today-card__meta">{t('pgui.today.cardError')}</p>
        <Button variant="secondary" size="sm" className="mt-auto self-start" loading={isFetching} onClick={() => refetch()}>
          {t('common.retry')}
        </Button>
      </div>
    );
  }

  return (
    <Link
      to={todayPath(code)}
      style={{ '--i': Math.min(index, 5), '--fe-duration': '0.4s', '--fe-rise': '12px' }}
      className="fe-reveal fe-reveal--free fe-reveal--stagger fe-today-card fe-press group"
    >
      <div className="fe-today-card__top">
        <p className="fe-today-card__label">{query}</p>
        <ArrowUpRight className="fe-today-card__go" aria-hidden="true" />
      </div>
      {isLoading ? (
        <>
          <SkeletonBox className="h-7 w-28" />
          <SkeletonBox className="h-4 w-24" />
          <SparklineSkeleton height={36} />
        </>
      ) : !last ? (
        <span className="fe-today-card__meta">{t('common.noData')}</span>
      ) : (
        <>
          <p className="fe-today-card__value">
            <span className="fe-today-card__num">{formatValue(last.value, unitDigits(unit), locale)}</span>
            {unitSuffix(unit) && !isIndexUnit ? <span className="fe-today-card__unit">{unitSuffix(unit)}</span> : null}
          </p>
          {/* Дата рядом с числом и крупнее: видно, какой день или месяц показан («сегодня» для месячных данных обманывало). */}
          {meta && <p className="fe-today-card__asof">{meta}</p>}
          {delta && (
            <p className="fe-today-card__delta">
              {delta.flat ? (
                <DeltaBadge delta={0}>{t('w3.tele.noChange')}</DeltaBadge>
              ) : (
                <>
                  <DeltaBadge delta={change} polarity={polarity}>{delta.text}</DeltaBadge>
                  <span className="fe-today-card__vs">{t(perKey)}</span>
                </>
              )}
            </p>
          )}
          {sparkValues.length > 1 ? (
            <div className="fe-today-card__spark">
              <Sparkline points={sparkValues} trend={trend} sentiment={sentiment} height={36} staggerMs={Math.min(index, 5) * 80} />
            </div>
          ) : (
            <div
              className="fe-today-card__spark fe-today-card__spark--empty"
              role="img"
              aria-label={t('x2.today.noChart')}
              title={t('x2.today.noChart')}
            />
          )}
          <p className="fe-today-card__go-text" aria-hidden="true">{t('w6f.today.openChart')}</p>
        </>
      )}
    </Link>
  );
}

export default function TodayHub() {
  const t = useT();
  const { locale } = useLocale();
  const today = formatTodayDate(new Date(), locale);
  useDocumentMeta({
    title: t('today.metaTitle', { date: today }),
    description: t('today.metaDesc'),
    path: todayPath(),
  });

  return (
    <div className="fe-data-page max-w-5xl mx-auto px-4 pt-24 pb-20">
      <Breadcrumbs items={todayTrail()} />

      <p className="fe-today-eyebrow">
        {t('today.eyebrow', { date: today })}
      </p>
      <h1 className="font-display text-3xl sm:text-4xl font-bold text-text-primary mb-3">
        {t('today.h1')}
      </h1>
      <p className="text-text-secondary max-w-2xl mb-4">
        {t('today.intro')}
      </p>
      <p className="fe-today-note">
        <Info className="h-4 w-4 shrink-0" aria-hidden="true" />
        <span>{t('w3.today.fxNote')}</span>
      </p>

      <section id="chart" className="mb-10 scroll-mt-28">
        <h2 className="font-display text-lg font-semibold text-text-primary mb-4">
          {t('today.sectionTitle')}
        </h2>
        <div className="fe-today-grid">
          {TODAY_CODES.map((code, i) => (
            <TodayCard key={code} code={code} index={i} />
          ))}
        </div>
      </section>

      <section className="rounded-[1.5rem] p-5 fe-glass-lite">
        <h2 className="font-display text-base font-semibold text-text-primary mb-2">
          {t('today.moreTitle')}
        </h2>
        <p className="text-sm text-text-secondary">
          {t('today.moreBody.beforeHome')}
          <Link to="/" className="text-champagne-ink hover:underline">{t('today.moreBody.home')}</Link>
          {t('today.moreBody.beforeRegions')}
          <Link to={regionHubPath()} className="text-champagne-ink hover:underline">
            {t('today.moreBody.regions')}
          </Link>
          {t('today.moreBody.beforeCalendar')}
          <Link to={calendarPath()} className="text-champagne-ink hover:underline">
            {t('today.moreBody.calendar')}
          </Link>
          {t('today.moreBody.after')}
        </p>
      </section>
    </div>
  );
}
