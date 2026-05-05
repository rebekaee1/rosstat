import { Activity } from 'lucide-react';
import ForecastTable from './ForecastTable';

const EMPTY_BOX_CLS = 'h-full min-h-[300px] rounded-[2rem] bg-surface border border-border-subtle border-dashed flex flex-col items-center justify-center gap-3 text-text-tertiary p-8';

function dateFormatFor(chartMode, indicator) {
  if (chartMode === 'quarterly') return 'quarterly';
  if (chartMode === 'annual') return 'annual';
  if (chartMode === 'weekly') return 'weekly';
  if (indicator?.frequency === 'quarterly') return 'quarterly';
  if (indicator?.frequency === 'annual') return 'annual';
  if (indicator?.frequency === 'weekly') return 'weekly';
  return 'full';
}

/**
 * Правая колонка под графиком: таблица прогноза или пустое состояние
 * (выключен переключатель / прогноз недоступен).
 */
export default function IndicatorForecastSection({
  indicator,
  chartMode,
  inflationResp,
  displayForecastData,
  quarterlyForecastData,
  annualForecastResp,
  weeklyForecastData,
  forecastEnabled,
  showForecast,
  hasForecastData,
}) {
  if (forecastEnabled && showForecast && hasForecastData) {
    const forecastData = chartMode === 'quarterly' ? quarterlyForecastData
      : chartMode === 'annual' ? annualForecastResp
        : chartMode === 'weekly' ? weeklyForecastData
          : displayForecastData;

    return (
      <section className="lg:col-span-2">
        <ForecastTable
          mode={chartMode}
          inflation={inflationResp}
          forecastData={forecastData}
          unit={indicator?.unit || '%'}
          dateFormat={dateFormatFor(chartMode, indicator)}
        />
      </section>
    );
  }

  if (forecastEnabled && !showForecast) {
    return (
      <section className="lg:col-span-2">
        <div className="h-full min-h-[300px] rounded-[2rem] bg-surface border border-border-subtle border-dashed flex flex-col items-center justify-center text-text-tertiary p-8">
          <Activity className="w-8 h-8 mb-4 opacity-20" />
          <p className="text-xs font-mono uppercase tracking-widest text-center">
            Включите переключатель «Прогноз», чтобы показать таблицу прогноза
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="lg:col-span-2">
      <div className={EMPTY_BOX_CLS}>
        <Activity className="w-8 h-8 mb-1 opacity-20" />
        <p className="text-sm font-medium text-text-secondary text-center max-w-md">
          Прогноз для этого показателя не рассчитан или недоступен
        </p>
        <p className="text-xs text-center max-w-lg leading-relaxed text-text-tertiary">
          Некоторые режимы показывают только официальный исторический ряд. Если прогноз появится, переключатель станет активным автоматически.
        </p>
      </div>
    </section>
  );
}
