import { useEffect, useRef } from 'react';
import { Activity } from 'lucide-react';
import ForecastTable from './ForecastTable';
import { track, events } from '../lib/track';

const EMPTY_BOX_CLS = 'h-full min-h-[300px] rounded-[2rem] bg-surface border border-border-subtle border-dashed flex flex-col items-center justify-center gap-3 text-text-tertiary p-8';

/**
 * `forecast_view` — цель «пользователь действительно увидел блок прогноза».
 * Срабатывает один раз на mount-видимость секции через IntersectionObserver
 * (≥40% площади в viewport). На устройствах без IO падает в no-op — это
 * совместимо со старыми WebView и Webvisor 2 не теряет основного goal.
 */
function useForecastView({ indicatorCode, indicatorCategory, chartMode, hasForecastData, showForecast }) {
  const ref = useRef(null);
  const firedRef = useRef(false);

  useEffect(() => {
    firedRef.current = false;
  }, [indicatorCode]);

  useEffect(() => {
    if (firedRef.current) return undefined;
    if (!hasForecastData || !showForecast) return undefined;
    if (!indicatorCode) return undefined;
    if (typeof window === 'undefined' || typeof window.IntersectionObserver !== 'function') return undefined;

    const node = ref.current;
    if (!node) return undefined;

    const io = new window.IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting && entry.intersectionRatio >= 0.4 && !firedRef.current) {
          firedRef.current = true;
          track(events.FORECAST_VIEW, {
            indicator: indicatorCode,
            indicatorCategory,
            chartMode,
          });
          io.disconnect();
        }
      }
    }, { threshold: [0, 0.25, 0.4, 0.6, 1] });

    io.observe(node);
    return () => io.disconnect();
  }, [indicatorCode, indicatorCategory, chartMode, hasForecastData, showForecast]);

  return ref;
}

function dateFormatFor(chartMode, indicator, safeViewMode) {
  if (chartMode === 'quarterly' || chartMode === 'qoq') return 'quarterly';
  if (chartMode === 'annual') return 'annual';
  if (chartMode === 'weekly') return 'weekly';
  // Индексные подрежимы фильтруют прогноз до концов кварталов/годов —
  // подписи дат должны соответствовать гранулярности.
  if (chartMode === 'index') {
    if (safeViewMode === 'index-quarterly') return 'quarterly';
    if (safeViewMode === 'index-annual') return 'annual';
  }
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
  safeViewMode,
  inflationResp,
  displayForecastData,
  quarterlyForecastData,
  annualForecastResp,
  yoyForecastData,
  qoqForecastData,
  periodMonthlyForecastData,
  periodWeeklyForecastData,
  forecastEnabled,
  showForecast,
  hasForecastData,
}) {
  const viewRef = useForecastView({
    indicatorCode: indicator?.code,
    indicatorCategory: indicator?.category,
    chartMode,
    hasForecastData,
    showForecast,
  });

  if (forecastEnabled && showForecast && hasForecastData) {
    const forecastData = chartMode === 'quarterly' ? quarterlyForecastData
      : chartMode === 'annual' ? annualForecastResp
        : chartMode === 'yoy' ? yoyForecastData
          : chartMode === 'qoq' ? qoqForecastData
            : chartMode === 'period-weekly' ? periodWeeklyForecastData
              : chartMode === 'period-monthly' ? periodMonthlyForecastData
                : displayForecastData;

    return (
      <section ref={viewRef} className="lg:col-span-2">
        <ForecastTable
          mode={chartMode}
          inflation={inflationResp}
          forecastData={forecastData}
          unit={chartMode === 'index' ? 'индекс' : (indicator?.unit || '%')}
          dateFormat={dateFormatFor(chartMode, indicator, safeViewMode)}
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
