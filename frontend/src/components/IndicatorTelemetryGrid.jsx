import { formatDate, resolveDateFormat, chartValueDigits } from '../lib/format';
import { dataModeForUrlMode } from '../lib/cpiViewModeResolve';
import { dataModeForHousingUrlMode } from '../lib/housingViewModeResolve';
import { dataModeForPpiUrlMode } from '../lib/ppiViewModeResolve';
import TelemetryCard from './TelemetryCard';
import { SkeletonBox } from './Skeleton';

/**
 * Сетка из 4 телеметрических карточек на странице индикатора:
 *   текущее значение, предыдущее, абсолютный максимум, среднее.
 *
 * Карточки максимума и среднего показываются только если для текущего
 * режима известно значение (или из агрегированной статистики `stats`).
 *
 * `viewStats` — это объект с полями {currentValue, previousValue, change,
 * highest, average, dataCount, ...}, посчитанный в текущем режиме.
 * Если в режиме статистики нет — берём fallback из API-полей индикатора.
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
  // Формат даты в карточках = гранулярность отображаемого ряда (тот же
  // резолвер, что у оси графика и таблицы). Квартальный ряд → «I кв. 2026»,
  // годовой → «2026», дневной → «12 марта 2026», месячный → «март 2026».
  const dateFmt = resolveDateFormat({
    chartMode,
    frequency: indicator?.frequency,
    safeViewMode,
  });
  // На режиме «Индекс» CPI-семьи показываем уровень накопленного индекса
  // (значения 100…1000+) — без `%`. Для прочих режимов используем
  // официальную единицу индикатора.
  const dataMode = isPriceCategory
    ? dataModeForUrlMode(safeViewMode)
    : isHousingFamily
      ? dataModeForHousingUrlMode(safeViewMode)
      : isPpiFamily
        ? dataModeForPpiUrlMode(safeViewMode)
        : safeViewMode;

  const unit = String(safeViewMode).startsWith('index')
    && (isPriceCategory || isHousingFamily || isPpiFamily)
    ? 'индекс'
    // Режим «год к году» у индекс-индикаторов (ИПП/ИЦП/жильё) — это проценты,
    // а не уровень индекса: единица «%», иначе значения 10.8 / 8.7 шли без знака.
    : (safeViewMode === 'yoy' && indicator?.hero_value != null)
      ? '%'
      : (indicator?.unit || '%');

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

  // Hero override: backend подставил YoY% (model_config_json.hero_view = "yoy_pct"),
  // потому что для индексных индикаторов абсолютное значение (например IPP 112)
  // не несёт смысловой нагрузки, а изменение г/г (+1.2%) — несёт. Применяем
  // только в режиме «год к году» (это режим по умолчанию у этих карточек):
  // в режимах «индекс»/«м/м»/«к/к» hero не подменяем, иначе верхняя цифра
  // не совпадала бы с графиком.
  const heroOverride = indicator?.hero_value != null && safeViewMode === 'yoy';

  const currentLabel = heroOverride ? (indicator.hero_label || 'Изменение г/г')
    : safeViewMode === 'yoy' ? 'Год к году'
      : safeViewMode === 'mom' ? 'Месяц к месяцу'
        : safeViewMode === 'qoq' ? 'Квартал к кварталу'
        : safeViewMode === 'period-monthly' ? 'Рост за месяц'
          : safeViewMode === 'period-weekly' ? 'С начала месяца'
            : safeViewMode === 'step-monthly' ? 'Изменение м/м'
              : safeViewMode === 'step-weekly' ? 'Изменение н/н'
                : dataMode === 'weekly' ? 'Инфляция за неделю'
                  : dataMode === 'cpi' && isPriceCategory ? 'Прирост за месяц'
                    : 'Текущее значение';

  const previousLabel = dataMode === 'weekly' || safeViewMode === 'step-weekly'
    || safeViewMode === 'period-weekly'
    ? 'Предыдущая неделя'
    : safeViewMode === 'qoq' ? 'Предыдущий квартал'
      : safeViewMode === 'mom' ? 'Предыдущий месяц'
        // В режиме г/г вторая карточка — это предыдущая точка того же (г/г) ряда,
        // т.е. предыдущий период, а не «тот же период год назад» (последнее
        // путало: подпись говорила «год назад», а дата была прошлого квартала).
        : safeViewMode === 'yoy'
          ? (indicator?.frequency === 'quarterly' ? 'Предыдущий квартал'
            : indicator?.frequency === 'annual' ? 'Предыдущий год'
              : 'Предыдущий месяц')
        : safeViewMode === 'quarterly' ? 'Предыдущий квартал'
          : safeViewMode === 'annual' ? 'Год назад'
            : isHousingFamily ? 'Предыдущий квартал'
              : isPriceCategory ? 'Предыдущий месяц' : 'Предыдущее значение';

  const deltaSuffix = safeViewMode === 'qoq' ? 'к пред. кварталу'
    : safeViewMode === 'mom' ? 'к пред. месяцу'
      : safeViewMode === 'yoy' ? 'к пред. году'
      : safeViewMode === 'quarterly' ? 'к пред. кварталу'
        : safeViewMode === 'annual' ? 'к пред. значению'
          : dataMode === 'weekly' || safeViewMode === 'step-weekly' ? 'к пред. неделе'
            : safeViewMode === 'period-weekly' ? 'к прошлому отчёту'
            : indicator?.frequency === 'quarterly' ? 'к пред. кварталу'
              : isPriceCategory ? 'к пред. месяцу' : 'к пред. значению';

  const currentValue = heroOverride ? indicator.hero_value
    : (s?.currentValue ?? adj(indicator?.current_value));
  const heroUnit = heroOverride ? (indicator.hero_unit || '%') : unit;
  const valueDigits = chartValueDigits(unit, safeViewMode === 'step-weekly' ? 'step-weekly' : dataMode);
  const previousValue = s?.previousValue ?? indicator?.previous_value;
  const pctChange = indicator?.unit === 'индекс' && previousValue && !heroOverride
    ? +(((s?.currentValue ?? adj(indicator?.current_value)) - previousValue) / previousValue * 100).toFixed(2)
    : undefined;

  const currentDate = s?.currentDate ?? indicator?.current_date;
  const currentMeta = dataMode === 'weekly' && Number(s?.currentValue) === 0
    ? `ДАТА: ${formatDate(currentDate, dateFmt)} · ЦЕНЫ БЕЗ ИЗМЕНЕНИЙ`
    : `ДАТА: ${formatDate(currentDate, dateFmt)}`;

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
          unit={unit}
          valueDigits={valueDigits}
          meta={`ДАТА: ${formatDate(s?.previousDate ?? cpiPrevDate, dateFmt)}`}
          delay={1}
        />
        {(s?.highest || stats?.highest) && (
          <TelemetryCard
            label="Абсолютный максимум"
            value={s?.highest?.value ?? adj(stats?.highest?.value)}
            unit={unit}
            valueDigits={valueDigits}
            meta={`ПИК: ${formatDate(s?.highest?.date ?? stats?.highest?.date, dateFmt)}`}
            delay={2}
          />
        )}
        {(s?.average != null || stats?.average != null) && (
          <TelemetryCard
            label="Среднее значение"
            value={s?.average ?? adj(stats?.average)}
            unit={unit}
            valueDigits={valueDigits}
            meta={`НАБЛ.: ${s?.dataCount ?? stats?.data_count} ПЕРИОД.`}
            delay={3}
          />
        )}
      </div>
    </section>
  );
}
