import { formatDate, resolveDateFormat, chartValueDigits, unitDigitsKnown } from '../lib/format';
import { cpiInflationGranularity, dataModeForUrlMode } from '../lib/cpiViewModeResolve';
import { dataModeForHousingUrlMode } from '../lib/housingViewModeResolve';
import { dataModeForPpiUrlMode } from '../lib/ppiViewModeResolve';
import { indicatorPolarity } from '../lib/deltaTone';
import { glueDate, periodPhrase, sincePhrase } from '../lib/periodPhrase';
import {
  bestGrowth, dataDigitsOf, formatTileValue, isGrowthBaseReliable, sameYearChange, unitKind, windowStats,
} from '../lib/indicatorSummary';
import { pluralRu } from '../lib/worldApi';
import { valueDigitsFor } from '../lib/seriesDigits';
import { visibleRangeStats } from '../lib/rangeStats';
import { useLocale, useT } from '../i18n';
import TelemetryCard from './TelemetryCard';
import { SkeletonBox } from './Skeleton';
import '../styles/indicator-russia.css';
import '../styles/x2-indicator.css';

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
  points = null,
  windowPoints = null,
  visibleRows = null,
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

  // «К соотв. периоду пред. года» по кварталам/годам: предыдущая точка это прошлый квартал или прошлый год, а не месяц (круг 9, Y10).
  const bucket = isPriceCategory ? cpiInflationGranularity(safeViewMode) : null;
  const previousLabel = bucket === 'quarter' ? t('indicator.telemetry.prevQuarter')
    : bucket === 'year' ? t('indicator.telemetry.prevYear')
    : dataMode === 'weekly' || safeViewMode === 'step-weekly'
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

  const deltaSuffix = bucket === 'quarter' ? t('w3.tele.delta.prevQuarter')
    : bucket === 'year' ? t('w3.tele.delta.prevYear')
    : safeViewMode === 'qoq' ? t('w3.tele.delta.prevQuarter')
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
  const unitDefaultDigits = chartValueDigits(unit, safeViewMode === 'step-weekly' ? 'step-weekly' : dataMode);
  // Единица без своей настройки точности («тыс. поездок», «мест»): знаков столько, сколько в самих данных — счётчики без «,00».
  // Счётные единицы: точность по фактическим точкам (общая с графиком и таблицей, `valueDigitsFor`), остальные как были.
  const countDigits = Array.isArray(points) && points.length
    ? valueDigitsFor(unit, points.map((point) => point.value), dataMode)
    : unitDefaultDigits;
  const baseDigits = countDigits !== unitDefaultDigits
    ? countDigits
    : (unitDigitsKnown(unit) || !Array.isArray(points) || !points.length
      ? unitDefaultDigits
      : Math.min(unitDefaultDigits, dataDigitsOf(points)));
  // Крупное число карточки укрупняется так же, как в шапке («7,8 млн поездок», а не «7 770,92 тыс. поездок»),
  // и все карточки сетки (предыдущее, максимум, среднее, изменение) показываются в той же единице.
  const big = !heroOverride && !isIndexUnit && unit !== '%' && currentValue != null
    ? formatTileValue(currentValue, unit, { locale })
    : null;
  const scale = big?.compacted ? big : null;
  const sv = (v) => (scale && v != null && Number.isFinite(Number(v)) ? Number(v) / scale.div : v);
  const cardUnit = scale ? scale.unit : displayUnit;
  const valueDigits = scale ? scale.digits : baseDigits;
  const currentDate = s?.currentDate ?? indicator?.current_date;
  const currentMeta = dataMode === 'weekly' && Number(s?.currentValue) === 0
    ? t('w3.tele.flatPrices', { date: formatDate(currentDate, dateFmt, locale) })
    : periodPhrase(t, currentDate, dateFmt, locale);
  const firstYear = firstDate ? new Date(firstDate).getUTCFullYear() : null;

  // Среднее и «исторический максимум» у денег, индексов и объёмов ничего не говорят: вместо них рост за год и за десять лет.
  const growthMode = Array.isArray(points) && points.length > 1 && unitKind(unit) !== 'rate';
  // «К году» — тот же период прошлого года (II кв. к II кв.), без допуска в четыре месяца.
  const yearGrowth = growthMode ? sameYearChange(points, indicator?.frequency) : null;
  // «Рост за 10 лет» только от надёжной базы: не от почти нуля и не от точки у пропуска в ряду (Турция «1 676 %», Греция «−98,7 %»).
  const rawLong = growthMode ? bestGrowth(points) : null;
  const longGrowth = rawLong && isGrowthBaseReliable(points, rawLong, indicator?.frequency) ? rawLong : null;
  // Подпись называет базовый период: «К II кв. 2016»; у месячных рядов «Рост с августа 2016» (падеж).
  const baseDate = (fmt) => glueDate(formatDate(longGrowth.from.date, fmt, locale));
  const longLabel = !longGrowth ? '' : (dateFmt === 'quarterly' || dateFmt === 'annual' || dateFmt === 'day' || dateFmt === 'weekly'
    ? t('kt1_tile_toBase', { date: baseDate(dateFmt) })
    : t('kt1_tile_sinceBase', { date: baseDate(dateFmt === 'full' ? 'fullGen' : dateFmt) }));
  // Максимум и среднее за всю историю (в России это 1990-е, «2 508 %») ничего не говорят: у ряда длиннее десяти лет берём последние десять.
  const win = !growthMode && Array.isArray(windowPoints) ? windowStats(windowPoints, 10) : null;
  const tenYears = win && win.years >= 10 ? win : null;
  // Окно сужено переключателем над графиком: максимум и среднее считаются по выбранному периоду (круг 11, U16).
  const chosen = !growthMode ? visibleRangeStats(visibleRows, windowPoints) : null;
  const windowed = chosen || tenYears;
  // Подпись карточки: у сужённого окна год в нужной форме («за 5 лет», «за 1 год»), у окна короче года «за выбранный период».
  const windowLabel = (kind) => {
    if (!chosen) return t(kind === 'max' ? 'c9c.tele.maxWindow' : 'c9c.tele.avgWindow', { n: windowed.years });
    if (chosen.years < 1) return t(`c11f.tele.${kind}Range`);
    const form = locale === 'en'
      ? (chosen.years === 1 ? 'one' : 'many')
      : pluralRu(chosen.years, ['one', 'few', 'many']);
    return t(`c11f.tele.${kind}.${form}`, { n: chosen.years });
  };

  // «Текущее значение» повторяет число шапки: его убрали. Остаются карточки с названием преобразования («Год к году»), у которых своё число.
  const showCurrent = heroOverride || currentLabel !== t('indicator.telemetry.current');

  return (
    <section className="fe-tele-section">
      <div className="fe-tele-grid">
        {showCurrent && (
          <TelemetryCard
            label={currentLabel}
            value={sv(currentValue)}
            unit={scale ? cardUnit : heroUnit}
            valueDigits={valueDigits}
            meta={currentMeta}
            delay={0}
            deltaSuffix={deltaSuffix}
            polarity={polarity}
          />
        )}
        <TelemetryCard
          label={previousLabel}
          value={sv(s?.previousValue ?? adj(indicator?.previous_value))}
          unit={cardUnit}
          valueDigits={valueDigits}
          meta={periodPhrase(t, s?.previousDate ?? cpiPrevDate, dateFmt, locale)}
          delay={1}
        />
        {growthMode && yearGrowth && (
          <TelemetryCard
            label={t('w6e.tile.yearChange')}
            value={yearGrowth.pct}
            unit="%"
            valueDigits={Math.abs(yearGrowth.pct) >= 100 ? 0 : 1}
            meta={sincePhrase(t, yearGrowth.from.date, dateFmt, locale)}
            delay={2}
          />
        )}
        {growthMode && longGrowth && (
          <TelemetryCard
            label={longLabel}
            value={longGrowth.pct}
            unit="%"
            valueDigits={Math.abs(longGrowth.pct) >= 100 ? 0 : 1}
            delay={3}
          />
        )}
        {!growthMode && (windowed || s?.highest || stats?.highest) && (
          <TelemetryCard
            label={windowed ? windowLabel('max') : t('w3.tele.max')}
            value={sv(windowed ? windowed.highest.value : (s?.highest?.value ?? adj(stats?.highest?.value)))}
            unit={cardUnit}
            valueDigits={valueDigits}
            meta={periodPhrase(t, windowed ? windowed.highest.date : (s?.highest?.date ?? stats?.highest?.date), dateFmt, locale)
              ? t('w3.tele.peakOn', { date: glueDate(formatDate(windowed ? windowed.highest.date : (s?.highest?.date ?? stats?.highest?.date), dateFmt, locale)) })
              : undefined}
            delay={2}
          />
        )}
        {!growthMode && (windowed || s?.average != null || stats?.average != null) && (
          <TelemetryCard
            label={windowed ? windowLabel('avg') : t('w3.tele.avg')}
            value={sv(windowed ? windowed.average : (s?.average ?? adj(stats?.average)))}
            unit={cardUnit}
            valueDigits={valueDigits}
            meta={windowed ? undefined : (firstYear ? t('w3.tele.dataSince', { year: firstYear }) : undefined)}
            delay={3}
          />
        )}
      </div>
    </section>
  );
}
