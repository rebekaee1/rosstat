import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useParams, useSearchParams, useNavigate, Link } from 'react-router-dom';
import { ArrowRight, GitCompare } from 'lucide-react';
import gsap from 'gsap';
import {
  useIndicator, useIndicatorData, useIndicatorStats, useIndicators, useForecast,
} from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import ApiRetryBanner from '../components/ApiRetryBanner';
import IndicatorDetailHeader from '../components/IndicatorDetailHeader';
import VariantGroupPicker from '../components/VariantGroupPicker';
import FrequencySwitcher from '../components/FrequencySwitcher';
import CpiIndicatorControls from '../components/CpiIndicatorControls';
import HousingIndicatorControls from '../components/HousingIndicatorControls';
import PpiIndicatorControls from '../components/PpiIndicatorControls';
import AutoLoanIndicatorControls from '../components/AutoLoanIndicatorControls';
import CbrTermSliceRateIndicatorControls from '../components/CbrTermSliceRateIndicatorControls';
import KeyRateIndicatorControls from '../components/KeyRateIndicatorControls';
import RuoniaIndicatorControls from '../components/RuoniaIndicatorControls';
import BtcUsdIndicatorControls from '../components/BtcUsdIndicatorControls';
import BrentIndicatorControls from '../components/BrentIndicatorControls';
import CnyRubIndicatorControls from '../components/CnyRubIndicatorControls';
import BudgetIndicatorControls from '../components/BudgetIndicatorControls';
import BankCreditIndicatorControls from '../components/BankCreditIndicatorControls';
import HouseholdFinanceIndicatorControls from '../components/HouseholdFinanceIndicatorControls';
import ExternalDebtIndicatorControls from '../components/ExternalDebtIndicatorControls';
import GdpUseIndicatorControls from '../components/GdpUseIndicatorControls';
import GdpNominalIndicatorControls from '../components/GdpNominalIndicatorControls';
import GdpRealIndicatorControls from '../components/GdpRealIndicatorControls';
import InternationalReservesIndicatorControls from '../components/InternationalReservesIndicatorControls';
import MonetaryMassIndicatorControls from '../components/MonetaryMassIndicatorControls';
import LaborMarketIndicatorControls from '../components/LaborMarketIndicatorControls';
import UnemploymentIndicatorControls from '../components/UnemploymentIndicatorControls';
import WagesNominalIndicatorControls from '../components/WagesNominalIndicatorControls';
import GoldPriceIndicatorControls from '../components/GoldPriceIndicatorControls';
import EurRubIndicatorControls from '../components/EurRubIndicatorControls';
import UsdRubIndicatorControls from '../components/UsdRubIndicatorControls';
import MortgageRateIndicatorControls from '../components/MortgageRateIndicatorControls';
import ViewModePicker from '../components/ViewModePicker';
import IndicatorTelemetryGrid from '../components/IndicatorTelemetryGrid';
import IndicatorChartSection from '../components/IndicatorChartSection';
import IndicatorMethodologyPanel from '../components/IndicatorMethodologyPanel';
import IndicatorForecastSection from '../components/IndicatorForecastSection';
import IndicatorDataTableSection from '../components/IndicatorDataTableSection';
import IndicatorSeoBlocks from '../components/IndicatorSeoBlocks';
import { findVariantGroup, relatedIndicatorCardCopy } from '../lib/indicatorVariants';
import useIndicatorViewModeData from '../lib/useIndicatorViewModeData';
import {
  findViewModeFamily,
  viewModeCanonicalTarget,
  applyMoMTransform,
  applyAggregateTransform,
  DAILY_AGG_FREQUENCY,
} from '../lib/viewModeFamilies';
import { getViewModeContent } from '../lib/cpiViewModeContent';
import { HOUSING_CODES, housingCanonicalTarget } from '../lib/housingViewModeResolve';
import { PPI_CODES, ppiCanonicalTarget } from '../lib/ppiViewModeResolve';
import { AUTO_LOAN_CODES } from '../lib/autoLoanViewModeResolve';
import { CBR_TERM_SLICE_CODES } from '../lib/cbrTermSliceRateResolve';
import { KEY_RATE_CODES, keyRateAggGranularity } from '../lib/keyRateViewModeResolve';
import { RUONIA_CODES, ruoniaAggGranularity } from '../lib/ruoniaViewModeResolve';
import { BTC_USD_CODES, btcUsdAggGranularity } from '../lib/btcUsdViewModeResolve';
import { BRENT_CODES, brentAggGranularity } from '../lib/brentViewModeResolve';
import { GOLD_PRICE_CODES, goldPriceAggGranularity } from '../lib/goldPriceViewModeResolve';
import { CNY_RUB_CODES, cnyRubAggGranularity } from '../lib/cnyRubViewModeResolve';
import { BUDGET_CODES, budgetAggGranularity } from '../lib/budgetViewModeResolve';
import { BANK_CREDIT_CODES, bankCreditAggGranularity } from '../lib/bankCreditViewModeResolve';
import {
  HOUSEHOLD_FINANCE_CODES,
  householdFinanceAggGranularity,
} from '../lib/householdFinanceViewModeResolve';
import {
  EXTERNAL_DEBT_CODES,
  externalDebtAggGranularity,
} from '../lib/externalDebtViewModeResolve';
import {
  GDP_USE_CODES,
  gdpUseAggGranularity,
} from '../lib/gdpUseViewModeResolve';
import {
  INTERNATIONAL_RESERVES_CODES,
  internationalReservesAggGranularity,
} from '../lib/internationalReservesViewModeResolve';
import {
  MONETARY_MASS_CODES,
  monetaryMassAggGranularity,
} from '../lib/monetaryMassViewModeResolve';
import {
  LABOR_MARKET_CODES,
  laborMarketAggGranularity,
} from '../lib/laborMarketViewModeResolve';
import {
  UNEMPLOYMENT_ROOT,
  unemploymentCanonicalTarget,
  unemploymentDataCodeForMode,
  unemploymentModeMeta,
  normalizeUnemploymentViewMode,
} from '../lib/unemploymentViewModeResolve';
import {
  WAGES_NOMINAL_ROOT,
  wagesNominalCanonicalTarget,
  wagesNominalDataCodeForMode,
  wagesNominalModeMeta,
  normalizeWagesNominalViewMode,
} from '../lib/wagesNominalViewModeResolve';
import {
  GDP_NOMINAL_ROOT,
  gdpNominalCanonicalTarget,
  gdpNominalDataCodeForMode,
  gdpNominalModeMeta,
  normalizeGdpNominalViewMode,
} from '../lib/gdpNominalViewModeResolve';
import {
  GDP_REAL_ROOT,
  gdpRealCanonicalTarget,
  gdpRealDataCodeForMode,
  gdpRealModeMeta,
  normalizeGdpRealViewMode,
} from '../lib/gdpRealViewModeResolve';
import { EUR_RUB_CODES, eurRubAggGranularity } from '../lib/eurRubViewModeResolve';
import { USD_RUB_CODES, usdRubAggGranularity } from '../lib/usdRubViewModeResolve';
import { MORTGAGE_RATE_CODES } from '../lib/mortgageRateViewModeResolve';
import { downloadExcel, downloadCSV } from '../lib/excel';
import { track, events } from '../lib/track';
import useScrollDepth from '../lib/useScrollDepth';
import { isIndicatorListed } from '../lib/categories';

// Правка №16 (звонок 2026-05-21): на карточке ИПП по умолчанию показываем
// г/г %, не уровень индекса 2018=100 (raw 105.2 без контекста бессмыслен).
// Редирект был стёрт при Phase 1 refactor 22-05, восстановлен после ревизии.
const DEFAULT_REDIRECTS = {
  ipi: 'ipi-yoy',
};

export default function IndicatorDetail() {
  const { code } = useParams();
  const navigate = useNavigate();
  const headerRef = useRef(null);
  const [showForecast, setShowForecast] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    const target = DEFAULT_REDIRECTS[code];
    if (target) {
      navigate(`/indicator/${target}`, { replace: true });
      return;
    }
    const canon = viewModeCanonicalTarget(code)
      ?? unemploymentCanonicalTarget(code)
      ?? wagesNominalCanonicalTarget(code)
      ?? gdpNominalCanonicalTarget(code)
      ?? gdpRealCanonicalTarget(code)
      ?? housingCanonicalTarget(code)
      ?? ppiCanonicalTarget(code);
    if (canon) {
      const isHousingParent = HOUSING_CODES.includes(canon.parentCode);
      const isPpiParent = PPI_CODES.includes(canon.parentCode);
      const omitMode = canon.mode === 'level'
        || (isHousingParent && canon.mode === 'yoy')
        || (isPpiParent && canon.mode === 'yoy');
      const suffix = omitMode ? '' : `?mode=${encodeURIComponent(canon.mode)}`;
      navigate(`/indicator/${canon.parentCode}${suffix}`, { replace: true });
    }
  }, [code, navigate]);
  // viewMode хранится в URL (?mode=…) — сохраняется при смене состава/среза.
  const urlMode = searchParams.get('mode');
  const levelRateDefault = AUTO_LOAN_CODES.includes(code)
    || MORTGAGE_RATE_CODES.includes(code)
    || CBR_TERM_SLICE_CODES.includes(code)
    || KEY_RATE_CODES.includes(code)
    || RUONIA_CODES.includes(code)
    || BTC_USD_CODES.includes(code)
    || BRENT_CODES.includes(code)
    || GOLD_PRICE_CODES.includes(code)
    || USD_RUB_CODES.includes(code)
    || EUR_RUB_CODES.includes(code)
    || CNY_RUB_CODES.includes(code)
    || BUDGET_CODES.includes(code)
    || BANK_CREDIT_CODES.includes(code)
    || HOUSEHOLD_FINANCE_CODES.includes(code)
    || MONETARY_MASS_CODES.includes(code)
    || INTERNATIONAL_RESERVES_CODES.includes(code)
    || EXTERNAL_DEBT_CODES.includes(code)
    || GDP_USE_CODES.includes(code)
    || code === UNEMPLOYMENT_ROOT
    || code === WAGES_NOMINAL_ROOT
    || code === GDP_NOMINAL_ROOT
    || code === GDP_REAL_ROOT;
  const defaultViewMode = levelRateDefault
    ? 'level'
    : PPI_CODES.includes(code) || HOUSING_CODES.includes(code)
      ? 'yoy'
      : 'inflation';
  const viewMode = urlMode || defaultViewMode;
  const setViewMode = useCallback((mode) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      const baseline = levelRateDefault
        ? 'level'
        : PPI_CODES.includes(code) || HOUSING_CODES.includes(code)
          ? 'yoy'
          : 'inflation';
      if (mode && mode !== baseline) next.set('mode', mode);
      else next.delete('mode');
      return next;
    }, { replace: true });
  }, [setSearchParams, code, levelRateDefault]);
  const [chartData, setChartData] = useState([]);
  const [currentRange, setCurrentRange] = useState('5y');

  const {
    data: indicator,
    isLoading: loadingInd,
    isError: indError,
    error: indErr,
    refetch: refetchInd,
    isFetching: fetchingInd,
  } = useIndicator(code);

  // Пока данные индикатора не пришли — не трогаем <head>: SSR-renderer
  // (seo_renderer.py::render_indicator_html) уже положил правильный title из
  // БД, плюс canonical/og:*. Любая клиентская перезапись на промежуточное
  // значение (например, "Индикатор cpi") вызывала бы flap у поисковиков.
  useDocumentMeta(indicator ? {
    title: indicator.seo_title || indicator.name,
    description: indicator.seo_description,
    path: `/indicator/${code}`,
  } : null);

  const { data: stats } = useIndicatorStats(code);
  const variantGroup = findVariantGroup(code);
  // Соседи по той же категории — нижний CTA-блок «Похожие индикаторы».
  // Загружается лениво (после того как мы знаем category), потому что
  // useIndicators({ category }) приходит из общего react-query-кэша и обычно
  // уже прогрет на /category/:slug страницей-родителем.
  const { data: siblings } = useIndicators({
    category: indicator?.category,
    includeInactive: false,
    enabled: Boolean(indicator?.category),
  });

  const relatedIndicators = useMemo(() => {
    if (!siblings?.length || !indicator) return [];
    return siblings
      .filter((s) => s.code !== indicator.code && isIndicatorListed(s) && s.is_active)
      .slice(0, 6);
  }, [siblings, indicator]);

  const view = useIndicatorViewModeData({ code, viewMode });
  const {
    isPriceCategory, isHousingFamily, isPpiFamily, isAutoLoanFamily, isMortgageFamily,
    isCbrTermSliceFamily, isKeyRateFamily, isRuoniaFamily, isBtcUsdFamily, isBrentFamily,
    isGoldPriceFamily,
    isUsdRubFamily,
    isEurRubFamily,
    isCnyRubFamily,
    isBudgetFamily,
    isBankCreditFamily,
    isHouseholdFinanceFamily,
    isMonetaryMassFamily,
    isLaborMarketFamily,
    isUnemploymentFamily,
    isUnemploymentCanonical,
    isWagesNominalFamily,
    isWagesNominalCanonical,
    isGdpNominalFamily,
    isGdpNominalCanonical,
    isGdpRealFamily,
    isGdpRealCanonical,
    isInternationalReservesFamily,
    isExternalDebtFamily,
    isGdpUseFamily,
    safeViewMode, chartMode, shouldSubtract100,
    dataPoints: baseDataPoints, momDataPoints, inflationResp,
    quarterlyDataPoints, annualDataPoints, weeklyDataPoints,
    yoyDataPoints, qoqDataPoints, periodMonthlyDataPoints, periodWeeklyDataPoints,
    displayForecastData, quarterlyForecastData, annualForecastResp, weeklyForecastData,
    yoyForecastData, qoqForecastData, periodMonthlyForecastData, periodWeeklyForecastData,
    stats: baseViewStats, cpiPrevDate,
    chartLoading: baseChartLoading, loadingData, loadingInflation,
    loadingAnnual, loadingWeekly, loadingQuarterly, loadingYoy, loadingQoq,
    loadingPeriodMonthly, loadingPeriodWeekly,
    dataError, fetchingData, hasForecastData, forecastEnabled: baseForecastEnabled,
    refetchData, refetchInflation, refetchForecast,
  } = view;

  // ============================================================
  // View-mode families (Phase 1+2+3): in-page переключение
  // «режим отображения» вместо отдельных карточек в каталоге.
  //
  // Если текущий код — корень family (exports / wages-nominal / unemployment
  // / housing-price-* и т.д.) и URL содержит ?mode=… — подгружаем derived
  // и подменяем dataPoints. Виртуальные transforms (MoM, agg) считаются
  // на фронте без backend-дёргания. См. lib/viewModeFamilies.js.
  //
  // Daily aggregation (Phase 5, daily-индикаторы вроде key-rate, ruonia,
  // cbr-fx-*, gold-price) обрабатывается отдельно ниже (dailyAggregation).
  // ============================================================
  const viewFamily = findViewModeFamily(code);
  const isFamily = !!viewFamily;
  const familyAllowedModes = useMemo(
    () => (viewFamily ? viewFamily.modes.map((m) => m.mode) : []),
    [viewFamily],
  );
  const familyMode = isFamily
    ? (familyAllowedModes.includes(viewMode) ? viewMode : 'level')
    : null;
  const familyModeMeta = useMemo(
    () => (viewFamily && familyMode ? viewFamily.modes.find((m) => m.mode === familyMode) : null),
    [viewFamily, familyMode],
  );
  const isVirtualTransform = isFamily && familyMode !== 'level' && !!familyModeMeta?.transform;
  const unemploymentSafeMode = isUnemploymentCanonical
    ? normalizeUnemploymentViewMode(viewMode)
    : null;
  const unemploymentDerivedCode = isUnemploymentCanonical && unemploymentSafeMode !== 'level'
    ? unemploymentDataCodeForMode(unemploymentSafeMode)
    : null;

  const wagesSafeMode = isWagesNominalCanonical
    ? normalizeWagesNominalViewMode(viewMode)
    : null;
  const wagesDerivedCode = isWagesNominalCanonical && wagesSafeMode !== 'level'
    ? wagesNominalDataCodeForMode(wagesSafeMode)
    : null;

  const gdpNominalSafeMode = isGdpNominalCanonical
    ? normalizeGdpNominalViewMode(viewMode)
    : null;
  const gdpNominalDerivedCode = isGdpNominalCanonical && gdpNominalSafeMode !== 'level'
    ? gdpNominalDataCodeForMode(gdpNominalSafeMode)
    : null;

  const gdpRealSafeMode = isGdpRealCanonical
    ? normalizeGdpRealViewMode(viewMode)
    : null;
  const gdpRealDerivedCode = isGdpRealCanonical && gdpRealSafeMode !== 'level'
    ? gdpRealDataCodeForMode(gdpRealSafeMode)
    : null;

  const familyDerivedCode = isFamily && familyMode !== 'level' && !isVirtualTransform
    ? familyModeMeta?.code ?? null
    : null;
  const modeSubstituteCode = familyDerivedCode || unemploymentDerivedCode
    || wagesDerivedCode || gdpNominalDerivedCode || gdpRealDerivedCode;

  const { data: familyDerivedResp, isLoading: loadingFamilyDerived } = useIndicatorData(
    modeSubstituteCode,
    undefined,
    { enabled: !!modeSubstituteCode },
  );
  const { data: familyForecastResp, refetch: refetchFamilyForecast } = useForecast(
    modeSubstituteCode,
    { enabled: !!modeSubstituteCode },
  );
  // ============================================================
  // Phase 5 — daily aggregation transforms (weekly/monthly/quarterly/annual).
  // Применяется к ЛЮБОМУ daily-индикатору, который ещё не принадлежит
  // family (чтобы не конфликтовало). Режимы:
  //   ?mode=weekly | monthly | quarterly | annual  → avg по bucket'ам.
  // ============================================================
  const dailyAggGranularity = useMemo(() => {
    if (isFamily) return null;
    if (isKeyRateFamily) return keyRateAggGranularity(viewMode);
    if (isRuoniaFamily) return ruoniaAggGranularity(viewMode);
    if (isBtcUsdFamily) return btcUsdAggGranularity(viewMode);
    if (isBrentFamily) return brentAggGranularity(viewMode);
    if (isGoldPriceFamily) return goldPriceAggGranularity(viewMode);
    if (isUsdRubFamily) return usdRubAggGranularity(viewMode);
    if (isEurRubFamily) return eurRubAggGranularity(viewMode);
    if (isCnyRubFamily) return cnyRubAggGranularity(viewMode);
    if (isBudgetFamily) return budgetAggGranularity(viewMode);
    if (isBankCreditFamily) return bankCreditAggGranularity(viewMode);
    if (isHouseholdFinanceFamily) return householdFinanceAggGranularity(viewMode);
    if (isMonetaryMassFamily) return monetaryMassAggGranularity(viewMode);
    if (isLaborMarketFamily) return laborMarketAggGranularity(viewMode);
    if (isInternationalReservesFamily) return internationalReservesAggGranularity(viewMode);
    if (isExternalDebtFamily) return externalDebtAggGranularity(viewMode);
    if (isGdpUseFamily) return gdpUseAggGranularity(viewMode);
    if (indicator?.frequency !== 'daily') return null;
    const mapping = { weekly: 'week', monthly: 'month', quarterly: 'quarter', annual: 'year' };
    return mapping[viewMode] || null;
  }, [isFamily, isKeyRateFamily, isRuoniaFamily, isBtcUsdFamily, isBrentFamily, isGoldPriceFamily, isUsdRubFamily, isEurRubFamily, isCnyRubFamily, isBudgetFamily, isBankCreditFamily, isHouseholdFinanceFamily, isMonetaryMassFamily, isLaborMarketFamily, isInternationalReservesFamily, isExternalDebtFamily, isGdpUseFamily, indicator?.frequency, viewMode]);

  const familyDataPoints = useMemo(() => {
    if (isVirtualTransform && familyModeMeta?.transform === 'mom') {
      return applyMoMTransform(baseDataPoints || []);
    }
    if (modeSubstituteCode && familyDerivedResp?.data?.length) {
      return familyDerivedResp.data;
    }
    if (dailyAggGranularity) {
      return applyAggregateTransform(baseDataPoints || [], dailyAggGranularity);
    }
    return null;
  }, [
    isVirtualTransform, familyModeMeta, modeSubstituteCode, familyDerivedResp,
    baseDataPoints, dailyAggGranularity,
  ]);

  const dataPoints = familyDataPoints || baseDataPoints;

  // Telemetry-cards — пересчёт по подменённому ряду (если он есть).
  const familyViewStats = useMemo(() => {
    if (!familyDataPoints?.length) return null;
    const pts = familyDataPoints;
    const current = pts[pts.length - 1];
    const previous = pts.length > 1 ? pts[pts.length - 2] : null;
    const highest = pts.reduce((max, p) => (p.value > max.value ? p : max), pts[0]);
    const avg = pts.reduce((sum, p) => sum + p.value, 0) / pts.length;
    return {
      currentValue: current.value,
      currentDate: current.date,
      previousValue: previous?.value,
      previousDate: previous?.date,
      change: previous ? current.value - previous.value : null,
      highest: { value: highest.value, date: highest.date },
      average: avg,
      dataCount: pts.length,
    };
  }, [familyDataPoints]);

  const viewStats = familyViewStats || baseViewStats;
  const chartLoading = baseChartLoading || (modeSubstituteCode && loadingFamilyDerived);
  const familyForecastValues = familyForecastResp?.forecast?.values;
  const familyHasForecast = Array.isArray(familyForecastValues) && familyForecastValues.length > 0;
  const isSubstituteDerivedMode = !!modeSubstituteCode;
  const chartForecastData = (isFamily && familyMode !== 'level' && !isVirtualTransform)
    ? familyForecastResp
    : displayForecastData;
  const forecastEnabled = !!dailyAggGranularity || isSubstituteDerivedMode
    ? false
    : (isFamily && familyMode !== 'level' && !isVirtualTransform)
      ? familyHasForecast
      : baseForecastEnabled;
  const hasForecastDataForSection = isSubstituteDerivedMode
    ? false
    : (isFamily && familyMode !== 'level' && !isVirtualTransform)
      ? familyHasForecast
      : hasForecastData;

  // Подменяем `indicator` для downstream-компонентов (телеметрия, график,
  // download, таблица) — даёт правильный unit, frequency и расширенное имя
  // («Экспорт товаров (YoY %)» или «Безработица (Квартально)»).
  // Unit берётся из режима: если `modeMeta.unit` задан — используем его;
  // если не задан — сохраняем родительскую единицу.
  // Frequency берётся из `modeMeta.frequency` для real siblings (например,
  // wages-nominal-annual → annual) и из `DAILY_AGG_FREQUENCY[granularity]`
  // для daily-aggregation (Phase 5). Для virtual `mom`-transform или
  // `level`-режима frequency остаётся родительская. См. trap «View-mode
  // family metadata leak» в CONTEXT.md.
  // Хедер страницы остаётся оригинальным (`indicator.name`), чтобы
  // breadcrumbs и H1 не дёргались при смене mode — frequency-pill в Header
  // подменяется через отдельный prop `displayFrequency`.
  const effectiveIndicator = useMemo(() => {
    if (!indicator) return indicator;
    if (isFamily && familyMode !== 'level') {
      const suffix = familyModeMeta ? familyModeMeta.label : familyMode;
      return {
        ...indicator,
        unit: familyModeMeta?.unit ?? indicator.unit,
        frequency: familyModeMeta?.frequency ?? indicator.frequency,
        name: `${indicator.name} (${suffix})`,
      };
    }
    if (isUnemploymentCanonical && unemploymentSafeMode !== 'level') {
      const uMeta = unemploymentModeMeta(unemploymentSafeMode);
      return {
        ...indicator,
        frequency: uMeta.frequency,
        name: `${indicator.name} (${uMeta.label})`,
      };
    }
    if (isWagesNominalCanonical && wagesSafeMode !== 'level') {
      const wMeta = wagesNominalModeMeta(wagesSafeMode);
      return {
        ...indicator,
        unit: wMeta.unit,
        frequency: wMeta.frequency,
        name: `${indicator.name} (${wMeta.label})`,
      };
    }
    if (isGdpNominalCanonical && gdpNominalSafeMode !== 'level') {
      const gMeta = gdpNominalModeMeta(gdpNominalSafeMode);
      return {
        ...indicator,
        unit: gMeta.unit,
        frequency: gMeta.frequency,
        name: `${indicator.name} (${gMeta.label})`,
      };
    }
    if (isGdpRealCanonical && gdpRealSafeMode !== 'level') {
      const rMeta = gdpRealModeMeta(gdpRealSafeMode);
      return {
        ...indicator,
        unit: rMeta.unit,
        frequency: rMeta.frequency,
        name: `${indicator.name} (${rMeta.label})`,
      };
    }
    if (dailyAggGranularity) {
      const aggLabel = viewMode === 'weekly' ? 'среднее по неделям'
        : viewMode === 'monthly' ? 'среднее по месяцам'
          : viewMode === 'quarterly' ? 'среднее по кварталам'
            : viewMode === 'annual' ? 'среднее по годам' : 'среднее за период';
      return {
        ...indicator,
        frequency: DAILY_AGG_FREQUENCY[dailyAggGranularity] ?? indicator.frequency,
        name: (isKeyRateFamily || isRuoniaFamily || isBtcUsdFamily || isBrentFamily
          || isGoldPriceFamily || isUsdRubFamily || isEurRubFamily || isCnyRubFamily || isBudgetFamily
          || isBankCreditFamily || isHouseholdFinanceFamily || isMonetaryMassFamily
          || isLaborMarketFamily || isInternationalReservesFamily || isExternalDebtFamily
          || isGdpUseFamily)
          ? `${indicator.name} (${aggLabel})`
          : `${indicator.name} (${aggLabel}, avg)`,
      };
    }
    return indicator;
  }, [indicator, isFamily, familyMode, familyModeMeta, isUnemploymentCanonical, unemploymentSafeMode, isWagesNominalCanonical, wagesSafeMode, isGdpNominalCanonical, gdpNominalSafeMode, isGdpRealCanonical, gdpRealSafeMode, dailyAggGranularity, viewMode, isKeyRateFamily, isRuoniaFamily, isBtcUsdFamily, isBrentFamily, isGoldPriceFamily, isUsdRubFamily, isEurRubFamily, isCnyRubFamily, isBudgetFamily, isBankCreditFamily, isHouseholdFinanceFamily, isMonetaryMassFamily, isLaborMarketFamily, isInternationalReservesFamily, isExternalDebtFamily, isGdpUseFamily]);

  const adj = useCallback((v) => {
    if (v == null || !shouldSubtract100) return v;
    return Number(v) - 100;
  }, [shouldSubtract100]);

  useEffect(() => {
    const els = headerRef.current?.querySelectorAll('[data-animate]');
    if (!els?.length) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const tween = gsap.fromTo(els,
      { y: 30, opacity: 0 },
      { y: 0, opacity: 1, duration: 1, ease: 'power3.out', stagger: 0.1 }
    );
    return () => tween.kill();
  }, []);

  useEffect(() => {
    if (!indicator?.code) return;
    track(events.INDICATOR_VIEW, {
      indicator: indicator.code,
      indicatorCategory: indicator.category,
    });
  }, [indicator?.code, indicator?.category]);

  useScrollDepth({
    key: code,
    page: 'indicator',
    indicator: code,
    indicatorCategory: indicator?.category,
  });

  const handleChartData = useCallback((data) => {
    setChartData(data);
  }, [setChartData]);

  const handleRangeChange = useCallback((range) => {
    setCurrentRange(range);
  }, [setCurrentRange]);

  const downloadMeta = useMemo(() => ({
    name: effectiveIndicator?.name, unit: effectiveIndicator?.unit,
  }), [effectiveIndicator?.name, effectiveIndicator?.unit]);

  const downloadMode = isPriceCategory ? chartMode : null;

  const handleDownloadExcel = useCallback(() => {
    downloadExcel(chartData, downloadMode, code, currentRange, downloadMeta);
    track(events.DOWNLOAD_EXCEL, { indicator: code, range: currentRange, indicatorCategory: indicator?.category });
  }, [chartData, downloadMode, code, currentRange, downloadMeta, indicator?.category]);

  const handleDownloadCSV = useCallback(() => {
    downloadCSV(chartData, downloadMode, code, currentRange, downloadMeta);
    track(events.DOWNLOAD_CSV, { indicator: code, range: currentRange, indicatorCategory: indicator?.category });
  }, [chartData, downloadMode, code, currentRange, downloadMeta, indicator?.category]);

  const chartEmptyHint = useMemo(() => {
    if (dataError) {
      return 'Не удалось получить исторический ряд. Нажмите «Повторить» выше или проверьте backend / прокси Vite.';
    }
    if (!loadingData && (dataPoints?.length ?? 0) === 0) {
      return (
        'В API пока нет точек для этого кода — например, прод ещё без backfill ключевой ставки, или локальный backend не запущен. '
        + 'После появления данных график заполнится автоматически.'
      );
    }
    return undefined;
  }, [dataError, loadingData, dataPoints]);

  const refetchIndicatorPage = useCallback(() => {
    refetchInd();
    refetchData();
    if (isPriceCategory) refetchInflation();
    refetchForecast();
    if (modeSubstituteCode) refetchFamilyForecast();
  }, [
    refetchInd, refetchData, refetchInflation, refetchForecast,
    refetchFamilyForecast, modeSubstituteCode, isPriceCategory,
  ]);

  const apiBannerFetching = fetchingInd || fetchingData;
  const viewModeContent = getViewModeContent({
    chartMode, safeViewMode, isPriceCategory, isHousingFamily, isPpiFamily,
    isAutoLoanFamily, isMortgageFamily, isCbrTermSliceFamily, isKeyRateFamily, isRuoniaFamily,
    isBtcUsdFamily, isBrentFamily, isGoldPriceFamily, isUsdRubFamily, isEurRubFamily, isCnyRubFamily,
    isBudgetFamily, isBankCreditFamily, isHouseholdFinanceFamily, isMonetaryMassFamily,
    isLaborMarketFamily,
    isUnemploymentFamily,
    isWagesNominalFamily,
    isGdpNominalFamily,
    isGdpRealFamily,
    isInternationalReservesFamily,
    isExternalDebtFamily,
    isGdpUseFamily,
    indicator,
  });
  const s = viewStats;

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-24 md:pb-28">
      {(indError || dataError) && (
        <div className="mb-8">
          <ApiRetryBanner
            onRetry={refetchIndicatorPage}
            isFetching={apiBannerFetching}
          >
            {indError && (
              <span className="block">
                Карточка индикатора не загрузилась
                {indErr?.message ? ` (${indErr.message})` : ''}.
              </span>
            )}
            {dataError && (
              <span className="block">
                Исторические данные недоступны — график и таблица без ряда.
              </span>
            )}
          </ApiRetryBanner>
        </div>
      )}

      <IndicatorDetailHeader
        indicator={indicator}
        code={code}
        loading={loadingInd}
        headerRef={headerRef}
        displayFrequency={effectiveIndicator?.frequency}
      />

      <IndicatorTelemetryGrid
        indicator={effectiveIndicator}
        viewStats={s}
        stats={stats}
        isPriceCategory={isPriceCategory}
        isHousingFamily={isHousingFamily}
        isPpiFamily={isPpiFamily}
        isAutoLoanFamily={isAutoLoanFamily}
        isCbrTermSliceFamily={isCbrTermSliceFamily}
        isKeyRateFamily={isKeyRateFamily}
        safeViewMode={safeViewMode}
        cpiPrevDate={cpiPrevDate}
        adj={adj}
        loading={
          loadingInd
          || (chartMode === 'inflation' && loadingInflation)
          || (chartMode === 'annual' && loadingAnnual)
          || (chartMode === 'weekly' && loadingWeekly)
          || (chartMode === 'quarterly' && loadingQuarterly)
          || (chartMode === 'yoy' && loadingYoy)
          || (chartMode === 'qoq' && loadingQoq)
          || (chartMode === 'period-monthly' && loadingPeriodMonthly)
          || (chartMode === 'period-weekly' && loadingPeriodWeekly)
          || (chartMode === 'mom' && loadingData)
          || (chartMode === 'index' && loadingData)
        }
      />

      {/* Оба переключателя — НАД графиком, сверху вниз:
          1) «Состав» (категории-родственники: cpi → cpi-food / housing-primary →
             housing-secondary и т.д.) — меняет сам индикатор и весь набор данных.
          2) «Режим инфляции» (мес / кв / год / нед / индекс) — меняет представление
             того же индикатора, должен стоять сразу над графиком.
          3) График.
          Под графиком — никаких переключателей (только range-пресеты внутри самого
          IndicatorChart и форекаст-toggle в тулбаре). */}
      <FrequencySwitcher
        currentCode={code}
        currentFrequency={indicator?.frequency}
        alternateFrequencies={indicator?.alternate_frequencies}
        primaryIndicatorCode={indicator?.primary_indicator_code}
        indicatorCategory={indicator?.category}
      />

      {isPriceCategory ? (
        <CpiIndicatorControls
          variantGroup={variantGroup}
          currentCode={code}
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isHousingFamily ? (
        <HousingIndicatorControls
          variantGroup={variantGroup}
          currentCode={code}
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isPpiFamily ? (
        <PpiIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isAutoLoanFamily ? (
        <AutoLoanIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isMortgageFamily ? (
        <MortgageRateIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isCbrTermSliceFamily ? (
        <CbrTermSliceRateIndicatorControls
          variantGroup={variantGroup}
          currentCode={code}
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isKeyRateFamily ? (
        <KeyRateIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isRuoniaFamily ? (
        <RuoniaIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isBtcUsdFamily ? (
        <BtcUsdIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isGoldPriceFamily ? (
        <GoldPriceIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isBrentFamily ? (
        <BrentIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isUsdRubFamily ? (
        <UsdRubIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isEurRubFamily ? (
        <EurRubIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isCnyRubFamily ? (
        <CnyRubIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isBudgetFamily ? (
        <BudgetIndicatorControls
          variantGroup={variantGroup}
          currentCode={code}
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isInternationalReservesFamily ? (
        <InternationalReservesIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isExternalDebtFamily ? (
        <ExternalDebtIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isGdpUseFamily ? (
        <GdpUseIndicatorControls
          variantGroup={variantGroup}
          currentCode={code}
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isHouseholdFinanceFamily ? (
        <HouseholdFinanceIndicatorControls
          variantGroup={variantGroup}
          currentCode={code}
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isMonetaryMassFamily ? (
        <MonetaryMassIndicatorControls
          variantGroup={variantGroup}
          currentCode={code}
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isGdpRealFamily && isGdpRealCanonical ? (
        <GdpRealIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isGdpNominalFamily && isGdpNominalCanonical ? (
        <GdpNominalIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isWagesNominalFamily && isWagesNominalCanonical ? (
        <WagesNominalIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isUnemploymentFamily && isUnemploymentCanonical ? (
        <UnemploymentIndicatorControls
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isLaborMarketFamily ? (
        <LaborMarketIndicatorControls
          variantGroup={variantGroup}
          currentCode={code}
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : isBankCreditFamily ? (
        <BankCreditIndicatorControls
          variantGroup={variantGroup}
          currentCode={code}
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      ) : (
        <VariantGroupPicker group={variantGroup} currentCode={code} />
      )}

      {isFamily && !isHousingFamily && !isPpiFamily && !isAutoLoanFamily && !isMortgageFamily
        && !isCbrTermSliceFamily && !isKeyRateFamily && !isRuoniaFamily && !isBtcUsdFamily
        && !isBrentFamily && !isGoldPriceFamily && !isUsdRubFamily && !isEurRubFamily
        && !isCnyRubFamily && !isBudgetFamily && !isBankCreditFamily && !isHouseholdFinanceFamily
        && !isMonetaryMassFamily && !isLaborMarketFamily && !isUnemploymentFamily
        && !isWagesNominalFamily && !isGdpNominalFamily && !isGdpRealFamily
        && !isInternationalReservesFamily
        && !isExternalDebtFamily && !isGdpUseFamily && (
        <ViewModePicker
          title="Режим отображения"
          modes={viewFamily.modes.map((m) => ({ mode: m.mode, label: m.label }))}
          currentMode={familyMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      )}

      {/* Phase 5: daily-агрегации для прочих daily (не key-rate — свой picker) */}
      {!isFamily && !isKeyRateFamily && !isRuoniaFamily && !isBtcUsdFamily && !isBrentFamily
        && !isGoldPriceFamily && !isUsdRubFamily && !isEurRubFamily && !isCnyRubFamily && !isBudgetFamily
        && !isBankCreditFamily && !isHouseholdFinanceFamily && !isMonetaryMassFamily
        && !isLaborMarketFamily && !isUnemploymentFamily && !isWagesNominalFamily
        && !isGdpNominalFamily && !isGdpRealFamily
        && !isInternationalReservesFamily && !isExternalDebtFamily
        && !isGdpUseFamily
        && indicator?.frequency === 'daily' && (
        <ViewModePicker
          title="Частота отображения"
          modes={[
            { mode: 'level', label: 'Ежедневно' },
            { mode: 'weekly', label: 'Понедельно' },
            { mode: 'monthly', label: 'Помесячно' },
            { mode: 'quarterly', label: 'Поквартально' },
            { mode: 'annual', label: 'Годово' },
          ]}
          currentMode={dailyAggGranularity ? viewMode : 'level'}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      )}

      <IndicatorChartSection
        code={code}
        indicator={effectiveIndicator}
        chartMode={chartMode}
        safeViewMode={safeViewMode}
        isPriceCategory={isPriceCategory}
        isHousingFamily={isHousingFamily}
        isPpiFamily={isPpiFamily}
        isAutoLoanFamily={isAutoLoanFamily}
        isCbrTermSliceFamily={isCbrTermSliceFamily}
        isKeyRateFamily={isKeyRateFamily}
        isRuoniaFamily={isRuoniaFamily}
        isBtcUsdFamily={isBtcUsdFamily}
        isBrentFamily={isBrentFamily}
        isGoldPriceFamily={isGoldPriceFamily}
        isUsdRubFamily={isUsdRubFamily}
        isEurRubFamily={isEurRubFamily}
        isCnyRubFamily={isCnyRubFamily}
        isBudgetFamily={isBudgetFamily}
        isBankCreditFamily={isBankCreditFamily}
        isHouseholdFinanceFamily={isHouseholdFinanceFamily}
        isMonetaryMassFamily={isMonetaryMassFamily}
        isLaborMarketFamily={isLaborMarketFamily}
        isUnemploymentFamily={isUnemploymentFamily}
        isWagesNominalFamily={isWagesNominalFamily}
        isGdpNominalFamily={isGdpNominalFamily}
        isGdpRealFamily={isGdpRealFamily}
        isInternationalReservesFamily={isInternationalReservesFamily}
        isExternalDebtFamily={isExternalDebtFamily}
        isGdpUseFamily={isGdpUseFamily}
        isMortgageFamily={isMortgageFamily}
        chartLoading={chartLoading}
        inflationResp={inflationResp}
        dataPoints={dataPoints}
        momDataPoints={momDataPoints}
        quarterlyDataPoints={quarterlyDataPoints}
        annualDataPoints={annualDataPoints}
        weeklyDataPoints={weeklyDataPoints}
        yoyDataPoints={yoyDataPoints}
        qoqDataPoints={qoqDataPoints}
        periodMonthlyDataPoints={periodMonthlyDataPoints}
        periodWeeklyDataPoints={periodWeeklyDataPoints}
        displayForecastData={chartForecastData}
        quarterlyForecastData={quarterlyForecastData}
        annualForecastResp={annualForecastResp}
        weeklyForecastData={weeklyForecastData}
        yoyForecastData={yoyForecastData}
        qoqForecastData={qoqForecastData}
        periodMonthlyForecastData={periodMonthlyForecastData}
        periodWeeklyForecastData={periodWeeklyForecastData}
        forecastEnabled={forecastEnabled}
        showForecast={showForecast}
        onToggleForecast={() => setShowForecast((v) => !v)}
        onChartData={handleChartData}
        onRangeChange={handleRangeChange}
        emptyHint={chartEmptyHint}
        onDownloadCsv={handleDownloadCSV}
        onDownloadExcel={handleDownloadExcel}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-16">
        <IndicatorMethodologyPanel
          indicator={indicator}
          content={viewModeContent}
        />
        <IndicatorForecastSection
          indicator={indicator}
          chartMode={chartMode}
          safeViewMode={safeViewMode}
          inflationResp={inflationResp}
          displayForecastData={chartForecastData}
          quarterlyForecastData={quarterlyForecastData}
          annualForecastResp={annualForecastResp}
          weeklyForecastData={weeklyForecastData}
          yoyForecastData={yoyForecastData}
          qoqForecastData={qoqForecastData}
          periodMonthlyForecastData={periodMonthlyForecastData}
          periodWeeklyForecastData={periodWeeklyForecastData}
          forecastEnabled={forecastEnabled}
          showForecast={showForecast}
          hasForecastData={hasForecastDataForSection}
        />
      </div>

      <IndicatorDataTableSection
        indicator={effectiveIndicator}
        chartMode={chartMode}
        safeViewMode={safeViewMode}
        isPriceCategory={isPriceCategory}
        isHousingFamily={isHousingFamily}
        isPpiFamily={isPpiFamily}
        isAutoLoanFamily={isAutoLoanFamily}
        isMortgageFamily={isMortgageFamily}
        isCbrTermSliceFamily={isCbrTermSliceFamily}
        isKeyRateFamily={isKeyRateFamily}
        isRuoniaFamily={isRuoniaFamily}
        isBtcUsdFamily={isBtcUsdFamily}
        isBrentFamily={isBrentFamily}
        isGoldPriceFamily={isGoldPriceFamily}
        isUsdRubFamily={isUsdRubFamily}
        isEurRubFamily={isEurRubFamily}
        isCnyRubFamily={isCnyRubFamily}
        isBudgetFamily={isBudgetFamily}
        isBankCreditFamily={isBankCreditFamily}
        isHouseholdFinanceFamily={isHouseholdFinanceFamily}
        isMonetaryMassFamily={isMonetaryMassFamily}
        isLaborMarketFamily={isLaborMarketFamily}
        isUnemploymentFamily={isUnemploymentFamily}
        isWagesNominalFamily={isWagesNominalFamily}
        isGdpNominalFamily={isGdpNominalFamily}
        isGdpRealFamily={isGdpRealFamily}
        isInternationalReservesFamily={isInternationalReservesFamily}
        isExternalDebtFamily={isExternalDebtFamily}
        inflationResp={inflationResp}
        dataPoints={dataPoints}
        momDataPoints={momDataPoints}
        quarterlyDataPoints={quarterlyDataPoints}
        annualDataPoints={annualDataPoints}
        weeklyDataPoints={weeklyDataPoints}
        yoyDataPoints={yoyDataPoints}
        qoqDataPoints={qoqDataPoints}
        periodMonthlyDataPoints={periodMonthlyDataPoints}
        periodWeeklyDataPoints={periodWeeklyDataPoints}
      />

      <IndicatorSeoBlocks blocks={indicator?.seo_blocks} indicatorCode={code} />

      {relatedIndicators.length > 0 && (
        <section className="mt-16">
          <div className="flex items-center gap-4 mb-6 flex-wrap">
            <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold">
              Похожие индикаторы
            </h2>
            <div className="h-[1px] flex-1 bg-border-subtle" />
            <Link
              to={`/compare?a=${code}`}
              onClick={() => track(events.RELATED_LINK_CLICK, {
                from: code,
                to: 'compare',
                surface: 'indicator-cta',
              })}
              className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-champagne hover:text-champagne-muted transition-colors"
            >
              <GitCompare className="w-3.5 h-3.5" />
              Сравнить
            </Link>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
            {relatedIndicators.map((rel) => {
              const card = relatedIndicatorCardCopy(rel.code, rel.name, rel.unit);
              return (
              <Link
                key={rel.code}
                to={`/indicator/${rel.code}`}
                onClick={() => track(events.RELATED_INDICATOR_CLICK, {
                  from: code,
                  to: rel.code,
                  indicatorCategory: indicator?.category,
                  surface: 'indicator-related',
                })}
                className="group flex items-start gap-3 p-4 rounded-2xl border border-border-subtle bg-surface hover:border-champagne/30 transition-colors min-h-[4.75rem]"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-text-primary leading-snug line-clamp-2 group-hover:text-champagne transition-colors">
                    {card.title}
                  </p>
                  {card.subtitle && (
                    <p className="mt-1.5 text-[10px] font-mono uppercase tracking-widest text-text-tertiary leading-relaxed line-clamp-2">
                      {card.subtitle}
                    </p>
                  )}
                </div>
                <ArrowRight className="w-4 h-4 text-text-tertiary shrink-0 mt-0.5 group-hover:text-champagne group-hover:translate-x-0.5 transition-all" />
              </Link>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
