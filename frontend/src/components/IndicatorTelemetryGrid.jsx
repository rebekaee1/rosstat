import { formatDate, resolveDateFormat, chartValueDigits } from '../lib/format';
import { dataModeForUrlMode } from '../lib/cpiViewModeResolve';
import { dataModeForHousingUrlMode } from '../lib/housingViewModeResolve';
import { dataModeForPpiUrlMode } from '../lib/ppiViewModeResolve';
import { useT } from '../i18n';
import TelemetryCard from './TelemetryCard';
import { SkeletonBox } from './Skeleton';

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
}) {
  const t = useT();
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
      <section className="mb-6 md:mb-12">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-6">
          {[...Array(4)].map((_, i) => (
            <SkeletonBox key={i} className="h-28 md:h-48 rounded-2xl md:rounded-[2rem]" />
          ))}
        </div>
      </section>
    );
  }

  const heroOverride = indicator?.hero_value != null && safeViewMode === 'yoy';

  const currentLabel = heroOverride
    ? (indicator.hero_label || t('indicator.telemetry.heroYoy'))
    : safeViewMode === 'yoy' || safeViewMode === 'annual' ? t('indicator.telemetry.yoy')
      : safeViewMode === 'mom' ? t('indicator.telemetry.mom')
        : safeViewMode === 'qoq' ? t('indicator.telemetry.qoq')
          : safeViewMode === 'period-monthly' ? t('indicator.telemetry.periodMonth')
            : safeViewMode === 'period-weekly' ? t('indicator.telemetry.periodWeek')
              : safeViewMode === 'step-monthly' ? t('indicator.telemetry.stepMom')
                : safeViewMode === 'step-weekly' ? t('indicator.telemetry.stepWow')
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

  const deltaSuffix = safeViewMode === 'qoq' ? t('indicator.telemetry.delta.prevQuarter')
    : safeViewMode === 'mom' ? t('indicator.telemetry.delta.prevMonth')
      : safeViewMode === 'yoy' ? t('indicator.telemetry.delta.prevYear')
        : safeViewMode === 'quarterly' ? t('indicator.telemetry.delta.prevQuarter')
          : safeViewMode === 'annual' ? t('indicator.telemetry.delta.prevYear')
            : dataMode === 'weekly' || safeViewMode === 'step-weekly'
              ? t('indicator.telemetry.delta.prevWeek')
              : safeViewMode === 'period-weekly'
                ? t('indicator.telemetry.delta.prevReport')
                : indicator?.frequency === 'quarterly'
                  ? t('indicator.telemetry.delta.prevQuarter')
                  : isPriceCategory
                    ? t('indicator.telemetry.delta.prevMonth')
                    : t('indicator.telemetry.delta.prevValue');

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
    ? t('indicator.telemetry.dateFlat', { date: formatDate(currentDate, dateFmt) })
    : t('indicator.telemetry.date', { date: formatDate(currentDate, dateFmt) });

  return (
    <section className="mb-6 md:mb-12">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-6">
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
        />
        <TelemetryCard
          label={previousLabel}
          value={s?.previousValue ?? adj(indicator?.previous_value)}
          unit={displayUnit}
          valueDigits={valueDigits}
          meta={t('indicator.telemetry.date', {
            date: formatDate(s?.previousDate ?? cpiPrevDate, dateFmt),
          })}
          delay={1}
        />
        {(s?.highest || stats?.highest) && (
          <TelemetryCard
            label={t('indicator.telemetry.max')}
            value={s?.highest?.value ?? adj(stats?.highest?.value)}
            unit={displayUnit}
            valueDigits={valueDigits}
            meta={t('indicator.telemetry.peak', {
              date: formatDate(s?.highest?.date ?? stats?.highest?.date, dateFmt),
            })}
            delay={2}
          />
        )}
        {(s?.average != null || stats?.average != null) && (
          <TelemetryCard
            label={t('indicator.telemetry.avg')}
            value={s?.average ?? adj(stats?.average)}
            unit={displayUnit}
            valueDigits={valueDigits}
            meta={t('indicator.telemetry.obs', {
              count: s?.dataCount ?? stats?.data_count,
            })}
            delay={3}
          />
        )}
      </div>
    </section>
  );
}
