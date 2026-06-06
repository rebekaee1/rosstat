import DataTable from './DataTable';

import { getCpiTableTitle } from '../lib/cpiViewModeContent';
import { getHousingTableTitle } from '../lib/housingViewModeContent';
import { getPpiTableTitle } from '../lib/ppiViewModeContent';
import { getAutoLoanTableTitle } from '../lib/autoLoanViewModeContent';
import { getMortgageTableTitle } from '../lib/mortgageRateViewModeContent';
import { getCbrTermSliceTableTitle } from '../lib/cbrTermSliceRateContent';
import { getKeyRateTableTitle } from '../lib/keyRateViewModeContent';
import { getRuoniaTableTitle } from '../lib/ruoniaViewModeContent';
import { getBtcUsdTableTitle } from '../lib/btcUsdViewModeContent';
import { getBrentTableTitle } from '../lib/brentViewModeContent';
import { getGoldPriceTableTitle } from '../lib/goldPriceViewModeContent';
import { getCnyRubTableTitle } from '../lib/cnyRubViewModeContent';
import { getEurRubTableTitle } from '../lib/eurRubViewModeContent';
import { getUsdRubTableTitle } from '../lib/usdRubViewModeContent';
import { getBudgetTableTitle } from '../lib/budgetViewModeContent';
import { getBankCreditTableTitle } from '../lib/bankCreditViewModeContent';
import { getHouseholdFinanceTableTitle } from '../lib/householdFinanceViewModeContent';
import { getMonetaryMassTableTitle } from '../lib/monetaryMassViewModeContent';
import { getLaborMarketTableTitle } from '../lib/laborMarketViewModeContent';
import { getUnemploymentTableTitle } from '../lib/unemploymentViewModeContent';
import { getWagesNominalTableTitle } from '../lib/wagesNominalViewModeContent';
import { getGdpNominalTableTitle } from '../lib/gdpNominalViewModeContent';
import { getGdpRealTableTitle } from '../lib/gdpRealViewModeContent';
import { getExternalDebtTableTitle } from '../lib/externalDebtViewModeContent';
import { getGdpUseTableTitle } from '../lib/gdpUseViewModeContent';
import { getInternationalReservesTableTitle } from '../lib/internationalReservesViewModeContent';
import { chartSeriesForViewMode } from '../lib/chartSeriesForViewMode';

function tableTitle({
  chartMode, isPriceCategory, isHousingFamily, isPpiFamily, isAutoLoanFamily, isMortgageFamily,
  isCbrTermSliceFamily, isKeyRateFamily, isRuoniaFamily, isBtcUsdFamily, isBrentFamily,
  isGoldPriceFamily,
  isUsdRubFamily,
  isEurRubFamily,
  isCnyRubFamily,
  isBudgetFamily,
  isBankCreditFamily,
  isHouseholdFinanceFamily,
  isLaborMarketFamily,
  isUnemploymentFamily,
  isWagesNominalFamily,
  isGdpNominalFamily,
  isGdpRealFamily,
  isMonetaryMassFamily,
  isInternationalReservesFamily,
  isExternalDebtFamily,
  isGdpUseFamily,
  indicator, safeViewMode,
}) {
  if (isWagesNominalFamily) {
    return getWagesNominalTableTitle(chartMode);
  }
  if (isGdpNominalFamily) {
    return getGdpNominalTableTitle(chartMode);
  }
  if (isGdpRealFamily) {
    return getGdpRealTableTitle(chartMode);
  }
  if (isUnemploymentFamily) {
    return getUnemploymentTableTitle(chartMode);
  }
  if (isPpiFamily) {
    return getPpiTableTitle(chartMode, safeViewMode);
  }
  if (isGdpUseFamily) {
    return getGdpUseTableTitle(chartMode, indicator?.code);
  }
  if (isExternalDebtFamily) {
    return getExternalDebtTableTitle(chartMode);
  }
  if (isInternationalReservesFamily) {
    return getInternationalReservesTableTitle(chartMode);
  }
  if (isLaborMarketFamily && indicator?.code) {
    return getLaborMarketTableTitle(chartMode, indicator.code);
  }
  if (isMonetaryMassFamily && indicator?.code) {
    return getMonetaryMassTableTitle(chartMode, indicator.code);
  }
  if (isGoldPriceFamily) {
    return getGoldPriceTableTitle(chartMode);
  }
  if (isBudgetFamily && indicator?.code) {
    return getBudgetTableTitle(chartMode, indicator.code);
  }
  if (isHouseholdFinanceFamily && indicator?.code) {
    return getHouseholdFinanceTableTitle(chartMode, indicator.code);
  }
  if (isBankCreditFamily) {
    return getBankCreditTableTitle(chartMode);
  }
  if (isBrentFamily) {
    return getBrentTableTitle(chartMode);
  }
  if (isUsdRubFamily) {
    return getUsdRubTableTitle(chartMode);
  }
  if (isEurRubFamily) {
    return getEurRubTableTitle(chartMode);
  }
  if (isCnyRubFamily) {
    return getCnyRubTableTitle(chartMode);
  }
  if (isBtcUsdFamily) {
    return getBtcUsdTableTitle(chartMode);
  }
  if (isRuoniaFamily) {
    return getRuoniaTableTitle(chartMode);
  }
  if (isKeyRateFamily) {
    return getKeyRateTableTitle(chartMode);
  }
  if (isMortgageFamily) {
    return getMortgageTableTitle(chartMode);
  }
  if (isAutoLoanFamily) {
    return getAutoLoanTableTitle(chartMode);
  }
  if (isCbrTermSliceFamily) {
    return getCbrTermSliceTableTitle(chartMode, indicator?.code);
  }
  if (isHousingFamily && indicator?.code) {
    return getHousingTableTitle(chartMode, indicator.code);
  }
  if (isPriceCategory && indicator?.code) {
    return getCpiTableTitle(chartMode, indicator.code, safeViewMode);
  }
  return `Исторические данные — ${indicator?.name || 'ряд'}`;
}

function dateFormatFor({ chartMode, indicator, safeViewMode }) {
  if (safeViewMode === 'index-quarterly') return 'quarterly';
  if (safeViewMode === 'index-annual') return 'annual';
  if (chartMode === 'quarterly' || chartMode === 'qoq') return 'quarterly';
  if (chartMode === 'annual') return 'annual';
  if (chartMode === 'yoy' || chartMode === 'period-weekly' || chartMode === 'period-monthly') return 'full';
  if (chartMode !== 'inflation' && indicator?.frequency === 'daily') return 'day';
  if (indicator?.frequency === 'quarterly') return 'quarterly';
  if (indicator?.frequency === 'annual') return 'annual';
  return 'full';
}

/**
 * Финальная секция страницы — таблица всех исторических точек выбранного
 * режима с поиском, сортировкой и пагинацией. Заголовок и формат даты
 * подбираются по chartMode.
 */
export default function IndicatorDataTableSection({
  indicator,
  chartMode,
  safeViewMode,
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
  isUsdRubFamily,
  isEurRubFamily,
  isCnyRubFamily,
  isBudgetFamily,
  isBankCreditFamily,
  isHouseholdFinanceFamily,
  isLaborMarketFamily,
  isUnemploymentFamily,
  isWagesNominalFamily,
  isGdpNominalFamily,
  isGdpRealFamily,
  isMonetaryMassFamily,
  isInternationalReservesFamily,
  isExternalDebtFamily,
  isGdpUseFamily,
  inflationResp,
  dataPoints,
  momDataPoints,
  quarterlyDataPoints,
  annualDataPoints,
  weeklyDataPoints,
  yoyDataPoints,
  qoqDataPoints,
  periodMonthlyDataPoints,
  periodWeeklyDataPoints,
}) {
  const data = chartMode === 'inflation'
    ? (inflationResp?.actuals || [])
    : chartSeriesForViewMode({
      chartMode,
      isKeyRateFamily,
      isRuoniaFamily,
      isBtcUsdFamily,
      isBrentFamily,
      isGoldPriceFamily,
      isUsdRubFamily,
      isEurRubFamily,
      isCnyRubFamily,
      isBudgetFamily,
      isBankCreditFamily,
      isHouseholdFinanceFamily,
      isLaborMarketFamily,
      isUnemploymentFamily,
      isWagesNominalFamily,
      isGdpNominalFamily,
      isGdpRealFamily,
      isMonetaryMassFamily,
      isInternationalReservesFamily,
      isExternalDebtFamily,
      isGdpUseFamily,
      dataPoints,
      momDataPoints,
      quarterlyDataPoints,
      annualDataPoints,
      weeklyDataPoints,
      yoyDataPoints,
      qoqDataPoints,
      periodWeeklyDataPoints,
      periodMonthlyDataPoints,
    });

  return (
    <section>
      <DataTable
        key={`${indicator?.code}-${chartMode}`}
        data={data}
        title={tableTitle({
          chartMode, isPriceCategory, isHousingFamily, isPpiFamily, isAutoLoanFamily,
          isMortgageFamily, isCbrTermSliceFamily, isKeyRateFamily, isRuoniaFamily,
          isBtcUsdFamily, isBrentFamily, isGoldPriceFamily, isUsdRubFamily, isEurRubFamily,
          isCnyRubFamily,
          isBudgetFamily,
          isBankCreditFamily,
          isHouseholdFinanceFamily,
          isLaborMarketFamily,
          isUnemploymentFamily,
          isWagesNominalFamily,
          isGdpNominalFamily,
          isGdpRealFamily,
          isMonetaryMassFamily,
          isInternationalReservesFamily,
          isExternalDebtFamily,
          isGdpUseFamily,
          indicator, safeViewMode,
        })}
        dateFormat={dateFormatFor({ chartMode, indicator, safeViewMode })}
        unit={chartMode === 'index' ? 'индекс' : ((isPpiFamily || isHousingFamily) && chartMode !== 'index' ? '%' : (indicator?.unit || '%'))}
      />
    </section>
  );
}
