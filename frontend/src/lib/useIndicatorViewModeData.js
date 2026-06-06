import { useMemo } from 'react';
import { useIndicatorData, useInflation, useForecast } from './hooks';
import { isCpiIndex, adjustCpiForecastDisplay } from './format';
import {
  dataModeForUrlMode,
  isActiveCpiUrlMode,
  normalizeCpiViewMode,
  cpiIndexGranularity,
} from './cpiViewModeResolve';
import {
  dataModeForHousingUrlMode,
  HOUSING_CODES,
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
  AUTO_LOAN_CODES,
  dataModeForAutoLoanUrlMode,
  isActiveAutoLoanUrlMode,
  normalizeAutoLoanViewMode,
} from './autoLoanViewModeResolve';
import {
  CBR_TERM_SLICE_CODES,
  dataModeForCbrTermSliceUrlMode,
  normalizeCbrTermSliceViewMode,
} from './cbrTermSliceRateResolve';
import {
  KEY_RATE_CODES,
  dataModeForKeyRateUrlMode,
  normalizeKeyRateViewMode,
} from './keyRateViewModeResolve';
import {
  MORTGAGE_RATE_CODES,
  dataModeForMortgageUrlMode,
  normalizeMortgageViewMode,
} from './mortgageRateViewModeResolve';
import {
  RUONIA_CODES,
  dataModeForRuoniaUrlMode,
  normalizeRuoniaViewMode,
} from './ruoniaViewModeResolve';
import {
  BTC_USD_CODES,
  dataModeForBtcUsdUrlMode,
  normalizeBtcUsdViewMode,
} from './btcUsdViewModeResolve';
import {
  BRENT_CODES,
  dataModeForBrentUrlMode,
  normalizeBrentViewMode,
} from './brentViewModeResolve';
import {
  GOLD_PRICE_CODES,
  dataModeForGoldPriceUrlMode,
  normalizeGoldPriceViewMode,
} from './goldPriceViewModeResolve';
import {
  CNY_RUB_CODES,
  dataModeForCnyRubUrlMode,
  normalizeCnyRubViewMode,
} from './cnyRubViewModeResolve';
import {
  EUR_RUB_CODES,
  dataModeForEurRubUrlMode,
  normalizeEurRubViewMode,
} from './eurRubViewModeResolve';
import {
  USD_RUB_CODES,
  dataModeForUsdRubUrlMode,
  normalizeUsdRubViewMode,
} from './usdRubViewModeResolve';
import {
  BUDGET_CODES,
  dataModeForBudgetUrlMode,
  normalizeBudgetViewMode,
} from './budgetViewModeResolve';
import {
  BANK_CREDIT_CODES,
  dataModeForBankCreditUrlMode,
  normalizeBankCreditViewMode,
} from './bankCreditViewModeResolve';
import {
  HOUSEHOLD_FINANCE_CODES,
  dataModeForHouseholdFinanceUrlMode,
  normalizeHouseholdFinanceViewMode,
} from './householdFinanceViewModeResolve';
import {
  EXTERNAL_DEBT_CODES,
  dataModeForExternalDebtUrlMode,
  normalizeExternalDebtViewMode,
} from './externalDebtViewModeResolve';
import {
  GDP_USE_CODES,
  dataModeForGdpUseUrlMode,
  normalizeGdpUseViewMode,
} from './gdpUseViewModeResolve';
import {
  INTERNATIONAL_RESERVES_CODES,
  dataModeForInternationalReservesUrlMode,
  normalizeInternationalReservesViewMode,
} from './internationalReservesViewModeResolve';
import {
  MONETARY_MASS_CODES,
  dataModeForMonetaryMassUrlMode,
  normalizeMonetaryMassViewMode,
} from './monetaryMassViewModeResolve';
import {
  LABOR_MARKET_CODES,
  dataModeForLaborMarketUrlMode,
  normalizeLaborMarketViewMode,
} from './laborMarketViewModeResolve';
import {
  UNEMPLOYMENT_ROOT,
  dataModeForUnemploymentUrlMode,
  isUnemploymentFamily,
  normalizeUnemploymentViewMode,
} from './unemploymentViewModeResolve';
import {
  WAGES_NOMINAL_ROOT,
  dataModeForWagesNominalUrlMode,
  isWagesNominalFamily,
  normalizeWagesNominalViewMode,
} from './wagesNominalViewModeResolve';
import {
  GDP_NOMINAL_ROOT,
  dataModeForGdpNominalUrlMode,
  isGdpNominalFamily,
  normalizeGdpNominalViewMode,
} from './gdpNominalViewModeResolve';
import {
  GDP_REAL_ROOT,
  dataModeForGdpRealUrlMode,
  isGdpRealFamily,
  normalizeGdpRealViewMode,
} from './gdpRealViewModeResolve';
import { applyMoMTransform } from './viewModeFamilies';

const CPI_DERIVED_CODES = {
  cpi: {
    quarterly: 'inflation-quarterly',
    annual: 'inflation-annual',
    weekly: 'inflation-weekly',
    yoy: 'cpi-yoy',
    qoq: 'cpi-qoq',
    periodMonthly: 'cpi-period-monthly',
    periodWeekly: 'cpi-period-weekly',
  },
  'cpi-food': {
    quarterly: 'cpi-food-quarterly',
    annual: 'cpi-food-annual',
    weekly: 'inflation-weekly-food',
    yoy: 'cpi-food-yoy',
    qoq: 'cpi-food-qoq',
    periodMonthly: 'cpi-food-period-monthly',
    periodWeekly: 'cpi-food-period-weekly',
  },
  'cpi-nonfood': {
    quarterly: 'cpi-nonfood-quarterly',
    annual: 'cpi-nonfood-annual',
    weekly: 'inflation-weekly-nonfood',
    yoy: 'cpi-nonfood-yoy',
    qoq: 'cpi-nonfood-qoq',
    periodMonthly: 'cpi-nonfood-period-monthly',
    periodWeekly: 'cpi-nonfood-period-weekly',
  },
  'cpi-services': {
    quarterly: 'cpi-services-quarterly',
    annual: 'cpi-services-annual',
    weekly: 'inflation-weekly-services',
    yoy: 'cpi-services-yoy',
    qoq: 'cpi-services-qoq',
    periodMonthly: 'cpi-services-period-monthly',
    periodWeekly: 'cpi-services-period-weekly',
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
  },
  'housing-price-secondary': {
    yoy: 'housing-yoy-secondary',
    qoq: 'housing-qoq-secondary',
  },
};

const PPI_DERIVED_CODES = {
  ppi: {
    yoy: 'ppi-yoy',
  },
};

// Накопленный индекс CPI (режим «Индекс»): база 100 в январе 2000.
// Историю 1991–1999 обрезаем — в 1992-м январский индекс доходил до 345%
// за месяц, и за 9 лет цепного произведения шкала уезжает в сотни тысяч,
// делая график нечитаемым (вся «история» сжимается в правый край).
// 2000-01 — начало пост-кризисного периода стабильной денежной политики;
// этот выбор даёт ~26 лет читаемой экспоненциальной кривой 100 → ~1000+,
// что покрывает горизонт всех современных решений по ставке/инфляции.
const CPI_INDEX_BASE_DATE = '2000-01-01';
const CPI_INDEX_BASE_VALUE = 100;

function buildCumulativeIndex(rawPoints) {
  if (!Array.isArray(rawPoints) || !rawPoints.length) return [];
  const trimmed = rawPoints.filter((p) => String(p.date) >= CPI_INDEX_BASE_DATE);
  if (!trimmed.length) return [];
  const out = [{ ...trimmed[0], value: CPI_INDEX_BASE_VALUE }];
  let acc = CPI_INDEX_BASE_VALUE;
  for (let i = 1; i < trimmed.length; i++) {
    acc = acc * (Number(trimmed[i].value) / 100);
    out.push({ ...trimmed[i], value: +acc.toFixed(2) });
  }
  return out;
}

/**
 * Последняя точка каждого периода (квартал/год) для индекса-уровня.
 * Вход — накопленный месячный индекс (по возрастанию даты).
 */
function lastOfBucket(points, granularity) {
  if (!Array.isArray(points) || !points.length) return points;
  const keyOf = (date) => {
    const d = String(date);
    const y = d.slice(0, 4);
    if (granularity === 'year') return y;
    const m = Number(d.slice(5, 7));
    const q = Math.floor((m - 1) / 3) + 1;
    return `${y}-Q${q}`;
  };
  const map = new Map();
  for (const p of points) map.set(keyOf(p.date), p);
  return Array.from(map.values());
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
  const isAutoLoanFamily = AUTO_LOAN_CODES.includes(code);
  const isMortgageFamily = MORTGAGE_RATE_CODES.includes(code);
  const isCbrTermSliceFamily = CBR_TERM_SLICE_CODES.includes(code);
  const isKeyRateFamily = KEY_RATE_CODES.includes(code);
  const isRuoniaFamily = RUONIA_CODES.includes(code);
  const isBtcUsdFamily = BTC_USD_CODES.includes(code);
  const isBrentFamily = BRENT_CODES.includes(code);
  const isGoldPriceFamily = GOLD_PRICE_CODES.includes(code);
  const isCnyRubFamily = CNY_RUB_CODES.includes(code);
  const isUsdRubFamily = USD_RUB_CODES.includes(code);
  const isEurRubFamily = EUR_RUB_CODES.includes(code);
  const isBudgetFamily = BUDGET_CODES.includes(code);
  const isBankCreditFamily = BANK_CREDIT_CODES.includes(code);
  const isHouseholdFinanceFamily = HOUSEHOLD_FINANCE_CODES.includes(code);
  const   isExternalDebtFamily = EXTERNAL_DEBT_CODES.includes(code);
  const isGdpUseFamily = GDP_USE_CODES.includes(code);
  const isInternationalReservesFamily = INTERNATIONAL_RESERVES_CODES.includes(code);
  const isMonetaryMassFamily = MONETARY_MASS_CODES.includes(code);
  const isLaborMarketFamily = LABOR_MARKET_CODES.includes(code);
  const isUnemploymentCanonical = code === UNEMPLOYMENT_ROOT;
  const isWagesNominalCanonical = code === WAGES_NOMINAL_ROOT;
  const isGdpNominalCanonical = code === GDP_NOMINAL_ROOT;
  const isGdpRealCanonical = code === GDP_REAL_ROOT;
  const isDailyAggRateFamily = isKeyRateFamily || isRuoniaFamily || isBtcUsdFamily
    || isBrentFamily || isGoldPriceFamily || isUsdRubFamily || isEurRubFamily || isCnyRubFamily
    || isBudgetFamily || isBankCreditFamily || isHouseholdFinanceFamily
    || isMonetaryMassFamily || isLaborMarketFamily || isInternationalReservesFamily
    || isExternalDebtFamily || isGdpUseFamily;
  const isLevelRateFamily = isAutoLoanFamily || isMortgageFamily || isCbrTermSliceFamily;

  const safeViewMode = isPriceCategory
    ? (isActiveCpiUrlMode(viewMode) ? normalizeCpiViewMode(viewMode) : 'inflation')
    : isHousingFamily
      ? (isActiveHousingUrlMode(viewMode) ? normalizeHousingViewMode(viewMode) : 'yoy')
      : isPpiFamily
        ? (isActivePpiUrlMode(viewMode) ? normalizePpiViewMode(viewMode) : 'yoy')
        : isAutoLoanFamily
          ? normalizeAutoLoanViewMode(viewMode)
          : isMortgageFamily
            ? normalizeMortgageViewMode(viewMode)
            : isCbrTermSliceFamily
            ? normalizeCbrTermSliceViewMode(viewMode)
            : isKeyRateFamily
              ? normalizeKeyRateViewMode(viewMode)
              : isRuoniaFamily
                ? normalizeRuoniaViewMode(viewMode)
                : isBtcUsdFamily
                  ? normalizeBtcUsdViewMode(viewMode)
                  : isBrentFamily
                    ? normalizeBrentViewMode(viewMode)
                    : isGoldPriceFamily
                      ? normalizeGoldPriceViewMode(viewMode)
                      : isUsdRubFamily
                        ? normalizeUsdRubViewMode(viewMode)
                        : isEurRubFamily
                      ? normalizeEurRubViewMode(viewMode)
                      : isCnyRubFamily
                        ? normalizeCnyRubViewMode(viewMode)
                        : isBudgetFamily
                          ? normalizeBudgetViewMode(viewMode)
                          : isBankCreditFamily
                            ? normalizeBankCreditViewMode(viewMode)
                            : isHouseholdFinanceFamily
                              ? normalizeHouseholdFinanceViewMode(viewMode)
                              : isMonetaryMassFamily
                                ? normalizeMonetaryMassViewMode(viewMode)
                                : isLaborMarketFamily
                                  ? normalizeLaborMarketViewMode(viewMode)
                                  : isUnemploymentCanonical
                                    ? normalizeUnemploymentViewMode(viewMode)
                                    : isWagesNominalCanonical
                                      ? normalizeWagesNominalViewMode(viewMode)
                                      : isGdpNominalCanonical
                                        ? normalizeGdpNominalViewMode(viewMode)
                                        : isGdpRealCanonical
                                          ? normalizeGdpRealViewMode(viewMode)
                                          : isInternationalReservesFamily
                                  ? normalizeInternationalReservesViewMode(viewMode)
                                  : isExternalDebtFamily
                                    ? normalizeExternalDebtViewMode(viewMode)
                                    : isGdpUseFamily
                                      ? normalizeGdpUseViewMode(viewMode)
                                      : viewMode;
  const chartMode = isPriceCategory
    ? dataModeForUrlMode(safeViewMode)
    : isHousingFamily
      ? dataModeForHousingUrlMode(safeViewMode)
      : isPpiFamily
        ? dataModeForPpiUrlMode(safeViewMode)
        : isKeyRateFamily
          ? dataModeForKeyRateUrlMode(safeViewMode)
          : isRuoniaFamily
            ? dataModeForRuoniaUrlMode(safeViewMode)
            : isBtcUsdFamily
              ? dataModeForBtcUsdUrlMode(safeViewMode)
              : isBrentFamily
                ? dataModeForBrentUrlMode(safeViewMode)
                : isGoldPriceFamily
                  ? dataModeForGoldPriceUrlMode(safeViewMode)
                  : isUsdRubFamily
                    ? dataModeForUsdRubUrlMode(safeViewMode)
                    : isEurRubFamily
                  ? dataModeForEurRubUrlMode(safeViewMode)
                  : isCnyRubFamily
                    ? dataModeForCnyRubUrlMode(safeViewMode)
                    : isBudgetFamily
                      ? dataModeForBudgetUrlMode(safeViewMode)
                      : isBankCreditFamily
                        ? dataModeForBankCreditUrlMode(safeViewMode)
                        : isHouseholdFinanceFamily
                          ? dataModeForHouseholdFinanceUrlMode(safeViewMode)
                          : isMonetaryMassFamily
                            ? dataModeForMonetaryMassUrlMode(safeViewMode)
                            : isLaborMarketFamily
                              ? dataModeForLaborMarketUrlMode(safeViewMode)
                              : isUnemploymentCanonical
                                ? dataModeForUnemploymentUrlMode(safeViewMode)
                                : isWagesNominalCanonical
                                  ? dataModeForWagesNominalUrlMode(safeViewMode)
                                  : isGdpNominalCanonical
                                    ? dataModeForGdpNominalUrlMode(safeViewMode)
                                    : isGdpRealCanonical
                                      ? dataModeForGdpRealUrlMode(safeViewMode)
                                      : isInternationalReservesFamily
                              ? dataModeForInternationalReservesUrlMode(safeViewMode)
                              : isExternalDebtFamily
                                ? dataModeForExternalDebtUrlMode(safeViewMode)
                                : isGdpUseFamily
                                  ? dataModeForGdpUseUrlMode(safeViewMode)
                                  : isLevelRateFamily
            ? (isAutoLoanFamily
              ? dataModeForAutoLoanUrlMode(safeViewMode)
              : isMortgageFamily
                ? dataModeForMortgageUrlMode(safeViewMode)
                : dataModeForCbrTermSliceUrlMode(safeViewMode))
            : 'cpi';

  // На режиме `index` строим накопленный индекс (база 100 = первая точка
  // ряда от 2000-01) — вычитать 100 не нужно. На остальных режимах
  // CPI-семейства — стандартное преобразование к шкале «delta % от 100».
  const isCumulativeIndex = isCpiIndex(code) && String(safeViewMode).startsWith('index');
  const cpiIndexBucket = isPriceCategory ? cpiIndexGranularity(safeViewMode) : null;
  const ppiIndexBucket = isPpiFamily ? ppiIndexGranularity(safeViewMode) : null;
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
  const { data: weeklyForecastResp } = useForecast(weeklyDerivedCode, {
    enabled: !!weeklyDerivedCode && chartMode === 'weekly',
  });
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

  const dataPoints = useMemo(() => {
    if (!rawDataPoints.length) return rawDataPoints;
    if (isCumulativeIndex) {
      const idx = buildCumulativeIndex(rawDataPoints);
      return cpiIndexBucket ? lastOfBucket(idx, cpiIndexBucket) : idx;
    }
    // ИЦП «Индекс» — ряд уже накопленный (2010=100); по кварталам/годам берём
    // уровень на конец периода.
    if (isPpiFamily && chartMode === 'index' && ppiIndexBucket) {
      return lastOfBucket(rawDataPoints, ppiIndexBucket);
    }
    if (!shouldSubtract100) return rawDataPoints;
    return rawDataPoints.map((p) => ({ ...p, value: Number(p.value) - 100 }));
  }, [
    rawDataPoints, shouldSubtract100, isCumulativeIndex, cpiIndexBucket,
    isPpiFamily, chartMode, ppiIndexBucket,
  ]);

  const momDataPoints = useMemo(() => {
    if (!isPpiFamily || chartMode !== 'mom') return [];
    return applyMoMTransform(rawDataPoints);
  }, [isPpiFamily, chartMode, rawDataPoints]);

  const displayForecastData = useMemo(() => {
    if (isCumulativeIndex) {
      // На агрегированном индексе (по кварталам/годам) прогноз не строим —
      // накопленная месячная кривая прогноза не сводится к концам периодов.
      if (cpiIndexBucket) return null;
      // Прогноз режима «Индекс» — продолжение накопленной кривой:
      // последнее накопленное факт-значение × прогнозные месячные / 100.
      const lastActual = dataPoints?.length
        ? dataPoints[dataPoints.length - 1].value
        : null;
      return buildCumulativeIndexForecast(forecastResp, lastActual);
    }
    // ИЦП по кварталам/годам — прогноз не строим (концы периодов не сводятся).
    if (isPpiFamily && chartMode === 'index' && ppiIndexBucket) return null;
    if (!shouldSubtract100) return forecastResp;
    return adjustCpiForecastDisplay(forecastResp, code);
  }, [
    forecastResp, shouldSubtract100, isCumulativeIndex, cpiIndexBucket, dataPoints, code,
    isPpiFamily, chartMode, ppiIndexBucket,
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

  // Прогноз inflation-weekly приходит в формате CPI-индекса (значения вокруг 100),
  // фронт же показывает delta (value - 100). Преобразуем чтобы прогноз был в той же
  // системе координат, что и actual-точки выше.
  const weeklyForecastData = useMemo(
    () => adjustCpiForecastDisplay(weeklyForecastResp, weeklyDerivedCode),
    [weeklyForecastResp, weeklyDerivedCode],
  );

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
    () => ((isLevelRateFamily || isDailyAggRateFamily) && chartMode === 'level'
      ? statsFromPoints(dataPoints)
      : null),
    [isLevelRateFamily, isDailyAggRateFamily, chartMode, dataPoints],
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
                : chartMode === 'level' && (isLevelRateFamily || isDailyAggRateFamily) ? levelStats
                  : chartMode === 'cpi' ? monthlyStats
                    : chartMode === 'index' && (isCumulativeIndex || isHousingFamily || isPpiFamily)
                      ? indexStats
                      : inflationStats;

  const cpiPrevDate = dataPoints.length >= 2
    ? dataPoints[dataPoints.length - 2].date
    : null;

  const chartLoading = isDailyAggRateFamily ? loadingData
    : chartMode === 'inflation' ? loadingInflation
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
    : chartMode === 'quarterly'
      ? quarterlyForecastData?.forecast?.values?.length > 0
      : chartMode === 'annual'
        ? annualForecastResp?.forecast?.values?.length > 0
        : chartMode === 'weekly'
          ? weeklyForecastData?.forecast?.values?.length > 0
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
    isAutoLoanFamily,
    isMortgageFamily,
    isCbrTermSliceFamily,
    isKeyRateFamily,
    isRuoniaFamily,
    isBtcUsdFamily,
    isBrentFamily,
    isGoldPriceFamily,
    isCnyRubFamily,
    isUsdRubFamily,
    isEurRubFamily,
    isBudgetFamily,
    isBankCreditFamily,
    isHouseholdFinanceFamily,
    isMonetaryMassFamily,
    isLaborMarketFamily,
    isUnemploymentFamily: isUnemploymentFamily(code),
    isUnemploymentCanonical,
    isWagesNominalFamily: isWagesNominalFamily(code),
    isWagesNominalCanonical,
    isGdpNominalFamily: isGdpNominalFamily(code),
    isGdpNominalCanonical,
    isGdpRealFamily: isGdpRealFamily(code),
    isGdpRealCanonical,
    isInternationalReservesFamily,
    isExternalDebtFamily,
    isGdpUseFamily,
    isDailyAggRateFamily,
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
    weeklyForecastData,
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
