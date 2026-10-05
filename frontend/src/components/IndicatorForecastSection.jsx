import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Activity } from 'lucide-react';
import ForecastTable from './ForecastTable';
import Button from './Button';
import { comparePath, russiaCategoriesPath, russiaIndicatorPath } from '../lib/sitePaths';
import '../styles/indicator-russia.css';
import '../styles/x2-indicator.css';
import { track, events } from '../lib/track';
import { useT } from '../i18n';
import { chartSeriesForViewMode } from '../lib/chartSeriesForViewMode';

const SOFT = { '--fe-duration': '0.35s', '--fe-rise': '10px' };

// Страница без прогноза не заканчивается тупиком: у курса валюты рядом стоят другие курсы и нефть, у остальных сравнение.
const RELATED_PAIRS = Object.freeze({
  'usd-rub': ['eur-rub', 'cny-rub', 'brent'],
  'eur-rub': ['usd-rub', 'cny-rub', 'brent'],
  'cny-rub': ['usd-rub', 'eur-rub', 'brent'],
});

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
  isUnemploymentFamily = false,
  dataPoints,
  momDataPoints,
  quarterlyDataPoints,
  annualDataPoints,
  weeklyDataPoints,
  yoyDataPoints,
  qoqDataPoints,
  periodMonthlyDataPoints,
  periodWeeklyDataPoints,
  inflationResp,
  displayForecastData,
  quarterlyForecastData,
  annualForecastResp,
  yoyForecastData,
  qoqForecastData,
  momForecastData,
  periodMonthlyForecastData,
  periodWeeklyForecastData,
  forecastEnabled,
  showForecast,
  hasForecastData,
}) {
  const t = useT();
  const actualPoints = chartSeriesForViewMode({
    chartMode, isUnemploymentFamily, dataPoints, momDataPoints,
    quarterlyDataPoints, annualDataPoints, weeklyDataPoints,
    yoyDataPoints, qoqDataPoints, periodMonthlyDataPoints, periodWeeklyDataPoints,
  });
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
            : chartMode === 'mom' ? momForecastData
              : chartMode === 'period-weekly' ? periodWeeklyForecastData
                : chartMode === 'period-monthly' ? periodMonthlyForecastData
                  : displayForecastData;

    return (
      <section ref={viewRef} data-block="forecast" className="min-w-0">
        <ForecastTable
          mode={chartMode}
          inflation={inflationResp}
          forecastData={forecastData}
          actualPoints={actualPoints}
          unit={chartMode === 'index' ? 'индекс' : (indicator?.unit || '%')}
          dateFormat={dateFormatFor(chartMode, indicator, safeViewMode)}
        />
      </section>
    );
  }

  if (forecastEnabled && !showForecast) {
    return (
      <section data-block="forecast-empty" className="fe-reveal fe-reveal--free fe-note-card" style={SOFT}>
        <span className="fe-note-card__icon" aria-hidden="true"><Activity className="h-5 w-5" /></span>
        <div className="fe-note-card__body">
          <p className="fe-note-card__title">{t('w3.forecast.offTitle')}</p>
          <p className="fe-note-card__text">{t('w3.forecast.offBody')}</p>
        </div>
      </section>
    );
  }

  return (
    <section data-block="forecast-empty" className="fe-reveal fe-reveal--free fe-note-card" style={SOFT}>
      <span className="fe-note-card__icon" aria-hidden="true"><Activity className="h-5 w-5" /></span>
      <div className="fe-note-card__body">
        <p className="fe-note-card__title">{t('w3.forecast.emptyTitle')}</p>
        <p className="fe-note-card__text">{t('w3.forecast.emptyBody')}</p>
      </div>
      <div className="fe-note-card__cta fe-note-card__actions">
        {(RELATED_PAIRS[indicator?.code] || []).map((pair) => (
          <Button key={pair} as={Link} to={russiaIndicatorPath(pair)} variant="secondary" size="sm">
            {t(`w6e.pair.${pair}`)}
          </Button>
        ))}
        {indicator?.code && (
          <Button as={Link} to={`${comparePath()}?codes=${encodeURIComponent(indicator.code)}`} variant="secondary" size="sm">
            {t('w6e.pair.compare')}
          </Button>
        )}
        <Button as={Link} to={russiaCategoriesPath()} variant="ghost" size="sm">
          {t('w3.forecast.emptyCta')}
        </Button>
      </div>
    </section>
  );
}
