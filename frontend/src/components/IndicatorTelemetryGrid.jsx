import { formatDate } from '../lib/format';
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
  safeViewMode,
  cpiPrevDate,
  adj,
  loading,
}) {
  const unit = indicator?.unit || '%';

  if (loading) {
    return (
      <section className="mb-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <SkeletonBox key={i} className="h-48 rounded-[2rem]" />
          ))}
        </div>
      </section>
    );
  }

  const currentLabel = safeViewMode === 'weekly' ? 'Инфляция за неделю'
    : safeViewMode === 'cpi' && isPriceCategory ? 'Прирост за месяц'
      : 'Текущее значение';

  const previousLabel = safeViewMode === 'weekly' ? 'Предыдущая неделя'
    : safeViewMode === 'quarterly' ? 'Предыдущий квартал'
      : safeViewMode === 'annual' ? 'Год назад'
        : isPriceCategory ? 'Предыдущий месяц' : 'Предыдущее значение';

  const deltaSuffix = safeViewMode === 'quarterly' ? 'к пред. кварталу'
    : safeViewMode === 'annual' ? 'к пред. значению'
      : safeViewMode === 'weekly' ? 'к пред. неделе'
        : indicator?.frequency === 'quarterly' ? 'к пред. кварталу'
          : isPriceCategory ? 'к пред. месяцу' : 'к пред. значению';

  const currentValue = s?.currentValue ?? adj(indicator?.current_value);
  const previousValue = s?.previousValue ?? indicator?.previous_value;
  const pctChange = indicator?.unit === 'индекс' && previousValue
    ? +(((currentValue) - previousValue) / previousValue * 100).toFixed(2)
    : undefined;

  const currentDate = s?.currentDate ?? indicator?.current_date;
  const currentMeta = safeViewMode === 'weekly' && Number(s?.currentValue) === 0
    ? `ДАТА: ${formatDate(currentDate, 'full')} · ЦЕНЫ БЕЗ ИЗМЕНЕНИЙ`
    : `ДАТА: ${formatDate(currentDate, 'full')}`;

  return (
    <section className="mb-12">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <TelemetryCard
          label={currentLabel}
          value={currentValue}
          unit={unit}
          change={s?.change ?? indicator?.change}
          pctChange={pctChange}
          meta={currentMeta}
          delay={0}
          deltaSuffix={deltaSuffix}
        />
        <TelemetryCard
          label={previousLabel}
          value={s?.previousValue ?? adj(indicator?.previous_value)}
          unit={unit}
          meta={`ДАТА: ${formatDate(s?.previousDate ?? cpiPrevDate, 'full')}`}
          delay={1}
        />
        {(s?.highest || stats?.highest) && (
          <TelemetryCard
            label="Абсолютный максимум"
            value={s?.highest?.value ?? adj(stats?.highest?.value)}
            unit={unit}
            meta={`ПИК: ${formatDate(s?.highest?.date ?? stats?.highest?.date, 'full')}`}
            delay={2}
          />
        )}
        {(s?.average != null || stats?.average != null) && (
          <TelemetryCard
            label="Среднее значение"
            value={s?.average ?? adj(stats?.average)}
            unit={unit}
            meta={`НАБЛ.: ${s?.dataCount ?? stats?.data_count} ПЕРИОД.`}
            delay={3}
          />
        )}
      </div>
    </section>
  );
}
