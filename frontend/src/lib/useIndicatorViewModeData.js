import { useMemo } from 'react';
import { useIndicatorData, useInflation, useForecast } from './hooks';
import { isCpiIndex, adjustCpiForecastDisplay } from './format';
import {
  dataModeForUrlMode,
  isActiveCpiUrlMode,
  isCpiModeAvailableForCode,
  normalizeCpiViewMode,
  cpiIndexGranularity,
} from './cpiViewModeResolve';
import {
  dataModeForHousingUrlMode,
  HOUSING_CODES,
  housingIndexGranularity,
  isActiveHousingUrlMode,
  normalizeHousingViewMode,
} from './housingViewModeResolve';
import {
  dataModeForPpiUrlMode,
  PPI_CODES,
  isActivePpiUrlMode,
  normalizePpiViewMode,
  ppiIndexGranularity,
} from './ppiViewModeResolve';
import {
  CBR_TERM_SLICE_CODES,
  dataModeForCbrTermSliceUrlMode,
  normalizeCbrTermSliceViewMode,
} from './cbrTermSliceRateResolve';
import {
  UNEMPLOYMENT_ROOT,
  dataModeForUnemploymentUrlMode,
  isUnemploymentFamily,
  normalizeUnemploymentViewMode,
} from './unemploymentViewModeResolve';
import { applyMoMTransform } from './viewModeFamilies';

// Режим Г/г («yoy» в URL) разрешается в `annual` — годовую инфляцию
// «декабрь к декабрю» (одна точка/год); помесячные ряды `cpi-*-yoy` с
// карточки сняты (созвон 2026-06-11), их коды остаются только как
// legacy-редиректы. Недельные режимы есть только у общего ИПЦ — по срезам
// корзины официальной недельной статистики нет.
const CPI_DERIVED_CODES = {
  cpi: {
    quarterly: 'inflation-quarterly',
    annual: 'inflation-annual',
    weekly: 'inflation-weekly',
    qoq: 'cpi-qoq',
    periodMonthly: 'cpi-period-monthly',
    periodWeekly: 'cpi-period-weekly',
  },
  'cpi-food': {
    quarterly: 'cpi-food-quarterly',
    annual: 'cpi-food-annual',
    qoq: 'cpi-food-qoq',
  },
  'cpi-nonfood': {
    quarterly: 'cpi-nonfood-quarterly',
    annual: 'cpi-nonfood-annual',
    qoq: 'cpi-nonfood-qoq',
  },
  'cpi-services': {
    quarterly: 'cpi-services-quarterly',
    annual: 'cpi-services-annual',
    qoq: 'cpi-services-qoq',
  },
};

/** Режимы, где значение в БД уже в % прироста (не индекс 100+). */
const CPI_PERCENT_GROWTH_MODES = new Set([
  'annual', 'yoy', 'qoq', 'period-weekly', 'period-monthly', 'inflation',
]);

const CPI_CODES = ['cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services'];

const HOUSING_DERIVED_CODES = {
  'housing-price-primary': {
    yoy: 'housing-yoy-primary',
    qoq: 'housing-qoq-primary',
    annual: 'housing-annual-primary',
  },
  'housing-price-secondary': {
    yoy: 'housing-yoy-secondary',
    qoq: 'housing-qoq-secondary',
    annual: 'housing-annual-secondary',
  },
};

const PPI_DERIVED_CODES = {
  ppi: {
    yoy: 'ppi-yoy',
    qoq: 'ppi-qoq',
    annual: 'ppi-annual',
  },
};

// Накопленный индекс CPI (режим «Индекс»): база 100 в январе 2000, история
// тянется от первой доступной месячной точки (с 1991 года; правка созвона
// 2026-06-11). Точки до базы достраиваются обратным цепным делением, поэтому
// значения 90-х микроскопические на фоне 100 — это ожидаемо: гиперинфляция
// первой половины 90-х означает, что уровень цен тогда был в тысячи раз ниже
// уровня января 2000 года.
//
// Архитектурное решение (cpi-ppi-migrate): накопленный индекс и его
// квартально-/годовые бакеты остаются client-side display-transform, а НЕ
// backend-derived рядом. Это детерминированное преобразование уже имеющегося
// месячного %-ряда с фиксированной базой — тот же класс, что daily-aggregation
// (ADR-0006: такие трансформации backend derived не заводим). Backend-ряд
// уровня дал бы SARIMA на экспоненте (некорректный прогноз) и не убрал бы
// клиентскую chain-логику прогноза (buildCumulativeIndexForecast всё равно
// продолжает кривую месячным %-прогнозом). Перенос = риск регрессии прогноза
// и десятки sibling-строк при нулевом видимом выигрыше.
const CPI_INDEX_BASE_DATE = '2000-01-01';
const CPI_INDEX_BASE_VALUE = 100;

// До базы значения уровня << 1 — два знака после запятой схлопнули бы их в
// 0.00, поэтому для малых значений сохраняем 4 значащие цифры.
function roundIndexLevel(v) {
  return Math.abs(v) >= 1 ? +v.toFixed(2) : +v.toPrecision(4);
}

function buildCumulativeIndex(rawPoints) {
  if (!Array.isArray(rawPoints) || !rawPoints.length) return [];
  const pts = rawPoints
    .slice()
    .sort((a, b) => String(a.date).localeCompare(String(b.date)));
  let baseIdx = pts.findIndex((p) => String(p.date) >= CPI_INDEX_BASE_DATE);
  if (baseIdx === -1) baseIdx = pts.length - 1;
  const out = new Array(pts.length);
  out[baseIdx] = { ...pts[baseIdx], value: CPI_INDEX_BASE_VALUE };
  let acc = CPI_INDEX_BASE_VALUE;
  for (let i = baseIdx + 1; i < pts.length; i++) {
    acc *= Number(pts[i].value) / 100;
    out[i] = { ...pts[i], value: roundIndexLevel(acc) };
  }
  acc = CPI_INDEX_BASE_VALUE;
  for (let i = baseIdx - 1; i >= 0; i--) {
    // value точки i+1 — это м/м-прирост к месяцу i: уровень(i) = уровень(i+1) / (м/м / 100).
    acc /= Number(pts[i + 1].value) / 100;
    out[i] = { ...pts[i], value: roundIndexLevel(acc) };
  }
  return out;
}

const BUCKET_END_MONTHS = {
  quarter: [3, 6, 9, 12],
  year: [12],
};

/**
 * Точки на конец периода (квартал/год) для индекса-уровня: оставляем только
 * наблюдения завершающего месяца bucket'а. Незавершённый текущий период
 * на график не попадает — «на конец квартала/года» означает именно конец.
 */
function bucketEndPoints(points, granularity) {
  const ends = BUCKET_END_MONTHS[granularity];
  if (!ends || !Array.isArray(points)) return points;
  return points.filter((p) => ends.includes(Number(String(p.date).slice(5, 7))));
}

/** Прогноз для bucket-режимов индекса: только точки на конец квартала/года. */
function filterForecastToBucketEnds(forecastResp, granularity) {
  const values = forecastResp?.forecast?.values;
  if (!values?.length) return forecastResp;
  const ends = BUCKET_END_MONTHS[granularity] ?? [];
  const filtered = values.filter((v) => ends.includes(Number(String(v.date).slice(5, 7))));
  if (!filtered.length) return null;
  return {
    ...forecastResp,
    forecast: { ...forecastResp.forecast, values: filtered },
  };
}

function buildCumulativeIndexForecast(forecastResp, lastActualValue) {
  const values = forecastResp?.forecast?.values;
  if (!values?.length || lastActualValue == null) return forecastResp;
  let acc = lastActualValue;
  let accLow = lastActualValue;
  let accUp = lastActualValue;
  const out = values.map((v) => {
    acc = acc * (Number(v.value) / 100);
    const next = { ...v, value: +acc.toFixed(2) };
    if (v.lower_bound != null) {
      accLow = accLow * (Number(v.lower_bound) / 100);
      next.lower_bound = +accLow.toFixed(2);
    }
    if (v.upper_bound != null) {
      accUp = accUp * (Number(v.upper_bound) / 100);
      next.upper_bound = +accUp.toFixed(2);
    }
    return next;
  });
  return {
    ...forecastResp,
    forecast: { ...forecastResp.forecast, values: out },
  };
}

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
  const isHousingFamily = HOUSING_CODES.includes(code);
  const isPpiFamily = PPI_CODES.includes(code);
  const isCbrTermSliceFamily = CBR_TERM_SLICE_CODES.includes(code);
  const isUnemploymentCanonical = code === UNEMPLOYMENT_ROOT;
  const isLevelRateFamily = isCbrTermSliceFamily;

  const safeViewMode = isPriceCategory
    ? (isActiveCpiUrlMode(viewMode) && isCpiModeAvailableForCode(viewMode, code)
      ? normalizeCpiViewMode(viewMode)
      : 'inflation')
    : isHousingFamily
      ? (isActiveHousingUrlMode(viewMode) ? normalizeHousingViewMode(viewMode) : 'yoy')
      : isPpiFamily
        ? (isActivePpiUrlMode(viewMode) ? normalizePpiViewMode(viewMode) : 'yoy')
        : isCbrTermSliceFamily
          ? normalizeCbrTermSliceViewMode(viewMode)
          : isUnemploymentCanonical
            ? normalizeUnemploymentViewMode(viewMode)
            : viewMode;
  const chartMode = isPriceCategory
    ? dataModeForUrlMode(safeViewMode)
    : isHousingFamily
      ? dataModeForHousingUrlMode(safeViewMode)
      : isPpiFamily
        ? dataModeForPpiUrlMode(safeViewMode)
        : isUnemploymentCanonical
          ? dataModeForUnemploymentUrlMode(safeViewMode)
          : isCbrTermSliceFamily
            ? dataModeForCbrTermSliceUrlMode(safeViewMode)
            : 'cpi';

  // На режиме `index` строим накопленный индекс (база 100 = первая точка
  // ряда от 2000-01) — вычитать 100 не нужно. На остальных режимах
  // CPI-семейства — стандартное преобразование к шкале «delta % от 100».
  const isCumulativeIndex = isCpiIndex(code) && String(safeViewMode).startsWith('index');
  const cpiIndexBucket = isPriceCategory ? cpiIndexGranularity(safeViewMode) : null;
  const ppiIndexBucket = isPpiFamily ? ppiIndexGranularity(safeViewMode) : null;
  const housingIndexBucket = isHousingFamily ? housingIndexGranularity(safeViewMode) : null;
  const shouldSubtract100 = isCpiIndex(code)
    && !CPI_PERCENT_GROWTH_MODES.has(chartMode)
    && !String(safeViewMode).startsWith('index');
  const cpiDerivedCodes = CPI_DERIVED_CODES[code] || {};
  const housingDerivedCodes = HOUSING_DERIVED_CODES[code] || {};
  const ppiDerivedCodes = PPI_DERIVED_CODES[code] || {};
  const modeDerivedCodes = isPriceCategory
    ? cpiDerivedCodes
    : isHousingFamily
      ? housingDerivedCodes
      : isPpiFamily
        ? ppiDerivedCodes
        : {};

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
  const { data: quarterlyForecastResp } = useForecast(modeDerivedCodes.quarterly, {
    enabled: !!modeDerivedCodes.quarterly && chartMode === 'quarterly',
  });
  const { data: annualForecastResp } = useForecast(modeDerivedCodes.annual, {
    enabled: !!modeDerivedCodes.annual && chartMode === 'annual',
  });
  const {
    data: quarterlyResp,
    isLoading: loadingQuarterly,
  } = useIndicatorData(modeDerivedCodes.quarterly, undefined, {
    enabled: !!modeDerivedCodes.quarterly && chartMode === 'quarterly',
  });
  const {
    data: annualResp,
    isLoading: loadingAnnual,
  } = useIndicatorData(modeDerivedCodes.annual, undefined, {
    enabled: !!modeDerivedCodes.annual && chartMode === 'annual',
  });
  const weeklyDerivedCode = modeDerivedCodes.weekly;
  const {
    data: weeklyResp,
    isLoading: loadingWeekly,
  } = useIndicatorData(weeklyDerivedCode, undefined, {
    enabled: !!weeklyDerivedCode && chartMode === 'weekly',
  });
  // Недельный режим — без прогноза (созвон 2026-06-11): показываем только
  // официальный оперативный ряд, прогноз на нём не строим и не запрашиваем.
  const { data: yoyForecastResp } = useForecast(modeDerivedCodes.yoy, {
    enabled: !!modeDerivedCodes.yoy && chartMode === 'yoy',
  });
  const { data: qoqForecastResp } = useForecast(modeDerivedCodes.qoq, {
    enabled: !!modeDerivedCodes.qoq && chartMode === 'qoq',
  });
  const { data: periodMonthlyForecastResp } = useForecast(modeDerivedCodes.periodMonthly, {
    enabled: !!modeDerivedCodes.periodMonthly && chartMode === 'period-monthly',
  });
  const { data: periodWeeklyForecastResp } = useForecast(modeDerivedCodes.periodWeekly, {
    enabled: !!modeDerivedCodes.periodWeekly && chartMode === 'period-weekly',
  });
  const {
    data: yoyResp,
    isLoading: loadingYoy,
  } = useIndicatorData(modeDerivedCodes.yoy, undefined, {
    enabled: !!modeDerivedCodes.yoy && chartMode === 'yoy',
  });
  const {
    data: qoqResp,
    isLoading: loadingQoq,
  } = useIndicatorData(modeDerivedCodes.qoq, undefined, {
    enabled: !!modeDerivedCodes.qoq && chartMode === 'qoq',
  });
  const {
    data: periodMonthlyResp,
    isLoading: loadingPeriodMonthly,
  } = useIndicatorData(modeDerivedCodes.periodMonthly, undefined, {
    enabled: !!modeDerivedCodes.periodMonthly && chartMode === 'period-monthly',
  });
  const {
    data: periodWeeklyResp,
    isLoading: loadingPeriodWeekly,
  } = useIndicatorData(modeDerivedCodes.periodWeekly, undefined, {
    enabled: !!modeDerivedCodes.periodWeekly && chartMode === 'period-weekly',
  });

  const rawDataPoints = useMemo(
    () => (Array.isArray(dataResp?.data) ? dataResp.data : []),
    [dataResp],
  );

  // Месячный накопленный индекс (полный) — нужен и для графика, и как база
  // продолжения прогнозной кривой в bucket-режимах.
  const cumulativeIndexPoints = useMemo(
    () => (isCumulativeIndex && rawDataPoints.length
      ? buildCumulativeIndex(rawDataPoints)
      : null),
    [isCumulativeIndex, rawDataPoints],
  );

  const dataPoints = useMemo(() => {
    if (!rawDataPoints.length) return rawDataPoints;
    if (isCumulativeIndex) {
      return cpiIndexBucket
        ? bucketEndPoints(cumulativeIndexPoints, cpiIndexBucket)
        : cumulativeIndexPoints;
    }
    // ИЦП «Индекс» — ряд уже накопленный (2010=100); по кварталам/годам берём
    // уровень на конец периода.
    if (isPpiFamily && chartMode === 'index' && ppiIndexBucket) {
      return bucketEndPoints(rawDataPoints, ppiIndexBucket);
    }
    // Жильё «Индекс» — квартальный ряд индекса; по годам берём уровень на
    // конец года (последний квартал).
    if (isHousingFamily && chartMode === 'index' && housingIndexBucket) {
      return bucketEndPoints(rawDataPoints, housingIndexBucket);
    }
    if (!shouldSubtract100) return rawDataPoints;
    return rawDataPoints.map((p) => ({ ...p, value: Number(p.value) - 100 }));
  }, [
    rawDataPoints, shouldSubtract100, isCumulativeIndex, cumulativeIndexPoints,
    cpiIndexBucket,
    isPpiFamily, chartMode, ppiIndexBucket, isHousingFamily, housingIndexBucket,
  ]);

  const momDataPoints = useMemo(() => {
    if (!isPpiFamily || chartMode !== 'mom') return [];
    return applyMoMTransform(rawDataPoints);
  }, [isPpiFamily, chartMode, rawDataPoints]);

  const displayForecastData = useMemo(() => {
    if (isCumulativeIndex) {
      // Прогноз режима «Индекс» — продолжение накопленной кривой:
      // последнее накопленное месячное факт-значение × прогнозные месячные / 100.
      const lastActual = cumulativeIndexPoints?.length
        ? cumulativeIndexPoints[cumulativeIndexPoints.length - 1].value
        : null;
      const continued = buildCumulativeIndexForecast(forecastResp, lastActual);
      // По кварталам/годам — только точки на конец завершённых периодов
      // прогнозного горизонта (полные кварталы/годы, без «огрызков»).
      return cpiIndexBucket
        ? filterForecastToBucketEnds(continued, cpiIndexBucket)
        : continued;
    }
    // ИЦП по кварталам/годам — прогноз уровня на конец завершённых периодов.
    if (isPpiFamily && chartMode === 'index' && ppiIndexBucket) {
      return filterForecastToBucketEnds(forecastResp, ppiIndexBucket);
    }
    // Жильё «Индекс по годам» — прогноз уровня на конец завершённых годов.
    // filterForecastToBucketEnds оставляет только точку декабря, поэтому в
    // годовом виде показываем одну прогнозную точку текущего года (без «огрызка»
    // следующего года из квартального хвоста прогноза). Симметрично ИЦП/ИЦП.
    if (isHousingFamily && chartMode === 'index' && housingIndexBucket) {
      return filterForecastToBucketEnds(forecastResp, housingIndexBucket);
    }
    if (!shouldSubtract100) return forecastResp;
    return adjustCpiForecastDisplay(forecastResp, code);
  }, [
    forecastResp, shouldSubtract100, isCumulativeIndex, cumulativeIndexPoints,
    cpiIndexBucket, code,
    isPpiFamily, chartMode, ppiIndexBucket, isHousingFamily, housingIndexBucket,
  ]);

  const quarterlyForecastData = useMemo(
    () => adjustCpiForecastDisplay(quarterlyForecastResp, modeDerivedCodes.quarterly),
    [quarterlyForecastResp, modeDerivedCodes.quarterly],
  );

  const quarterlyDataPoints = useMemo(() => {
    if (!quarterlyResp?.data?.length) return [];
    return quarterlyResp.data.map((p) => ({ ...p, value: Number(p.value) - 100 }));
  }, [quarterlyResp]);

  const annualDataPoints = useMemo(() => {
    if (!annualResp?.data?.length) return [];
    // Backend с 2026-05-06 отдаёт уже агрегированный «декабрь-к-декабрю» ряд:
    // одна точка на 1 января каждого завершённого года, значение — годовая
    // инфляция в %. Никаких клиентских преобразований не нужно.
    return annualResp.data
      .slice()
      .sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }, [annualResp]);

  const weeklyDataPoints = useMemo(() => {
    if (!weeklyResp?.data?.length) return [];
    return weeklyResp.data.map((p) => ({ ...p, value: Number(p.value) - 100 }));
  }, [weeklyResp]);

  const yoyDataPoints = useMemo(() => {
    if (!yoyResp?.data?.length) return [];
    return yoyResp.data.map((p) => ({ ...p, value: Number(p.value) }));
  }, [yoyResp]);

  const qoqDataPoints = useMemo(() => {
    if (!qoqResp?.data?.length) return [];
    return qoqResp.data.map((p) => ({ ...p, value: Number(p.value) }));
  }, [qoqResp]);

  const periodMonthlyDataPoints = useMemo(() => {
    if (!periodMonthlyResp?.data?.length) return [];
    return periodMonthlyResp.data.map((p) => ({ ...p, value: Number(p.value) }));
  }, [periodMonthlyResp]);

  const periodWeeklyDataPoints = useMemo(() => {
    if (!periodWeeklyResp?.data?.length) return [];
    return periodWeeklyResp.data.map((p) => ({ ...p, value: Number(p.value) }));
  }, [periodWeeklyResp]);

  const yoyForecastData = useMemo(() => yoyForecastResp, [yoyForecastResp]);
  const qoqForecastData = useMemo(() => qoqForecastResp, [qoqForecastResp]);
  const periodMonthlyForecastData = useMemo(
    () => periodMonthlyForecastResp,
    [periodMonthlyForecastResp],
  );
  const periodWeeklyForecastData = useMemo(
    () => periodWeeklyForecastResp,
    [periodWeeklyForecastResp],
  );

  const inflationStats = useMemo(() => {
    if (chartMode !== 'inflation' || !inflationResp?.actuals?.length) return null;
    return statsFromPoints(inflationResp.actuals);
  }, [chartMode, inflationResp]);

  const quarterlyStats = useMemo(
    () => (chartMode === 'quarterly' ? statsFromPoints(quarterlyDataPoints) : null),
    [chartMode, quarterlyDataPoints],
  );

  const annualStats = useMemo(
    () => (chartMode === 'annual' ? statsFromPoints(annualDataPoints) : null),
    [chartMode, annualDataPoints],
  );

  const weeklyStats = useMemo(
    () => (chartMode === 'weekly' ? statsFromPoints(weeklyDataPoints) : null),
    [chartMode, weeklyDataPoints],
  );

  const momStats = useMemo(
    () => (chartMode === 'mom' ? statsFromPoints(momDataPoints) : null),
    [chartMode, momDataPoints],
  );

  const indexStats = useMemo(
    () => ((isCumulativeIndex || ((isHousingFamily || isPpiFamily) && chartMode === 'index'))
      ? statsFromPoints(dataPoints)
      : null),
    [isCumulativeIndex, isHousingFamily, isPpiFamily, chartMode, dataPoints],
  );

  const monthlyStats = useMemo(
    () => (chartMode === 'cpi' ? statsFromPoints(dataPoints) : null),
    [chartMode, dataPoints],
  );

  const levelStats = useMemo(
    () => (isLevelRateFamily && chartMode === 'level'
      ? statsFromPoints(dataPoints)
      : null),
    [isLevelRateFamily, chartMode, dataPoints],
  );

  const yoyStats = useMemo(
    () => (chartMode === 'yoy' ? statsFromPoints(yoyDataPoints) : null),
    [chartMode, yoyDataPoints],
  );

  const qoqStats = useMemo(
    () => (chartMode === 'qoq' ? statsFromPoints(qoqDataPoints) : null),
    [chartMode, qoqDataPoints],
  );

  const periodMonthlyStats = useMemo(
    () => (chartMode === 'period-monthly' ? statsFromPoints(periodMonthlyDataPoints) : null),
    [chartMode, periodMonthlyDataPoints],
  );

  const periodWeeklyStats = useMemo(
    () => (chartMode === 'period-weekly' ? statsFromPoints(periodWeeklyDataPoints) : null),
    [chartMode, periodWeeklyDataPoints],
  );

  const stats = chartMode === 'quarterly' ? quarterlyStats
    : chartMode === 'annual' ? annualStats
      : chartMode === 'weekly' ? weeklyStats
        : chartMode === 'yoy' ? yoyStats
          : chartMode === 'qoq' ? qoqStats
            : chartMode === 'period-weekly' ? periodWeeklyStats
              : chartMode === 'period-monthly' ? periodMonthlyStats
              : chartMode === 'mom' ? momStats
                : chartMode === 'level' && isLevelRateFamily ? levelStats
                  : chartMode === 'cpi' ? monthlyStats
                    : chartMode === 'index' && (isCumulativeIndex || isHousingFamily || isPpiFamily)
                      ? indexStats
                      : inflationStats;

  const cpiPrevDate = dataPoints.length >= 2
    ? dataPoints[dataPoints.length - 2].date
    : null;

  const chartLoading = chartMode === 'inflation' ? loadingInflation
    : chartMode === 'quarterly' ? loadingQuarterly
      : chartMode === 'annual' ? loadingAnnual
        : chartMode === 'weekly' ? loadingWeekly
          : chartMode === 'yoy' ? loadingYoy
            : chartMode === 'qoq' ? loadingQoq
              : chartMode === 'period-weekly' ? loadingPeriodWeekly
                : chartMode === 'period-monthly' ? loadingPeriodMonthly
                  : chartMode === 'index' && (isHousingFamily || isPpiFamily) ? loadingData
                    : chartMode === 'mom' && isPpiFamily ? loadingData
                      : loadingData;

  const hasForecastData = chartMode === 'mom' && isPpiFamily
    ? false
    // Недельный режим — официальный оперативный ряд без прогноза.
    : chartMode === 'weekly'
      ? false
      : chartMode === 'quarterly'
        ? quarterlyForecastData?.forecast?.values?.length > 0
        : chartMode === 'annual'
          ? annualForecastResp?.forecast?.values?.length > 0
          : chartMode === 'yoy'
            ? yoyForecastData?.forecast?.values?.length > 0
            : chartMode === 'qoq'
              ? qoqForecastData?.forecast?.values?.length > 0
              : chartMode === 'period-weekly'
                ? periodWeeklyForecastData?.forecast?.values?.length > 0
                : chartMode === 'period-monthly'
                  ? periodMonthlyForecastData?.forecast?.values?.length > 0
                  : chartMode === 'inflation'
                    ? inflationResp?.forecast?.length > 0
                    : displayForecastData?.forecast?.values?.length > 0;

  const forecastEnabled = hasForecastData;

  return {
    isPriceCategory,
    isHousingFamily,
    isPpiFamily,
    isCbrTermSliceFamily,
    isUnemploymentFamily: isUnemploymentFamily(code),
    isUnemploymentCanonical,
    momDataPoints,
    safeViewMode,
    chartMode,
    shouldSubtract100,

    dataPoints,
    inflationResp,
    quarterlyDataPoints,
    annualDataPoints,
    weeklyDataPoints,
    yoyDataPoints,
    qoqDataPoints,
    periodMonthlyDataPoints,
    periodWeeklyDataPoints,

    displayForecastData,
    quarterlyForecastData,
    annualForecastResp,
    yoyForecastData,
    qoqForecastData,
    periodMonthlyForecastData,
    periodWeeklyForecastData,

    stats,
    cpiPrevDate,

    chartLoading,
    loadingData,
    loadingInflation,
    loadingAnnual,
    loadingWeekly,
    loadingQuarterly,
    loadingYoy,
    loadingQoq,
    loadingPeriodMonthly,
    loadingPeriodWeekly,
    dataError,
    fetchingData,
    hasForecastData,
    forecastEnabled,

    refetchData,
    refetchInflation,
    refetchForecast,
  };
}
