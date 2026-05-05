import { useMemo } from 'react';
import { useIndicatorData, useInflation, useForecast } from './hooks';
import { isCpiIndex, adjustCpiForecastDisplay } from './format';

const CPI_DERIVED_CODES = {
  cpi: { quarterly: 'inflation-quarterly', annual: 'inflation-annual' },
  'cpi-food': { quarterly: 'cpi-food-quarterly', annual: 'cpi-food-annual' },
  'cpi-nonfood': { quarterly: 'cpi-nonfood-quarterly', annual: 'cpi-nonfood-annual' },
  'cpi-services': { quarterly: 'cpi-services-quarterly', annual: 'cpi-services-annual' },
};

const CPI_CODES = ['cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services'];

function statsFromPoints(points) {
  if (!points?.length) return null;
  const current = points[points.length - 1];
  const previous = points.length > 1 ? points[points.length - 2] : null;
  const highest = points.reduce((max, p) => (p.value > max.value ? p : max), points[0]);
  const avg = points.reduce((sum, p) => sum + p.value, 0) / points.length;
  return {
    currentValue: current.value,
    currentDate: current.date,
    previousValue: previous?.value,
    previousDate: previous?.date,
    change: previous ? current.value - previous.value : null,
    highest: { value: highest.value, date: highest.date },
    average: avg,
    dataCount: points.length,
  };
}

/**
 * Хук, инкапсулирующий всю режим-зависимую логику страницы индикатора:
 *   - какой ряд показывать на графике (основной / квартальный / годовой / недельный / накопленная инфляция)
 *   - какой прогноз показывать
 *   - какую статистику считать для телеметрических карточек
 *   - что считать «загрузкой» в текущем режиме
 *
 * Контракт прежний — компонент IndicatorDetail отдаёт точно те же данные
 * во все нижестоящие компоненты, что и до рефактора.
 */
export default function useIndicatorViewModeData({ code, viewMode }) {
  const isPriceCategory = CPI_CODES.includes(code);

  // Защита от устаревших ?mode=... в URL: 'weekly' только у общего `cpi`,
  // остальные режимы либо недоступны на текущем коде, либо валидны как `inflation`.
  const ALLOWED_MODES = ['inflation', 'cpi', 'quarterly', 'annual', 'weekly', 'index'];
  const fallbackMode = !ALLOWED_MODES.includes(viewMode) ? 'inflation' : viewMode;
  const safeViewMode = isPriceCategory && code !== 'cpi' && fallbackMode === 'weekly'
    ? 'inflation'
    : fallbackMode;

  // На режиме `index` показываем сырой индекс (значения вокруг 100) — не
  // нужно вычитать 100. На остальных режимах CPI-семейства — стандартное
  // преобразование к шкале «delta % от 100».
  const shouldSubtract100 = isCpiIndex(code) && safeViewMode !== 'index';
  const cpiDerivedCodes = CPI_DERIVED_CODES[code] || {};
  const chartMode = isPriceCategory ? safeViewMode : 'cpi';

  // Основной ряд индикатора + прогноз (всегда нужны).
  const {
    data: dataResp,
    isLoading: loadingData,
    isError: dataError,
    refetch: refetchData,
    isFetching: fetchingData,
  } = useIndicatorData(code);

  const {
    data: inflationResp,
    isLoading: loadingInflation,
    refetch: refetchInflation,
  } = useInflation(code, { enabled: isPriceCategory });

  const { data: forecastResp, refetch: refetchForecast } = useForecast(code);

  // Производные ряды CPI — подгружаются только в соответствующих режимах.
  const { data: quarterlyForecastResp } = useForecast(cpiDerivedCodes.quarterly, {
    enabled: !!cpiDerivedCodes.quarterly && safeViewMode === 'quarterly',
  });
  const { data: annualForecastResp } = useForecast(cpiDerivedCodes.annual, {
    enabled: !!cpiDerivedCodes.annual && safeViewMode === 'annual',
  });
  const {
    data: quarterlyResp,
    isLoading: loadingQuarterly,
  } = useIndicatorData(cpiDerivedCodes.quarterly, undefined, {
    enabled: !!cpiDerivedCodes.quarterly && safeViewMode === 'quarterly',
  });
  const {
    data: annualResp,
    isLoading: loadingAnnual,
  } = useIndicatorData(cpiDerivedCodes.annual, undefined, {
    enabled: !!cpiDerivedCodes.annual && safeViewMode === 'annual',
  });
  const {
    data: weeklyResp,
    isLoading: loadingWeekly,
  } = useIndicatorData('inflation-weekly', undefined, {
    enabled: code === 'cpi' && safeViewMode === 'weekly',
  });
  const { data: weeklyForecastResp } = useForecast('inflation-weekly', {
    enabled: code === 'cpi' && safeViewMode === 'weekly',
  });

  const rawDataPoints = useMemo(
    () => (Array.isArray(dataResp?.data) ? dataResp.data : []),
    [dataResp],
  );

  const dataPoints = useMemo(() => {
    if (!shouldSubtract100 || !rawDataPoints.length) return rawDataPoints;
    return rawDataPoints.map((p) => ({ ...p, value: Number(p.value) - 100 }));
  }, [rawDataPoints, shouldSubtract100]);

  const displayForecastData = useMemo(() => {
    if (!shouldSubtract100) return forecastResp;
    return adjustCpiForecastDisplay(forecastResp, code);
  }, [forecastResp, shouldSubtract100, code]);

  const quarterlyForecastData = useMemo(
    () => adjustCpiForecastDisplay(quarterlyForecastResp, cpiDerivedCodes.quarterly),
    [quarterlyForecastResp, cpiDerivedCodes.quarterly],
  );

  const quarterlyDataPoints = useMemo(() => {
    if (!quarterlyResp?.data?.length) return [];
    return quarterlyResp.data.map((p) => ({ ...p, value: Number(p.value) - 100 }));
  }, [quarterlyResp]);

  const annualDataPoints = useMemo(() => {
    if (!annualResp?.data?.length) return [];
    // Один максимально поздний месяц на год, чтобы график «годовой инфляции»
    // был ровным year-over-year рядом без дублей внутри одного года.
    const byYear = new Map();
    for (const p of annualResp.data) {
      const year = String(p.date).slice(0, 4);
      const existing = byYear.get(year);
      if (!existing || String(p.date) > String(existing.date)) {
        byYear.set(year, p);
      }
    }
    return Array.from(byYear.values())
      .sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }, [annualResp]);

  const weeklyDataPoints = useMemo(() => {
    if (!weeklyResp?.data?.length) return [];
    return weeklyResp.data.map((p) => ({ ...p, value: Number(p.value) - 100 }));
  }, [weeklyResp]);

  // Прогноз inflation-weekly приходит в формате CPI-индекса (значения вокруг 100),
  // фронт же показывает delta (value - 100). Преобразуем чтобы прогноз был в той же
  // системе координат, что и actual-точки выше.
  const weeklyForecastData = useMemo(
    () => adjustCpiForecastDisplay(weeklyForecastResp, 'inflation-weekly'),
    [weeklyForecastResp],
  );

  const inflationStats = useMemo(() => {
    if (chartMode !== 'inflation' || !inflationResp?.actuals?.length) return null;
    return statsFromPoints(inflationResp.actuals);
  }, [chartMode, inflationResp]);

  const quarterlyStats = useMemo(
    () => (safeViewMode === 'quarterly' ? statsFromPoints(quarterlyDataPoints) : null),
    [safeViewMode, quarterlyDataPoints],
  );

  const annualStats = useMemo(
    () => (safeViewMode === 'annual' ? statsFromPoints(annualDataPoints) : null),
    [safeViewMode, annualDataPoints],
  );

  const weeklyStats = useMemo(
    () => (safeViewMode === 'weekly' ? statsFromPoints(weeklyDataPoints) : null),
    [safeViewMode, weeklyDataPoints],
  );

  const stats = safeViewMode === 'quarterly' ? quarterlyStats
    : safeViewMode === 'annual' ? annualStats
      : safeViewMode === 'weekly' ? weeklyStats
        : inflationStats;

  const cpiPrevDate = dataPoints.length >= 2
    ? dataPoints[dataPoints.length - 2].date
    : null;

  const chartLoading = chartMode === 'inflation' ? loadingInflation
    : chartMode === 'quarterly' ? loadingQuarterly
      : chartMode === 'annual' ? loadingAnnual
        : chartMode === 'weekly' ? loadingWeekly
          : loadingData;

  const hasForecastData = chartMode === 'quarterly'
    ? quarterlyForecastData?.forecast?.values?.length > 0
    : chartMode === 'annual'
      ? annualForecastResp?.forecast?.values?.length > 0
      : chartMode === 'weekly'
        ? weeklyForecastData?.forecast?.values?.length > 0
        : chartMode === 'inflation'
          ? inflationResp?.forecast?.length > 0
          : displayForecastData?.forecast?.values?.length > 0;

  const forecastEnabled = hasForecastData;

  return {
    isPriceCategory,
    safeViewMode,
    chartMode,
    shouldSubtract100,

    dataPoints,
    inflationResp,
    quarterlyDataPoints,
    annualDataPoints,
    weeklyDataPoints,

    displayForecastData,
    quarterlyForecastData,
    annualForecastResp,
    weeklyForecastData,

    stats,
    cpiPrevDate,

    chartLoading,
    loadingData,
    loadingInflation,
    loadingAnnual,
    loadingWeekly,
    loadingQuarterly,
    dataError,
    fetchingData,
    hasForecastData,
    forecastEnabled,

    refetchData,
    refetchInflation,
    refetchForecast,
  };
}
