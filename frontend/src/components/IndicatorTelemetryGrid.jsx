import { formatDate, resolveDateFormat, chartValueDigits } from '../lib/format';
import { dataModeForUrlMode } from '../lib/cpiViewModeResolve';
import { dataModeForHousingUrlMode } from '../lib/housingViewModeResolve';
import { dataModeForPpiUrlMode } from '../lib/ppiViewModeResolve';
import { indicatorPolarity } from '../lib/deltaTone';
import { periodPhrase } from '../lib/periodPhrase';
import { useLocale, useT } from '../i18n';
import TelemetryCard from './TelemetryCard';
import { SkeletonBox } from './Skeleton';
import '../styles/indicator-russia.css';

/**
 * Сетка из 4 телеметрических карточек на странице индикатора:
 *   текущее значение, предыдущее, абсолютный максимум, среднее.
 */
export default function IndicatorTelemetryGrid({
  indicator,
  viewStats: s,
  stats,
  isPriceCategory,
  isHousingFamily,
  isPpiFamily,
  chartMode,
  safeViewMode,
  cpiPrevDate,
  adj,
  loading,
  firstDate,
}) {
  const t = useT();
  const { locale } = useLocale();
  const polarity = indicatorPolarity(indicator?.name, indicator?.name_en, indicator?.code);
  const dateFmt = resolveDateFormat({
    chartMode,
    frequency: indicator?.frequency,
    safeViewMode,
  });
  const dataMode = isPriceCategory
    ? dataModeForUrlMode(safeViewMode)
    : isHousingFamily
      ? dataModeForHousingUrlMode(safeViewMode)
      : isPpiFamily
        ? dataModeForPpiUrlMode(safeViewMode)
        : safeViewMode;

  const PCT_VIEW_MODES = new Set([
    'yoy', 'annual', 'qoq', 'mom', 'quarterly', 'inflation',
    'step-monthly', 'step-weekly', 'period-monthly', 'period-weekly',
  ]);
  const isIndexUnit = String(safeViewMode).startsWith('index')
    && (isPriceCategory || isHousingFamily || isPpiFamily);
  const unit = isIndexUnit
    ? 'индекс'
    : PCT_VIEW_MODES.has(safeViewMode) && (isPriceCategory || isHousingFamily || isPpiFamily)
      ? '%'
      : (safeViewMode === 'yoy' && indicator?.hero_value != null)
        ? '%'
        : (indicator?.unit || '%');
  const displayUnit = isIndexUnit ? t('indicator.telemetry.unitIndex') : unit;

  if (loading) {
    return (
      <section className="fe-tele-section">
        <div className="fe-tele-grid" aria-hidden="true">
          {[...Array(4)].map((_, i) => (
            <SkeletonBox key={i} className="fe-tele-skeleton" />
          ))}
        </div>
      </section>
    );
  }

  const heroOverride = indicator?.hero_value != null && safeViewMode === 'yoy';

  const currentLabel = heroOverride
    ? (indicator.hero_label || t('w3.tele.heroYoy'))
    : ['inflation', 'yoy', 'annual'].includes(dataMode) ? t('indicator.telemetry.yoy')
      : safeViewMode === 'yoy' || safeViewMode === 'annual' ? t('indicator.telemetry.yoy')
      : safeViewMode === 'mom' ? t('indicator.telemetry.mom')
        : safeViewMode === 'qoq' ? t('indicator.telemetry.qoq')
          : safeViewMode === 'period-monthly' ? t('indicator.telemetry.periodMonth')
            : safeViewMode === 'period-weekly' ? t('indicator.telemetry.periodWeek')
              : safeViewMode === 'step-monthly' ? t('w3.tele.stepMom')
                : safeViewMode === 'step-weekly' ? t('w3.tele.stepWow')
                  : dataMode === 'weekly' ? t('indicator.telemetry.weekInflation')
                    : dataMode === 'cpi' && isPriceCategory ? t('indicator.telemetry.monthGrowth')
                      : t('indicator.telemetry.current');

  const previousLabel = dataMode === 'weekly' || safeViewMode === 'step-weekly'
    || safeViewMode === 'period-weekly'
    ? t('indicator.telemetry.prevWeek')
    : safeViewMode === 'qoq' ? t('indicator.telemetry.prevQuarter')
      : safeViewMode === 'mom' ? t('indicator.telemetry.prevMonth')
        : safeViewMode === 'yoy'
          ? (chartMode === 'annual' || indicator?.frequency === 'annual'
            ? t('indicator.telemetry.prevYear')
            : indicator?.frequency === 'quarterly'
              ? t('indicator.telemetry.prevQuarter')
              : t('indicator.telemetry.prevMonth'))
          : safeViewMode === 'quarterly' ? t('indicator.telemetry.prevQuarter')
            : safeViewMode === 'annual' ? t('indicator.telemetry.prevYear')
              : isHousingFamily ? t('indicator.telemetry.prevQuarter')
                : isPriceCategory ? t('indicator.telemetry.prevMonth')
                  : t('indicator.telemetry.prev');

  const deltaSuffix = safeViewMode === 'qoq' ? t('w3.tele.delta.prevQuarter')
    : safeViewMode === 'mom' ? t('w3.tele.delta.prevMonth')
      : safeViewMode === 'yoy' ? t('w3.tele.delta.prevYear')
        : safeViewMode === 'quarterly' ? t('w3.tele.delta.prevQuarter')
          : safeViewMode === 'annual' ? t('w3.tele.delta.prevYear')
            : dataMode === 'weekly' || safeViewMode === 'step-weekly'
              ? t('w3.tele.delta.prevWeek')
              : safeViewMode === 'period-weekly'
                ? t('w3.tele.delta.prevReport')
                : indicator?.frequency === 'quarterly'
                  ? t('w3.tele.delta.prevQuarter')
                  : isPriceCategory
                    ? t('w3.tele.delta.prevMonth')
                    : t('w3.tele.delta.prevValue');

  const currentValue = heroOverride ? indicator.hero_value
    : (s?.currentValue ?? adj(indicator?.current_value));
  const heroUnit = heroOverride ? (indicator.hero_unit || '%') : displayUnit;
  const valueDigits = chartValueDigits(unit, safeViewMode === 'step-weekly' ? 'step-weekly' : dataMode);
  const previousValue = s?.previousValue ?? indicator?.previous_value;
  const pctChange = unit === 'индекс' && previousValue && !heroOverride
    ? +(((s?.currentValue ?? adj(indicator?.current_value)) - previousValue) / previousValue * 100).toFixed(2)
    : undefined;

  const currentDate = s?.currentDate ?? indicator?.current_date;
  const currentMeta = dataMode === 'weekly' && Number(s?.currentValue) === 0
    ? t('w3.tele.flatPrices', { date: formatDate(currentDate, dateFmt, locale) })
    : periodPhrase(t, currentDate, dateFmt, locale);
  const firstYear = firstDate ? new Date(firstDate).getUTCFullYear() : null;

  return (
    <section className="fe-tele-section">
      <div className="fe-tele-grid">
        <TelemetryCard
          label={currentLabel}
          value={currentValue}
          unit={heroUnit}
          valueDigits={valueDigits}
          change={heroOverride ? undefined : (s?.change ?? indicator?.change)}
          pctChange={heroOverride ? undefined : pctChange}
          meta={currentMeta}
          delay={0}
          deltaSuffix={deltaSuffix}
          polarity={polarity}
        />
        <TelemetryCard
          label={previousLabel}
          value={s?.previousValue ?? adj(indicator?.previous_value)}
          unit={displayUnit}
          valueDigits={valueDigits}
          meta={periodPhrase(t, s?.previousDate ?? cpiPrevDate, dateFmt, locale)}
          delay={1}
        />
        {(s?.highest || stats?.highest) && (
          <TelemetryCard
            label={t('w3.tele.max')}
            value={s?.highest?.value ?? adj(stats?.highest?.value)}
            unit={displayUnit}
            valueDigits={valueDigits}
            meta={periodPhrase(t, s?.highest?.date ?? stats?.highest?.date, dateFmt, locale)
              ? t('w3.tele.peakOn', { date: formatDate(s?.highest?.date ?? stats?.highest?.date, dateFmt, locale) })
              : undefined}
            delay={2}
          />
        )}
        {(s?.average != null || stats?.average != null) && (
          <TelemetryCard
            label={t('w3.tele.avg')}
            value={s?.average ?? adj(stats?.average)}
            unit={displayUnit}
            valueDigits={valueDigits}
            meta={firstYear ? t('w3.tele.dataSince', { year: firstYear }) : undefined}
            delay={3}
          />
        )}
      </div>
    </section>
  );
}
